# Backend Phase Plan — Enterprise AI Workspace (AMOF)

This breaks the PRD's backend into **12 standalone backend projects**. Build and test each one in isolation (own repo, own DB/tests, own README), then wire it into the main frontend one at a time. Order below is dependency-driven — each phase only needs what came before it.

---

## How to Use This Doc

- Each phase = one deployable service you can build, run, and hit with Postman/curl **before** touching the frontend.
- Each phase lists: what it is, why it exists, tech stack, core modules, the API surface it must expose, and the exact integration point where your frontend will plug in.
- Don't jump ahead — Phase 4 (RAG) is much easier once Phase 2 (Connectors) already gives you real documents to embed, and Phase 7 (Orchestration) is meaningless until Phases 2–6 exist as callable services.

---

## Phase Overview

| Phase | Project Name | Core Job | Depends On |
|---|---|---|---|
| 1 | Core Platform Service | Auth, users, base Postgres schema | — |
| 2 | Connector Service | Gmail + Drive OAuth, read/send | 1 |
| 3 | Retrieval Service (RAG) | Chunk, embed, hybrid search | 1, 2 |
| 4 | Database Agent (Text-to-SQL) | NL → SQL on sample enterprise DB | 1 |
| 5 | AI Execution Manager | Local vs cloud routing decision | 1 |
| 6 | Model Runtime Layer | Ollama (local) + LiteLLM (cloud) gateway | 5 |
| 7 | AMOF Orchestration Service | Supervisor + multi-agent graph | 2, 3, 4, 5, 6 |
| 8 | Approval / Human-in-the-Loop | Draft → approve → execute (Gmail send etc.) | 2, 7 |
| 9 | Caching Layer | Semantic cache, Redis | 3, 7 |
| 10 | Observability & Eval | Tracing, metrics, regression detection | 7 |
| 11 | Admin/Metrics Backend | Routing/cost dashboards, feature flags | 5, 9, 10 |
| 12 | Background Workers | Drive sync, embedding jobs, scheduled evals | 2, 3, 10 |

---

## Phase 1 — Core Platform Service

**What it is:** The foundation every other service sits on — user accounts, sessions/JWT, base Postgres schema, and the audit log table.

**Why first:** Nothing else can be tested standalone without a user identity and a database to write to.

**Stack:** FastAPI, PostgreSQL, SQLAlchemy + Alembic migrations, JWT (or session cookies), Redis (optional at this stage just for session cache).

**Core modules:**
- `models.py` — `User`, `Session`, `AuditLog`, `Role` tables
- `routes_auth.py` — signup/login, token refresh, logout
- `session.py` — DB session management
- RBAC scaffolding (roles: `user`, `admin`)

**API surface:**
- `POST /auth/signup`, `POST /auth/login`, `POST /auth/refresh`
- `GET /users/me`
- `POST /audit-log` (internal, called by other services)

**Frontend integration point:** Login/signup pages, the JWT this issues is what every later service will validate.

---

## Phase 2 — Connector Service (Gmail + Google Drive)

**What it is:** A dedicated OAuth2 + API adapter service that owns all Gmail/Drive access. This is the PRD's "Connector Layer" — build it as its own microservice so Slack/Jira can be added later without touching agents.

**Why second:** Every downstream feature (RAG, orchestration, approvals) needs real documents/emails to work against. Build this early so you're not testing on mock data for the rest of the project.

**Stack:** FastAPI, `google-api-python-client`, OAuth2 (`google-auth-oauthlib`), Postgres (encrypted token storage — use `cryptography`/Fernet or a KMS), Redis (rate-limit counters).

**Core modules:**
- `gmail_client.py` — `list_threads`, `get_message`, `send_message` (gated behind approval upstream)
- `gdrive_client.py` — `list_files`, `get_file`, `export_google_doc`
- `base_connector.py` — shared interface so future connectors (Slack, Jira) implement the same contract
- Token refresh + encrypted storage
- Scope enforcement: `drive.readonly`, `gmail.readonly`, `gmail.send` only — no `modify`/delete

**API surface:**
- `GET /connectors/google/oauth/start` / `/callback`
- `GET /drive/files`, `GET /drive/files/{id}`
- `GET /gmail/threads`, `GET /gmail/threads/{id}`
- `POST /gmail/send` (internal-only, called after approval — never public-facing without an approval token)

**Frontend integration point:** "Connect Google Account" button in onboarding, Integrations settings page, Documents page (lists synced Drive files).

**Test it standalone by:** connecting a real test Google account, listing Drive files, reading a thread, and sending one test email — before any agent exists.

---

## Phase 3 — Retrieval Service (RAG)

**What it is:** Chunking, embedding, and hybrid (vector + keyword) search over documents pulled from Phase 2.

**Why third:** Needs Phase 2 to have real content to chunk; needs Phase 1 for user-scoped storage.

**Stack:** FastAPI, `pgvector` (Postgres extension), an embedding model (OpenAI/local via Ollama), a reranker (e.g., cross-encoder), BM25 or Postgres full-text for the keyword half.

