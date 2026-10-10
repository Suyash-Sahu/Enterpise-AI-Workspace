# Enterprise AI Workspace — AMOF

An AI-native workspace that unifies company documents, a sample database, Gmail, Google Drive, and Google Calendar into one conversational interface, powered by **AMOF** (Adaptive Multi-agent Orchestration Framework). AMOF decomposes a request, routes each sub-task to a specialized agent, decides per-task whether it runs **locally (Ollama)** or in the **cloud (OpenRouter/LiteLLM)** based on data sensitivity, and gates every side-effecting action (e.g. sending an email) behind human approval.

This README reflects the actual state of the codebase, verified by reading the code and running the test suites — not the original project plan. Where the two disagree, the code wins.

---

## What's actually built

### Core orchestration
- **AMOF Supervisor** — a real intent → plan → persist → execute → verify → replan → synthesize loop. Every plan and step is persisted (`WorkflowPlan`/`WorkflowStep`), every routing decision is recorded, every dispatch is approval-gated.
- **ATGO task decomposer** — turns a multi-part request into a real, validated multi-node DAG constrained to registered capabilities. Execution of that graph is currently sequential, not parallel.
- **CDRP (confidence-driven replanning)** — a capped, recorded replan loop triggered by the verifier's confidence band, re-dispatching through the same approval-gated path as the main loop.
- **Execution Router** — hard-constraint privacy routing across 4 tiers (`PUBLIC`/`INTERNAL`/`CONFIDENTIAL`/`RESTRICTED`) between local (Ollama) and cloud (OpenRouter/LiteLLM) execution. Privacy is never relaxed for cost or quality.
- **Capability registry** — every callable capability declares its own risk level, side effects, and whether it requires human approval or verification, enforced at registration time.

### Agents & capabilities
- **Document Agent / RAG** — chunking, embeddings, hybrid search + reranking, pgvector-backed. Ingests real Google Drive file content (native Docs are exported as text, other files downloaded directly) — fixed this pass; it previously fell back to fabricated placeholder text on any fetch failure instead of surfacing a real error.
- **Database Agent (Text-to-SQL)** — `sqlglot` AST validation, read-only enforcement, safe fallback on validation failure.
- **Meeting Agent** — extracts summary/decisions/risks/unresolved-questions/action-items from a pasted or exported transcript. There is no live Google Meet transcript-export API for third-party apps, so this is paste/upload-only by design, not a missing feature. Proven resistant to prompt injection both architecturally and by test.
- **Calendar** — real Google Calendar event list/create/update/free-busy via OAuth. Creating an event can request a genuine Google Meet conference link (`conferenceData`) rather than a fabricated URL.
- **WorkGraph (Projects & Tasks)** — full CRUD, with AI-created and human-created tasks sharing one table, distinguished only by `created_by`/`source_type`.
- **Connector layer (Gmail/Drive)** — OAuth2 (PKCE), Gmail read/send, Drive read, Fernet-encrypted token storage.
- **Automations + events** — Celery workers/beat schedule Drive sync, embedding generation, meeting processing, and condition-triggered automations; a Redis-stream event bus is instrumented at 8 real lifecycle points and degrades to a no-op (not a crash) when Redis is unreachable.

### Human approval
Any capability marked `requires_human_approval` (e.g. `gmail.send`) cannot execute without a matching, unexpired, unconsumed `Approval` row, claimed atomically. This is enforced in the executor itself, not just in the UI, and is covered end-to-end by tests (draft → reject/approve → execute, replay protection, edited-payload precedence).

### Security
- `app/core/trust_boundary.py` — a formal boundary between system/user/tool-result/retrieved content.
- `tests/security/` — prompt injection corpus, an approval-bypass sweep over every side-effecting capability, an RBAC matrix, and IDOR/SSRF checks.
- OAuth tokens encrypted at rest (Fernet); passwords hashed with argon2 (legacy bcrypt hashes upgrade transparently on next login).

### Evaluation / research infrastructure
A real evaluation harness (`app/evaluation/`) does baseline comparison (always-local / always-cloud / static-rule / AMOF), a 7-config ablation study, and paired significance testing (`scipy`) over a template-generated privacy corpus. It reports `None` for anything not measured rather than inventing a number. The frontend's `/research/benchmark` page clearly tags every figure `MEASURED` or `ILLUSTRATIVE` — it does not present prototype estimates as real results.

