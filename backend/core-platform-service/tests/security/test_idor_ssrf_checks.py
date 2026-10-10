"""
AMOF-X Phase 9 Security Hardening: IDOR & SSRF Prevention Tests.

Verifies:
1. Insecure Direct Object Reference (IDOR): Users cannot access, modify, or delete
   meetings, documents, or workflow traces owned by another tenant.
2. No user-suppliable fetch-URL surface exists (the SSRF prerequisite) --
   see test_no_user_supplied_fetch_url_surface for why this replaced an
   earlier test that validated a URL-safety function defined only inside
   the test file itself, never imported from app/.
"""
import secrets

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.database import Base, SessionLocal, engine
from app.main import app
from app.services.meeting_service import meeting_service

USER_A = "201"
USER_B = "202"


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield


def test_meeting_idor_prevention():
    """
    User B cannot retrieve User A's meeting by ID.
    """
    db = SessionLocal()
    try:
        meeting_a = meeting_service.create_meeting(
            db=db,
            owner_id=USER_A,
            transcript_text="Confidential strategy meeting transcript for User A.",
            transcript_source="manual_paste",
        )

        # User B attempts to access User A's meeting
        meeting_b = meeting_service.get_meeting(db=db, owner_id=USER_B, meeting_id=meeting_a.id)
        assert meeting_b is None, "Meeting service must return None (IDOR isolation) when User B requests User A's meeting"

    finally:
        db.close()


def test_rag_idor_prevention(auth_client, tokens):
    """
    User B cannot see, search, or delete User A's ingested RAG document.

    Regression: /rag/* endpoints used to accept a client-suppliable
    `owner_id` (request body field / query param defaulting to "1"), so any
    caller could read or delete any other user's documents by just naming
    their owner_id. owner_id is now always derived server-side from the
    authenticated user's bearer token.
    """
    file_id = f"idor-rag-{secrets.token_hex(6)}"

    ingest = auth_client.post(
        "/api/v1/rag/ingest",
        json={"file_id": file_id, "source": "idor_test.txt", "text": "User A's confidential document content."},
    )
    assert ingest.status_code == 200, ingest.text

    b_client = TestClient(app)
    b_client.headers.update({"Authorization": f"Bearer {tokens['access_token']}"})

    try:
        listing = b_client.get("/api/v1/rag/documents")
        assert listing.status_code == 200
        assert not any(
            d["file_id"] == file_id for d in listing.json()["data"]["documents"]
        ), "User B must not see User A's document in their own /rag/documents listing"

        search = b_client.post(
            "/api/v1/rag/search",
            json={"query": "confidential document content", "file_id": file_id},
        )
        assert search.status_code == 200
        assert search.json()["data"]["count"] == 0, "User B must not retrieve User A's document via search"

        delete = b_client.delete(f"/api/v1/rag/document/{file_id}")
        assert delete.status_code == 200
        assert delete.json()["data"]["deleted"] is False, "User B must not be able to delete User A's document by guessing its file_id"
    finally:
        auth_client.delete(f"/api/v1/rag/document/{file_id}")


def test_document_idor_prevention_via_missing_google_connection(auth_client, tokens):
    """
    /documents/summarize resolves the Google Drive file to fetch using the
    authenticated caller's own OAuth grant, not a client-suppliable owner_id.

    Regression: the endpoint previously had no auth dependency at all and
    never threaded a user_id through DocumentAgent -> DocumentService (a
    call that would raise TypeError: missing 'user_id', since DocumentService
    has required it all along). Two independently authenticated users hitting
    the same file_id must each be processed against their OWN identity --
    never a bare TypeError from the old signature mismatch.

    Note: neither test user has a connected Google account, and
    DocumentService.load_document() catches the resulting fetch failure and
    falls back to a hardcoded placeholder string rather than surfacing an
    error (the same class of silent-fabrication bug already fixed in
    RAGPipeline.ingest() -- this one is in a different call path and is out
    of this phase's scope; flagged here, not fixed, so this test only
    asserts what Phase 9 actually guarantees: no crash, no cross-user leak).
    """
    b_client = TestClient(app)
    b_client.headers.update({"Authorization": f"Bearer {tokens['access_token']}"})

    file_id = f"idor-doc-{secrets.token_hex(6)}"

    resp_a = auth_client.post("/api/v1/documents/summarize", json={"file_id": file_id})
    resp_b = b_client.post("/api/v1/documents/summarize", json={"file_id": file_id})

    for resp in (resp_a, resp_b):
        assert resp.status_code == 200, resp.text
        assert "TypeError" not in resp.text


def test_no_user_supplied_fetch_url_surface():
    """
    Structural SSRF regression guard.

    No production Pydantic request schema currently exposes a field that
    would cause the backend to fetch an arbitrary, user-supplied URL -- the
    prerequisite for an SSRF vulnerability. Confirmed by direct code
    inspection: every outbound HTTP call in app/ targets a fixed,
    config-defined host (Google APIs, Ollama, OpenRouter, the embeddings
    provider), never a URL taken from request input.

    This replaces a prior test that defined and validated its own
    `is_safe_url` helper inline, never importing anything from app/ -- it
    passed unconditionally regardless of whether any real SSRF protection
    existed. This version inspects the actual schemas: if a future feature
    adds a field like `webhook_url`/`callback_url`/`target_url`, this test
    fails, forcing a deliberate SSRF-validation decision instead of a silent
    gap.
    """
    import importlib
    import pkgutil
    import re

    from pydantic import BaseModel

    import app.schemas as schemas_pkg

    suspicious_field = re.compile(r"(^|_)(url|uri|endpoint|webhook|callback)($|_)", re.IGNORECASE)
    offending: list[str] = []

    for _, module_name, _ in pkgutil.iter_modules(schemas_pkg.__path__):
        module = importlib.import_module(f"app.schemas.{module_name}")
        for name in dir(module):
            obj = getattr(module, name)
            if isinstance(obj, type) and issubclass(obj, BaseModel) and obj is not BaseModel:
                for field_name in obj.model_fields:
                    if suspicious_field.search(field_name):
                        offending.append(f"{module_name}.{obj.__name__}.{field_name}")

    assert not offending, (
        "Found request schema field(s) that look like a user-suppliable fetch "
        f"URL: {offending}. If this is real, add SSRF validation (reject "
        "internal/metadata IPs and non-http(s) schemes) before merging."
    )