**Core modules:**
- `chunking.py` — document → chunks, tagged with `source`, `file_id`, `owner`, `last_modified`
- `embeddings.py` — embedding generation + storage
- `hybrid_search.py` — vector + keyword fusion
- `reranker.py` — final relevance re-ordering

**API surface:**
- `POST /rag/ingest` (given a Drive file ID from Phase 2, chunk+embed it)
- `POST /rag/search` → `{query, top_k}` → ranked chunks with citations

**Frontend integration point:** The "sources" panel (right sidebar) that shows which Drive files/Gmail threads backed an answer.

**Test it standalone by:** ingesting a handful of real test Drive docs and confirming search returns correct, correctly-scoped chunks.

---

## Phase 4 — Database Agent (Text-to-SQL)

**What it is:** Converts natural language into validated SQL against a sample enterprise database (per PRD, seeded via `seed_sample_db.py`).

**Why now:** Independent of Gmail/Drive — can be built and tested in parallel with Phase 3 once Phase 1 exists.

**Stack:** FastAPI, `sqlglot` (SQL validation/guardrails), any LLM for NL→SQL, PostgreSQL (sample sales/revenue schema).

**Core modules:**
- `nl_to_sql.py` — prompt → SQL generation
- `sql_guardrails.py` — parses generated SQL with `sqlglot`, blocks write statements, restricts to allow-listed tables/columns

**API surface:**
- `POST /db-agent/query` → `{question}` → `{sql, rows, explanation}`

**Frontend integration point:** Chat timeline step "DB Agent" with an expandable SQL/JSON view (monospace `JetBrains Mono` block per your design system).

**Test it standalone by:** running 10–15 sample business questions against the seeded DB and checking the generated SQL never touches disallowed tables.

---

## Phase 5 — AI Execution Manager

**What it is:** The routing brain — decides, per task, whether execution happens locally (Ollama) or in the cloud (LiteLLM), based on privacy/complexity/cost/latency (P/C/Co/L) factors. This is the PRD's headline research contribution — build it as a clean, independently testable decision service.

**Why now:** Doesn't need Gmail/Drive/RAG to exist yet — it's a pure decision function you can unit-test with synthetic inputs, then plug real signals in later.

**Stack:** FastAPI, a policy engine (Casbin or Oso), a scoring module you can unit test independently of any LLM call.

**Core modules:**
- `scoring.py` — computes P (privacy sensitivity), C (task complexity), Co (cost), L (latency requirement)
- `policy.py` — Casbin/Oso rules (e.g., "confidential-tagged content → local only")
- `router.py` — combines score + policy → `{location, model, reasoning}`

**API surface:**
- `POST /execution-manager/route` → `{task_metadata}` → `{location: "local"|"cloud", model, reasoning}`

**Frontend integration point:** The emerald/blue execution-mode badges shown per agent step.

**Test it standalone by:** feeding it labeled synthetic tasks (a personal email vs. a public doc vs. a confidential folder) and confirming routing matches your "ideal routing" labels — this is also your success metric from PRD §12.

---

## Phase 6 — Model Runtime Layer

**What it is:** The actual execution backends the Execution Manager routes to: a local Ollama interface and a cloud LiteLLM gateway.

**Why now:** Needs Phase 5's routing decision as input, but is otherwise a thin, swappable interface layer — good to isolate so you can add/remove models without touching agent logic.

**Stack:** Ollama (local), LiteLLM (cloud gateway, multi-provider), FastAPI wrapper exposing a single normalized interface.

**Core modules:**
- `local_runtime.py` — calls Ollama, handles quantized model fallback
- `cloud_gateway.py` — LiteLLM call, provider fallback on outage

**API surface:**
- `POST /runtime/generate` → `{prompt, location, model}` → `{completion}` (single normalized contract regardless of where it actually ran)

**Frontend integration point:** None directly — this is purely internal, called by Phase 7's agents.

---

## Phase 7 — AMOF Orchestration Service (Supervisor + Agents)

**What it is:** The multi-agent brain that decomposes a user request, calls Document/DB/Meeting/Writing/Verification/Connector agents, and streams the step-by-step plan back.

**Why now:** This is the integration layer — it can only be built once Phases 2–6 exist as callable services, since each agent is really just a thin wrapper that calls those services and asks the Execution Manager where to run.

**Stack:** FastAPI + WebSocket (for streaming agent steps), LangGraph (supervisor/task graph), Redis (short-term memory/state).

**Core modules:**
- `supervisor.py` — decomposes request into a task graph
- `task_graph.py` — graph execution/state
- `agents/document_agent.py`, `database_agent.py`, `meeting_agent.py`, `writing_agent.py`, `verification_agent.py`, `connector_agent.py` — each calls the relevant Phase 2–6 service, not raw APIs directly
- `memory.py` — conversation/task memory

**API surface:**
- `WS /chat/stream` — streams `{step, agent, execution_mode, output, sources}` events
- `POST /chat/message` — kicks off a new task graph

**Frontend integration point:** The center chat panel's `AgentStepTimeline.tsx` — each event from this WebSocket is one expandable timeline row.

---

## Phase 8 — Approval / Human-in-the-Loop System