### Frontend
Next.js 16 / React 19 app shell with ~20 authenticated workspace routes (chat, documents, database, approvals, dashboard, drive, gmail, calendar, meet, projects, tasks, integrations, notifications, settings, supervisor, writer, research, execution, knowledge, communication, jira) plus a marketing/landing site.

---

## Known limitations — read before assuming a feature works end-to-end

These are real gaps, not hidden ones:

| Area | Status |
|---|---|
| **Desktop app** (`apps/desktop`) | **Not implemented.** The directory contains only orphaned build-cache artifacts (a stray `Cargo.lock`, empty `target/`/`node_modules/` folders) — no `package.json`, no `tauri.conf.json`, no `Cargo.toml`, no source files. There is no desktop app to build yet. |
| **Admin dashboard** | Backend API exists (`app/api/admin.py`), but `web/src/app/(workspace)/admin/` is an **empty directory** with no `page.tsx` — the route does not build or render. Confirmed by the production build output, which lists no `/admin` route. |
| **`/communication` page** | Static seed/mock inbox data (`SEED_EMAILS`), not wired to Gmail. The separate `/gmail` page is the real, connector-backed one. |
| **`/jira` page** | An honest "coming soon" placeholder. No backend Jira connector exists. |
| **`/knowledge` page** | Renders a static, hardcoded architecture diagram (React Flow with fixed nodes), not a live knowledge graph over your data. |
| **ATGO execution** | Produces a correct multi-node DAG but executes it sequentially, not in parallel. |
| **CDRP replanning** | Targets the last step in the plan as a proxy for "the step responsible for low confidence" — correct for single-step plans, an approximation for genuine multi-node ones. |
| **Privacy classifier** | 4 tiers exist, but the `RESTRICTED` tier is deterministic-rules-only; the embedding/LLM-judge stages still distinguish only the original 3 tiers. |
| **Observability** | Structured `logging` throughout; no Langfuse tracing or Prometheus metrics wired up. |
| **CI/CD** | No GitHub Actions workflows for this project. |
| **RBAC** | The `Role` model and checks exist; enforcement coverage hasn't been fully audited. |

---

## Tech stack

| Layer | Choice |
|---|---|
| Backend | FastAPI, SQLAlchemy 2.x, Alembic (17 migrations), PostgreSQL + pgvector |
| Auth | JWT (access + refresh, separately-derived secrets) via httpOnly cookies, argon2 password hashing, Google OAuth2/PKCE |
| AI runtime | Ollama (local) + OpenRouter/LiteLLM (cloud), routed per-request by the Execution Router |
| Background jobs | Celery + Redis (worker + beat); app degrades gracefully without Redis |
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS 4, TanStack Query, Axios |
| Testing | Pytest (43 backend test files, 300+ test functions) · Vitest (frontend, 53 tests) |

---

## Prerequisites

- **Node.js** v18+ (v20+ recommended)
- **Python** v3.10+
- **PostgreSQL** with the `pgvector` extension available
- **Git**
- Optional: **Redis** (only needed for Celery automations/events — everything else works without it) and **Ollama** (only needed for local-mode inference)

---

## Setup

### 1. Backend (`backend/core-platform-service`)

```bash
cd backend/core-platform-service
python -m venv .venv
```

Windows: `.\.venv\Scripts\activate` · macOS/Linux: `source .venv/bin/activate`

```bash
pip install -r requirements.txt
cp .env.example .env    # Windows: Copy-Item .env.example .env
```

Generate the two required secrets (the app refuses to start without them):

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"       # SECRET_KEY / JWT_SECRET_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"  # FERNET_KEY
```

Fill in `.env` — at minimum:

```env
DATABASE_URL=postgresql://postgres:password@localhost:5432/core_platform_db
SECRET_KEY=<generated>
JWT_SECRET_KEY=<generated>
FERNET_KEY=<generated>
FRONTEND_URL=http://localhost:3000

GOOGLE_CLIENT_ID=your_google_client_id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your_google_client_secret
# Leave GOOGLE_REDIRECT_URI empty -- see the OAuth section below.

