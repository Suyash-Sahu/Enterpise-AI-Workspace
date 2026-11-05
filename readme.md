# Enterprise AI Workspace — AMOF

An enterprise-grade, privacy-first AI workspace powered by **AMOF** (Adaptive Multi-agent Orchestration Framework). It unifies company documents, databases, Gmail, Google Drive, and Google Calendar into a cohesive operational intelligence platform.

AMOF breaks complex multi-step user intents into validated task graphs (DAGs), dispatches sub-tasks to specialized domain agents, routes inferences between **local models (Ollama)** and **cloud providers (OpenRouter/LiteLLM)** according to strict privacy policies, and gates every side-effecting operation (e.g., sending emails, creating tasks) behind human approval.

---

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Core Capabilities & Workspace Features](#core-capabilities--workspace-features)
   - [Commitment Intelligence Center V2 vs. Morning Brief](#commitment-intelligence-center-v2-vs-morning-brief)
   - [AMOF Orchestration & Task Decomposition](#amof-orchestration--task-decomposition)
   - [Privacy Classifier & Model Routing](#privacy-classifier--model-routing)
   - [Human-in-the-Loop Approvals](#human-in-the-loop-approvals)
   - [Domain Agents (Document RAG, Text-to-SQL, Meetings, WorkGraph)](#domain-agents)
3. [Prerequisites & Software Installation](#prerequisites--software-installation)
4. [Step-by-Step Setup from Scratch](#step-by-step-setup-from-scratch)
   - [Option A: Manual Local Setup (Recommended for Development)](#option-a-manual-local-setup-recommended-for-development)
     - [1. Clone Repository](#1-clone-repository)
     - [2. Database Setup (PostgreSQL + pgvector or SQLite Fallback)](#2-database-setup-postgresql--pgvector-or-sqlite-fallback)
     - [3. Backend Configuration & Setup](#3-backend-configuration--setup)
     - [4. Local AI Setup with Ollama (100% Free & Private)](#4-local-ai-setup-with-ollama-100-free--private)
     - [5. Frontend Setup (Next.js)](#5-frontend-setup-nextjs)
   - [Option B: Docker Compose Setup (One-Click)](#option-b-docker-compose-setup-one-click)
5. [Configuring Google Integrations (Gmail, Drive, Calendar)](#configuring-google-integrations-gmail-drive-calendar)
6. [Running the Application](#running-the-application)
7. [Testing & Quality Verification](#testing--quality-verification)
8. [API Reference](#api-reference)
9. [Project Directory Structure](#project-directory-structure)
10. [Troubleshooting & FAQ](#troubleshooting--faq)

---

## System Architecture

```mermaid
flowchart TD
    User([User / Browser]) <-->|http://localhost:3000| NextUI[Next.js 16 / React 19 Frontend]
    NextUI <-->|Internal Proxy /api/v1/*| FastAPIServer[FastAPI Backend :8001]

    subgraph Backend Core
        FastAPIServer --> Auth[Auth & Session Engine\nhttpOnly Cookies + JWT]
        FastAPIServer --> PrivacyRouter[Privacy Classifier & Router]
        FastAPIServer --> AMOF[AMOF Supervisor\nPlanner & Decomposer]
        FastAPIServer --> ExecutionManager[Execution Manager & Capability Registry]
        FastAPIServer --> CommitmentEngine[Commitment Intelligence V2\nRun Tracker & Lifecycle Engine]
    end

    subgraph Execution & Agents
        ExecutionManager --> DocAgent[Document / RAG Agent]
        ExecutionManager --> DBAgent[Database Agent / Text-to-SQL]
        ExecutionManager --> MeetAgent[Meeting Transcript Agent]
        ExecutionManager --> InboxAgent[Inbox / Gmail Agent]
        ExecutionManager --> WorkGraphAgent[WorkGraph Projects & Tasks]
    end

    subgraph Storage & Infrastructure
        FastAPIServer <--> Postgres[(PostgreSQL 15+ & pgvector)]
        FastAPIServer <-.-> Redis[(Redis Event Bus & Celery Cache)]
        FastAPIServer <--> GoogleAPI[Google Cloud APIs\nGmail, Calendar, Drive]
    end

    subgraph Inference Runtimes
        PrivacyRouter -->|Confidential / Local| Ollama[Local Ollama :11434\nqwen2.5 / nomic-embed-text]
        PrivacyRouter -->|Public / Cloud| OpenRouter[Cloud Inference\nOpenRouter / LiteLLM]
    end
```

---

## Core Capabilities & Workspace Features

### Commitment Intelligence Center V2 vs. Morning Brief

The workspace provides two distinct, non-overlapping tools for daily workflows:

| Route | Role | Core Question Answered | Primary Experience |
|---|---|---|---|
| **`/brief`** (Executive Morning Brief) | Daily overview & situational awareness | *"What needs my attention today?"* | Daily executive briefing: high-level summary, unread email triage highlights, upcoming calendar agenda, active tasks due today, and at-risk commitments. |
| **`/commitments`** (Commitment Intelligence Center) | Dedicated operational console | *"Which promises have been made, who owns them, are they fulfilled, and what action is needed?"* | Enterprise lifecycle management: discovery across Gmail and meeting notes, micro-batch AI extraction, persistent background runs, bidirectional ownership (`owed_by_me`, `owed_to_me`, `mutual`), evidence-based completion verification, smart follow-up drafting, and delivery analytics. |

#### Highlights of Commitment Intelligence V2:
1. **Durable Background Scans & AI Sweeps**: Long-running scans execute as persistent database runs (`CommitmentRun` & `CommitmentRunStage`). The UI displays real-time progress percentages, stage milestones, errors, and cancellation controls that survive browser refreshes.
2. **Bidirectional Ownership**: Explicit separation of `responsible_party` from `counterparty`, preventing misattribution.
3. **Timezone-Aware Deadline Intelligence**: Converts natural-language dates (*"by Friday"*, *"next Monday"*, *"in 2 days"*) into normalized UTC timestamps while flagging ambiguities.
4. **Evidence-Based Verification**: Prevents premature completion. Commitments require verifiable evidence (linked task completion, sent follow-ups, or explicit user sign-off).
5. **Smart Follow-Up Assistant**: Drafts context-aware reminder emails with 1-click clipboard copy; never sends emails without explicit human approval.
6. **Task Proposals to AI Inbox**: Eligible commitments can be proposed as WorkGraph tasks, routed through human-in-the-loop review.

### AMOF Orchestration & Task Decomposition
- **Intent → Plan → Execute → Verify → Replan Loop**: Decomposes multi-step prompts into a directed acyclic graph (DAG) of capability steps.
- **Confidence-Driven Replanning (CDRP)**: Verifiers evaluate step results. If confidence falls below the target band, AMOF replans and adapts execution.
- **Fail-Closed Capability Registry**: Every action declares its risk level (`low`, `medium`, `high`), side-effect classification (`read_only`, `reversible_write`, `destructive`, `external_communication`), and whether it requires human approval.

### Privacy Classifier & Model Routing
A three-stage cascade classifies every prompt into one of four tiers:
- **`PUBLIC`**: Safe for external cloud models (OpenRouter/LiteLLM).
- **`INTERNAL`**: Standard company operational data.
- **`CONFIDENTIAL`**: Must execute on local hardware (Ollama) with zero external leakage.
- **`RESTRICTED`**: Highly sensitive credentials, PII, keys; strictly restricted to local execution.

### Human-in-the-Loop Approvals
Any action with external communication or irreversible side-effects (e.g. `gmail.send`) creates an `Approval` record. The executor will refuse to run without an active, unexpired, user-approved token.

### Domain Agents
- **Document Agent (RAG)**: Ingests documents, extracts text from Google Drive files, creates embeddings with `nomic-embed-text` or `text-embedding-3-small`, and performs hybrid vector + BM25 keyword search using `pgvector`.
- **Database Agent**: Translates natural language into SQL queries, using `sqlglot` for Abstract Syntax Tree (AST) inspection to enforce read-only safety.
- **Meeting Agent**: Ingests meeting notes and transcripts to extract summaries, key decisions, and action items with 1-click task conversion.
- **WorkGraph**: Unified project and task tracking supporting dependencies, subtasks, and progress metrics.

---

## Prerequisites & Software Installation

If you are setting this up on a fresh machine with **nothing installed**, install the following core tools:

### 1. Git
- **Windows**: Download from [git-scm.com](https://git-scm.com/download/win) or run `winget install --id Git.Git -e --source winget`
- **macOS**: Run `xcode-select --install` or `brew install git`
- **Linux (Ubuntu/Debian)**: `sudo apt update && sudo apt install -y git`

### 2. Node.js (v20+ LTS recommended)
- **Windows**: Download LTS from [nodejs.org](https://nodejs.org/) or run `winget install OpenJS.NodeJS.LTS`
- **macOS**: `brew install node@20`
- **Linux**: Use [NodeSource](https://github.com/nodesource/distributions) or `sudo apt install -y nodejs npm`

### 3. Python (v3.11 to v3.13)
- **Windows**: Download from [python.org](https://www.python.org/downloads/) (check the box **"Add python.exe to PATH"** during installation) or run `winget install Python.Python.3.13`
- **macOS**: `brew install python@3.13`
- **Linux**: `sudo apt install -y python3 python3-pip python3-venv`

### 4. Database: PostgreSQL with pgvector (Or SQLite Fallback)
Choose one of the following:
- **Option 1 (Easiest — Docker for Postgres + pgvector)**:
  Install Docker Desktop ([docker.com](https://www.docker.com/products/docker-desktop/)) and run:
  ```bash
  docker run -d --name enterprise-pg -p 5432:5432 -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=core_platform_db pgvector/pgvector:pg16
  ```
- **Option 2 (Native PostgreSQL)**:
  Install PostgreSQL 15 or 16 from [postgresql.org](https://www.postgresql.org/download/). Install the `pgvector` extension from [github.com/pgvector/pgvector](https://github.com/pgvector/pgvector).
- **Option 3 (Zero-Install Development Fallback — SQLite)**:
  If you do not want to install PostgreSQL immediately, set `ALLOW_SQLITE_FALLBACK=true` in your backend `.env`. The backend will automatically create and use a local SQLite database for development!

### 5. Ollama (For Free Offline Local AI)
- Download and install Ollama from [ollama.com](https://ollama.com/).
- Once installed, open your terminal and pull the default models:
  ```bash
  ollama pull qwen2.5:3b-instruct
  ollama pull nomic-embed-text
  ```

---

## Step-by-Step Setup from Scratch

### Option A: Manual Local Setup (Recommended for Development)

#### 1. Clone Repository
```bash
git clone https://github.com/your-username/multi-agent-ai-workspace.git
cd multi-agent-ai-workspace
```

---

#### 2. Database Setup (PostgreSQL + pgvector or SQLite Fallback)

If using native PostgreSQL, create the database:
```sql
CREATE DATABASE core_platform_db;
\c core_platform_db
CREATE EXTENSION IF NOT EXISTS vector;
```

*(If using SQLite fallback, simply ensure `ALLOW_SQLITE_FALLBACK=true` in `.env` as shown below).*

---

#### 3. Backend Configuration & Setup

1. **Navigate to the backend directory**:
   ```bash
   cd backend/core-platform-service
   ```

2. **Create and activate a virtual environment**:
   - **Windows (PowerShell)**:
     ```powershell
     python -m venv .venv
     .\.venv\Scripts\Activate.ps1
     ```
   - **macOS / Linux**:
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```

3. **Install Python dependencies**:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. **Create the environment file**:
   - **Windows**: `Copy-Item .env.example .env`
   - **macOS / Linux**: `cp .env.example .env`

5. **Generate required cryptographic secrets**:
   The application requires secure keys for JWT session signing and token encryption at rest. Run these commands:
   ```bash
   # Generate SECRET_KEY
   python -c "import secrets; print(secrets.token_urlsafe(48))"

   # Generate FERNET_KEY
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

6. **Configure your `.env`**:
   Open `backend/core-platform-service/.env` and update:
   ```ini
   ENVIRONMENT=development
   
   # Database (PostgreSQL)
   DATABASE_URL=postgresql://postgres:postgres@localhost:5432/core_platform_db
   
   # Or enable SQLite fallback if you don't have Postgres running yet:
   ALLOW_SQLITE_FALLBACK=true

   # Paste the keys generated in step 5:
   SECRET_KEY=your_generated_secret_key_here
   FERNET_KEY=your_generated_fernet_key_here

   FRONTEND_URL=http://localhost:3000

   # Local Ollama AI settings
   OLLAMA_BASE_URL=http://localhost:11434
   OLLAMA_DEFAULT_MODEL=qwen2.5:3b-instruct

   # Embeddings
   EMBEDDING_PROVIDER=ollama
   EMBEDDING_MODEL=nomic-embed-text
   EMBEDDING_DIM=768

   # Optional Cloud AI (leave blank if running purely local):
   OPENROUTER_API_KEY=
   ```

7. **Run Database Migrations & Seed Default Roles**:
   ```bash
   alembic upgrade head
   python seed.py
   ```

8. **Start the FastAPI Backend Server**:
   ```bash
   uvicorn app.main:app --reload --port 8001
   ```
   - **Backend API**: [http://127.0.0.1:8001](http://127.0.0.1:8001)
   - **Interactive API Documentation (Swagger)**: [http://127.0.0.1:8001/docs](http://127.0.0.1:8001/docs)

---

#### 4. Local AI Setup with Ollama (100% Free & Private)

Ollama runs open-weight LLMs locally on your GPU/CPU:
1. Verify Ollama is running:
   ```bash
   curl http://localhost:11434/api/tags
   ```
2. Download the models used by the agents:
   ```bash
   ollama pull qwen2.5:3b-instruct
   ollama pull nomic-embed-text
   ```

---

#### 5. Frontend Setup (Next.js)

1. **Open a new terminal window** and navigate to the `web` folder:
   ```bash
   cd web
   ```

2. **Install Node dependencies**:
   ```bash
   npm install
   ```

3. **Configure Frontend Environment**:
   - **Windows**: `Copy-Item .env.example .env.local`
   - **macOS / Linux**: `cp .env.example .env.local`

   Your `web/.env.local` should contain:
   ```ini
   APP_URL=http://localhost:3000
   NEXT_PUBLIC_APP_URL=http://localhost:3000
   BACKEND_INTERNAL_URL=http://127.0.0.1:8001
   ```
   > **Note on Architecture**: The Next.js app acts as a server-side proxy for `/api/v1/*` requests to the backend (`BACKEND_INTERNAL_URL`). This architecture guarantees that `httpOnly`, `SameSite=lax` session cookies function reliably without CORS or cross-origin restrictions.

4. **Start the Next.js Development Server**:
   ```bash
   npm run dev
   ```

5. **Open your browser**:
   Navigate to [http://localhost:3000](http://localhost:3000)

---

### Option B: Docker Compose Setup (One-Click)

If you have Docker Desktop installed, you can spin up the full stack (PostgreSQL, Redis, Celery Worker, Celery Beat, FastAPI Backend, and Next.js Frontend) in one command:

1. Copy environment variables:
   ```bash
   cp backend/core-platform-service/.env.example backend/core-platform-service/.env
   cp web/.env.example web/.env.local
   ```
2. Generate your `SECRET_KEY` and `FERNET_KEY` and set them in `backend/core-platform-service/.env`.
3. Start all services:
   ```bash
   docker compose up --build
   ```
4. Access the web workspace at [http://localhost:3000](http://localhost:3000).

---

## Configuring Google Integrations (Gmail, Drive, Calendar)

To enable live Google integrations (reading unread emails, inspecting drive documents, viewing calendar meetings, and syncing commitments):

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project (e.g. `Enterprise AI Workspace`).
3. Navigate to **APIs & Services > Library** and enable:
   - **Gmail API**
   - **Google Drive API**
   - **Google Calendar API**
4. Configure the **OAuth Consent Screen**:
   - User Type: **External** (or Internal if using Google Workspace).
   - Add test user email addresses (e.g. your personal Gmail address).
   - Add required scopes: `email`, `profile`, `openid`, `https://www.googleapis.com/auth/gmail.readonly`, `https://www.googleapis.com/auth/gmail.send`, `https://www.googleapis.com/auth/drive.readonly`, `https://www.googleapis.com/auth/calendar`.
5. Navigate to **Credentials > Create Credentials > OAuth client ID**:
   - Application Type: **Web application**
   - **Authorized JavaScript origins**:
     `http://localhost:3000`
   - **Authorized redirect URIs**:
     `http://localhost:3000/api/v1/auth/google/callback`
6. Copy your **Client ID** and **Client Secret** into `backend/core-platform-service/.env`:
   ```ini
   GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=your-client-secret
   ```
7. Restart the backend. You can now sign in with Google or connect accounts under **Settings > Integrations**.

---

## Running the Application

For normal local development, run two terminal processes:

| Component | Directory | Command | URL |
|---|---|---|---|
| **FastAPI Backend** | `backend/core-platform-service` | `uvicorn app.main:app --reload --port 8001` | [http://127.0.0.1:8001](http://127.0.0.1:8001) |
| **Next.js Frontend** | `web` | `npm run dev` | [http://localhost:3000](http://localhost:3000) |
| *(Optional)* **Ollama Server** | Anywhere | `ollama serve` | [http://localhost:11434](http://localhost:11434) |
| *(Optional)* **Celery Worker** | `backend/core-platform-service` | `celery -A app.workers.celery_app worker --loglevel=info` | Background worker |

---

## Testing & Quality Verification

Run the test suites to ensure full system integrity:

### Backend Tests (Pytest)
From `backend/core-platform-service` with the virtual environment active:
```bash
# Run all backend tests
pytest

# Run the Commitment Intelligence V2 suite
pytest tests/test_commitment_intelligence_v2.py -v

# Run the full commitment verification suite
pytest tests/test_commitment_scan.py tests/test_commitment_service.py tests/test_commitment_sweep.py -v

# Run the security & trust boundary suite
pytest tests/security/
```

### Frontend Tests & Type Checking (Vitest & TypeScript)
From the `web` folder:
```bash
# Run unit tests (59 test cases)
npm run test

# Run strict TypeScript type checking (zero errors)
npm run typecheck

# Run production build
npm run build
```

---

## API Reference

The backend provides versioned REST endpoints mounted under `/api/v1`:

| Endpoint Prefix | Description |
|---|---|
| `/api/v1/auth` | User signup, password login, Google OAuth login/callback, session refresh & logout. |
| `/api/v1/commitments` | **Commitment Intelligence V2**: CRUD, persistent execution runs (`/runs`), stage tracking, completion verification, follow-up generation, and analytics. |
| `/api/v1/workgraph` | Projects, tasks, subtask dependencies, and timeline management. |
| `/api/v1/workgraph-ai` | AI Task proposal generation and AI Inbox reviews. |
| `/api/v1/supervisor` | AMOF supervisor planning, DAG generation, step-by-step execution, and replanning (CDRP). |
| `/api/v1/approvals` | Human-in-the-loop approval queue for high-risk and external actions. |
| `/api/v1/rag` | Document ingestion, chunking, pgvector embedding, and hybrid question answering. |
| `/api/v1/db-agent` | Natural language text-to-SQL with read-only AST safety validation. |
| `/api/v1/meetings` | Meeting transcript parsing, key decision identification, and action-item extraction. |
| `/api/v1/calendar` | Google Calendar integration: event listing, scheduling with Google Meet links. |
| `/api/v1/connectors/google` | OAuth token lifecycle, Gmail reading/sending, and Google Drive syncing. |
| `/api/v1/runtime` | Model runtime gateway (Ollama vs OpenRouter policy decisions). |
| `/api/v1/automations` | Background and condition-triggered automations. |

Interactive OpenAPI documentation is available live at [http://127.0.0.1:8001/docs](http://127.0.0.1:8001/docs).

---

## Project Directory Structure

```
multi-agent-ai-workspace/
├── backend/
│   └── core-platform-service/
│       ├── app/
│       │   ├── agents/             # Inbox, Database, Document, Meeting, Calendar agents
│       │   ├── api/                # FastAPI routers (/commitments, /auth, /supervisor, etc.)
│       │   ├── connectors/         # Google OAuth, Gmail, Drive, Calendar connectors
│       │   ├── core/               # App config, security headers, rate limiting, trust boundary
│       │   ├── db/                 # Database session, base model, role seeds
│       │   ├── evaluation/         # Ablation studies, benchmarking harness
│       │   ├── execution/          # Capability contracts, execution manager
│       │   ├── models/             # SQLAlchemy ORM models (Commitment, User, Task, Run, etc.)
│       │   ├── privacy/            # Sensitivity classifier (Regex, Exemplars, LLM Judge)
│       │   ├── rag/                # Embeddings, chunking, pgvector search
│       │   ├── runtime/            # Ollama local runtime, OpenRouter cloud runtime, policy
│       │   ├── schemas/            # Pydantic request/response validation schemas
│       │   ├── services/           # Business logic (CommitmentService, RunService, etc.)
│       │   ├── supervisor/         # AMOF Supervisor planner & executor
│       │   └── workers/            # Celery worker & beat configuration
│       ├── alembic/versions/       # Database migrations
│       ├── tests/                  # Pytest test suites (unit, integration, security)
│       ├── requirements.txt        # Python package dependencies
│       └── .env.example            # Backend environment template
│
├── web/
│   ├── src/
│   │   ├── app/
│   │   │   ├── (auth)/login/       # Authentication pages
│   │   │   └── (workspace)/        # Authenticated workspace routes:
│   │   │       ├── brief/          # Daily Executive Morning Brief
│   │   │       ├── commitments/    # Commitment Intelligence Center V2
│   │   │       ├── chat/           # Conversational AMOF Interface
│   │   │       ├── documents/      # Document Knowledge Base & RAG
│   │   │       ├── database/       # Text-to-SQL DB Agent
│   │   │       ├── meet/           # Meeting Transcript Extractor
│   │   │       ├── projects/       # WorkGraph Projects
│   │   │       ├── tasks/          # WorkGraph Tasks
│   │   │       ├── work/           # AI Inbox (Human Approvals)
│   │   │       ├── calendar/       # Google Calendar
│   │   │       ├── drive/          # Google Drive Explorer
│   │   │       └── settings/       # Workspace settings & Integrations
│   │   ├── components/
│   │   │   ├── commitments/        # Commitment Center UI components (Table, Drawer, Stats, etc.)
│   │   │   ├── brief/              # Executive Morning Brief components
│   │   │   ├── shared/             # Reusable UI primitives
│   │   │   └── ui/                 # Buttons, Dialogs, Sheets, Badges (Tailwind / Radix)
│   │   ├── hooks/                  # React Query custom hooks
│   │   ├── services/               # Axios API client services
│   │   └── types/                  # TypeScript data contracts & DTOs
│   ├── package.json                # Frontend package dependencies
│   └── .env.example                # Frontend environment template
│
├── docker-compose.yml              # Complete container orchestration
└── README.md                       # Master project documentation
```

---

## Troubleshooting & FAQ

### 1. `SECRET_KEY must be set to at least 32 characters`
- **Cause**: The application enforces cryptographic entropy on startup to prevent token forgery.
- **Solution**: Run `python -c "import secrets; print(secrets.token_urlsafe(48))"` and paste the result into `SECRET_KEY` in `backend/core-platform-service/.env`.

### 2. Database Connection Error (`psycopg2.OperationalError`)
- **Cause**: PostgreSQL is not running or the database `core_platform_db` hasn't been created yet.
- **Solution**:
  - If using Docker: Ensure the PostgreSQL container is running: `docker ps`.
  - If using native Postgres: Run `createdb -U postgres core_platform_db`.
  - Quick fix: Set `ALLOW_SQLITE_FALLBACK=true` in `backend/core-platform-service/.env` to develop immediately using SQLite.

### 3. Missing `pgvector` Extension
- **Cause**: Your PostgreSQL installation lacks the vector extension.
- **Solution**: Run `CREATE EXTENSION vector;` in PostgreSQL. If installing pgvector natively is inconvenient, run PostgreSQL via the official docker image: `docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=postgres pgvector/pgvector:pg16`.

### 4. User Looks Permanently Signed Out / Cookie Not Sent
- **Cause**: Accessing the backend directly on port 8001 from your browser instead of through the Next.js frontend proxy on port 3000.
- **Solution**: Always navigate to `http://localhost:3000`. The Next.js frontend proxies `/api/v1/*` to `http://127.0.0.1:8001`, which allows the secure `httpOnly` cookie to attach properly.

### 5. Ollama Request Timeout / Model Not Found
- **Cause**: Ollama is not running or the required model hasn't been pulled.
- **Solution**:
  - Run `ollama serve` in a terminal.
  - Pull the model: `ollama pull qwen2.5:3b-instruct` and `ollama pull nomic-embed-text`.
  - You can increase the timeout in `.env` using `RUNTIME_TIMEOUT=60`.

### 6. Google Sign-In `Error 400: redirect_uri_mismatch`
- **Cause**: The redirect URI in Google Cloud Console does not match the exact address requested.
- **Solution**: In Google Cloud Console under your OAuth Web Client Credentials, ensure the **Authorized redirect URI** is set exactly to:
  `http://localhost:3000/api/v1/auth/google/callback`

---

## License

This project is licensed under the Apache 2.0 License.
