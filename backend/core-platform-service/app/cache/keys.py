"""
Project 9 — Deterministic Cache Key Generator
Normalizes text queries and constructs canonical JSON hashes with multi-tenant
user, workspace, capability, model, and data version isolation.
"""

import hashlib
import json
import re
from typing import Any, Dict, Optional
from app.core.config import settings


def normalize_query(query: str) -> str:
    """
    Normalizes input query string:
    1. Removes leading/trailing whitespace.
    2. Converts to lowercase.
    3. Collapses multiple contiguous spaces into single space.
    """
    if not query:
        return ""
    text = query.strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def build_canonical_payload(
    query: str,
    capability: str,
    user_id: str,
    workspace_id: str,
    data_version: str = "v1",
    model: str = "qwen2.5:7b",
    system_prompt_version: str = "v1",
    temperature: float = 0.2,
    additional_params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Constructs a canonical payload dictionary for exact hashing.
    """
    norm_query = normalize_query(query)
    payload = {
        "capability": capability,
        "data_version": data_version,
        "model": model,
        "query": norm_query,
        "system_prompt_version": system_prompt_version,
        "temperature": temperature,
        "user_id": str(user_id),
        "workspace_id": str(workspace_id),
    }
    if additional_params:
        # Include extra parameters securely
        for k in sorted(additional_params.keys()):
            val = additional_params[k]
            if isinstance(val, (str, int, float, bool)):
                payload[f"param_{k}"] = val

    return payload


def build_exact_hash(payload: Dict[str, Any]) -> str:
    """
    Computes SHA-256 hash of minified, key-sorted canonical JSON.
    """
    canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def build_cache_key(
    query: str,
    capability: str,
    user_id: str,
    workspace_id: str,
    data_version: str = "v1",
    model: str = "qwen2.5:7b",
    system_prompt_version: str = "v1",
    temperature: float = 0.2,
    additional_params: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Builds deterministic exact cache key:
    amof:v1:user:{user_id}:ws:{workspace_id}:{capability}:v{data_version}:{sha256_hash}
    """
    payload = build_canonical_payload(
        query=query,
        capability=capability,
        user_id=user_id,
        workspace_id=workspace_id,
        data_version=data_version,
        model=model,
        system_prompt_version=system_prompt_version,
        temperature=temperature,
        additional_params=additional_params,
    )
    sha256_hash = build_exact_hash(payload)
    return (
        f"{settings.CACHE_NAMESPACE}:{settings.CACHE_SCHEMA_VERSION}:"
        f"user:{user_id}:ws:{workspace_id}:{capability}:v{data_version}:{sha256_hash}"
    )