# Only needed for cloud routing / embeddings:
OPENROUTER_API_KEY=your_openrouter_key
```

`.env.example` is generated from `app/core/config.py` — every key it lists is actually read by the app.

Run migrations and seed roles (signup fails without them):

```bash
alembic upgrade head
python -c "from app.db.session import SessionLocal; from app.db.seed import seed_roles; db=SessionLocal(); seed_roles(db); db.close()"
```

Start the API:

```bash
uvicorn app.main:app --reload --port 8001
```

API at `http://127.0.0.1:8001`, interactive docs at `http://127.0.0.1:8001/docs`.

### 2. Frontend (`web`)

```bash
cd web
npm install
cp .env.example .env.local    # Windows: Copy-Item .env.example .env.local
npm run dev
```

App at `http://localhost:3000`. The frontend proxies `/api/v1/*` to the backend (`BACKEND_INTERNAL_URL` in `.env.local`, default `http://127.0.0.1:8001`) — the browser never talks to the API directly, which is what lets the httpOnly session cookie work. Auth configuration (Google client ID/secret, JWT secrets) lives entirely on the backend now; the frontend `.env.local` only needs `APP_URL`, `NEXT_PUBLIC_APP_URL`, and `BACKEND_INTERNAL_URL`.

### 3. Google OAuth setup

1. In [Google Cloud Console](https://console.cloud.google.com/), create/select a project and enable the **Gmail API**, **Google Drive API**, and **Google Calendar API**.
2. Configure the OAuth consent screen.
3. Create an **OAuth client ID** (type: Web application) with:
   - **Authorized JavaScript origin**: `http://localhost:3000`
   - **Authorized redirect URI**: `http://localhost:3000/api/v1/auth/google/callback`

     (This goes through the frontend's `/api/v1/*` proxy to the backend's real handler — the backend is no longer registered directly with Google. Only add a second redirect URI, `http://localhost:8001/api/v1/connectors/google/oauth/callback`, if you explicitly set `GOOGLE_REDIRECT_URI` in `.env` to opt into the separate connect flow — leave it unset otherwise.)
4. Copy the Client ID and Secret into the backend `.env` (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`).

---

## Running the tests

Backend (from `backend/core-platform-service`, with the venv active):

```bash
pytest                    # full suite
pytest tests/test_rag.py  # a single file
pytest tests/security/    # the security suite specifically
```

A couple of tests skip themselves (with a stated reason) when Redis or Ollama isn't reachable, rather than silently passing against a disabled dependency.

Frontend (from `web`):

```bash
npm run test         # Vitest suite
npm run typecheck    # tsc --noEmit
npm run build        # production build, generates all routes
```

---

## API reference

Base path: `/api/v1`

| Prefix | Covers |
|---|---|
| `/auth` | Signup/login/refresh, Google sign-in |
| `/connectors/google` | Google account connect/status, Gmail, Drive |
| `/calendar` | Google Calendar events, availability |
| `/meetings` | Transcript extraction, action-item → task creation |
| `/workgraph` | Projects, tasks |
| `/rag` | Document ingest, search, grounded answer |
| `/db-agent` | Text-to-SQL |
| `/supervisor` | AMOF plan/execute |
| `/execution-manager` | Direct capability execution |
| `/runtime` | Local/cloud routing decisions |
| `/approvals` | Approval queue, approve/reject/execute |
| `/automations` | Automation CRUD |
| `/documents`, `/writer`, `/notifications`, `/workspace`, `/users`, `/audit-log`, `/evaluation`, `/observability`, `/admin` | Supporting APIs |

Full interactive reference: `http://127.0.0.1:8001/docs`.

---

## Project structure

```
multi-agent-ai-workspace/
├── backend/
│   └── core-platform-service/     # FastAPI backend
│       ├── app/                   # api/, services/, models/, supervisor/, agents/, connectors/, execution/, rag/, evaluation/, core/
│       ├── alembic/versions/      # 17 migrations
│       ├── tests/                 # 43 test files (incl. tests/security/)
│       ├── requirements.txt
│       └── .env.example
├── web/                            # Next.js frontend
│   ├── src/app/(workspace)/       # ~20 authenticated routes
│   ├── src/services/, hooks/, types/
│   ├── package.json
│   └── .env.example
├── apps/desktop/                   # Not implemented (see Known limitations)
├── docs/                           # PRD, architecture notes, phase-by-phase implementation history
└── docker-compose.yml              # backend + redis + celery worker/beat + frontend
```