**What it is:** Mandatory gate for any side-effecting action (Gmail send, etc.). Verification Agent output → pending-approval record → user approves/edits/rejects → only then does Phase 2's `gmail.send` get called.

**Why now:** Depends on Phase 7 producing drafts and Phase 2 owning the actual send call.

**Stack:** FastAPI, Postgres (`approvals` table with status: pending/approved/edited/rejected), WebSocket or polling for the pending-queue badge count.

**Core modules:**
- `routes_approvals.py` — list pending, approve, edit, reject
- Enforced invariant: Phase 2's `gmail.send` endpoint refuses calls without a valid `approval_id` in `approved` state

**API surface:**
- `GET /approvals/pending`
- `POST /approvals/{id}/approve` | `/edit` | `/reject`

**Frontend integration point:** `ApprovalModal.tsx`, the Approvals sidebar item with badge count.

**Test it standalone by:** confirming Phase 2's send endpoint hard-rejects any request lacking an approved approval record — this is your PRD success metric "100% of Gmail-send actions logged with explicit human approval."

---

## Phase 9 — Caching Layer

**What it is:** Redis-backed general cache + a semantic cache (GPTCache-style) that recognizes near-duplicate queries and skips redundant LLM calls.

**Why now:** Bolt onto Phases 3 & 7 once they're stable — caching an unstable interface just hides bugs.

**Stack:** Redis, GPTCache (or a hand-rolled embedding-similarity cache).

**Core modules:**
- `semantic_cache.py` — embed query, check similarity threshold against cached queries, return cached result or pass through

**API surface:** No new public endpoints — this wraps Phase 3 (search) and Phase 7 (generation) calls transparently.

**Frontend integration point:** None directly; shows up as lower latency, and optionally a "cached" indicator in the step timeline.

---

## Phase 10 — Observability & Eval

**What it is:** Tracing (Langfuse), metrics (Prometheus), an eval pipeline (promptfoo) run against a hand-built eval set, and a regression detector that flags quality drops — including per execution-mode (local vs cloud) as called out in PRD §12.

**Why now:** Needs Phase 7 running real traffic to trace against.

**Stack:** Langfuse, Prometheus (+ Grafana if you want dashboards), promptfoo.

**Core modules:**
- `tracing.py` — Langfuse spans per agent step
- `metrics.py` — Prometheus counters/histograms (latency, cost, routing split)
- `log_miner.py` — pulls real conversation logs into eval candidates
- `eval_runner.py`, `regression_detector.py`

**API surface:**
- `GET /metrics` (Prometheus scrape endpoint)
- `POST /eval/run` (trigger eval pipeline)

**Frontend integration point:** Feeds the Admin Dashboard (Phase 11) — not directly user-facing otherwise.

---

## Phase 11 — Admin/Metrics Backend

**What it is:** Aggregation layer over Phase 5 (routing decisions), Phase 9 (cache hit rates), and Phase 10 (eval/regression results) into the `/admin` dashboard data.

**Why last among the "support" phases:** It's pure aggregation — nothing to show until the services it reads from are producing real data.

**Stack:** FastAPI, reads from Postgres/Prometheus, a feature-flag store (Postgres table or a lightweight flag service).

**Core modules:**
- `routes_admin.py` — routing split over time, cost tracking, drift alerts, feature-flag CRUD

**API surface:**
- `GET /admin/routing-stats`, `GET /admin/cost`, `GET /admin/drift-alerts`
- `GET/POST /admin/feature-flags`

**Frontend integration point:** `RoutingMetricsChart.tsx`, `CostTracker.tsx`, `DriftAlertList.tsx` on the `/admin` route.

---

## Phase 12 — Background Workers

**What it is:** Celery workers for anything that shouldn't block a request: Drive re-indexing, embedding generation queued from Phase 3, and scheduled eval runs from Phase 10.

**Why last:** It's infrastructure around already-working services — scheduling jobs against endpoints that don't exist yet just wastes time.

**Stack:** Celery, Redis (broker), Postgres (job status).

**Core modules:**
- Scheduled Drive sync job (respecting the PRD's open question — full periodic vs. on-demand sync)
- Embedding generation queue consumer
- Scheduled eval/regression runs

**API surface:** None public — internal job queue, status exposed via Phase 11's admin routes.

**Frontend integration point:** Indirect — sync status indicator on the Documents page.

---

## Suggested Build Order

```
1 → 2 → 3
        ↘
1 → 4     → 7 → 8
1 → 5 → 6 ↗     ↓
              9, 10 → 11
        2, 3, 10 → 12
```

Build 1 → 2 → (3 and 4 in parallel) → 5 → 6 → 7 → 8, then treat 9/10/11/12 as a polish layer you can add incrementally without breaking anything already integrated.

## Integration Strategy

For each phase, before touching the frontend:
1. Run the service standalone with its own `.env`, DB, and test script.
2. Hit every endpoint with curl/Postman and confirm the exact response shape you'll need.
3. Only then wire the corresponding frontend page/component (noted per phase above) to call it — one phase, one integration PR, one working demo checkpoint. This keeps you able to demo "phase N works end-to-end" at every step rather than a single big-bang integration at the end.