import hashlib
import logging
import os
from pathlib import Path

from cryptography.fernet import Fernet
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent

logger = logging.getLogger(__name__)

# Minimum entropy we accept for a JWT signing secret.
MIN_SECRET_KEY_LENGTH = 32


class Settings(BaseSettings):
    # Application & Host Settings
    PROJECT_NAME: str = "Enterprise AI Workspace — Shared Backend"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    PORT: int = 8001
    HOST: str = "127.0.0.1"

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")

    # Development escape hatch only. When the configured database is
    # unreachable the app fails to start unless this is explicitly enabled.
    ALLOW_SQLITE_FALLBACK: bool = (
        os.getenv("ALLOW_SQLITE_FALLBACK", "false").lower() == "true"
    )

    # Environment
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

    # Security & Tokens
    # No default: an unset SECRET_KEY must fail startup, never silently sign
    # tokens with an empty string.
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

    @field_validator("SECRET_KEY")
    @classmethod
    def _validate_secret_key(cls, value: str) -> str:
        if len(value) < MIN_SECRET_KEY_LENGTH:
            raise ValueError(
                "SECRET_KEY must be set to at least "
                f"{MIN_SECRET_KEY_LENGTH} characters. Generate one with: "
                "python -c \"import secrets; print(secrets.token_urlsafe(48))\""
            )
        return value

    @property
    def REFRESH_SECRET_KEY(self) -> str:
        """
        Refresh tokens are signed with a key derived from SECRET_KEY rather than
        SECRET_KEY itself, so an access token can never validate as a refresh
        token (or vice versa) even if the type claim check were bypassed.
        """
        return hashlib.sha256(
            b"refresh-token-v1:" + self.SECRET_KEY.encode()
        ).hexdigest()

    # Session cookies
    #
    # The backend is the only thing that issues or clears a session. Cookies
    # are httpOnly (script cannot read them) and Secure outside development.
    #
    # SameSite is "lax", not "strict", and that distinction is load-bearing.
    # Google sign-in ends with Google redirecting the browser back here; that
    # navigation is *cross-site initiated*, and a Strict cookie is withheld
    # from every request in such a redirect chain. The cookie would be stored
    # correctly and then not sent on the hop to /dashboard, so the route guard
    # saw no session and bounced the user back to /login — a sign-in that
    # silently failed at the last step.
    #
    # Lax still withholds the cookie from cross-site POSTs, iframes and
    # subresource requests, so CSRF protection for the API is unchanged: it is
    # sent only on top-level GET navigations. Every API call this app makes is
    # same-origin anyway, because Next proxies /api/v1/* to this service.
    ACCESS_COOKIE_NAME: str = os.getenv("ACCESS_COOKIE_NAME", "amof_access")
    REFRESH_COOKIE_NAME: str = os.getenv("REFRESH_COOKIE_NAME", "amof_refresh")
    COOKIE_SAMESITE: str = os.getenv("COOKIE_SAMESITE", "lax")
    COOKIE_DOMAIN: str = os.getenv("COOKIE_DOMAIN", "")

    @field_validator("COOKIE_SAMESITE")
    @classmethod
    def _validate_cookie_samesite(cls, value: str) -> str:
        normalized = (value or "lax").strip().lower()

        if normalized not in ("lax", "strict", "none"):
            raise ValueError(
                "COOKIE_SAMESITE must be one of: lax, strict, none "
                f"(got {value!r})."
            )

        if normalized == "strict":
            # Not fatal — someone may run without Google sign-in — but this is
            # the exact setting that breaks the OAuth return leg, so say so
            # rather than let it fail as a mysterious redirect loop.
            logger.warning(
                "COOKIE_SAMESITE=strict will break Google sign-in: the browser "
                "withholds Strict cookies on the cross-site redirect back from "
                "Google, so the session is set but never sent. Use 'lax'."
            )

        return normalized

    # Connectors
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")

    # Where Google sends the browser back after a sign-in. It must be an
    # address the *browser* can reach, which is the Next origin, because that
    # is what proxies /api/v1/* to this service.
    GOOGLE_SIGNIN_REDIRECT_URI: str = os.getenv("GOOGLE_SIGNIN_REDIRECT_URI", "")

    # Extra browser origins allowed to call this API, comma-separated.
    # FRONTEND_URL is always included and does not need repeating here.
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "")

    # Rate limiting. Storage is in-process unless a redis:// URI is given,
    # which is required once more than one worker is running.
    RATE_LIMIT_ENABLED: bool = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
    RATE_LIMIT_STORAGE_URI: str = os.getenv("RATE_LIMIT_STORAGE_URI", "")
    RATE_LIMIT_DEFAULT: str = os.getenv("RATE_LIMIT_DEFAULT", "300/minute")
    # Credential-guessing surfaces get a much tighter budget.
    RATE_LIMIT_LOGIN: str = os.getenv("RATE_LIMIT_LOGIN", "5/minute")
    RATE_LIMIT_SIGNUP: str = os.getenv("RATE_LIMIT_SIGNUP", "3/minute")
    RATE_LIMIT_REFRESH: str = os.getenv("RATE_LIMIT_REFRESH", "20/minute")
    # Endpoints that spend money or call a third party.
    RATE_LIMIT_EXPENSIVE: str = os.getenv("RATE_LIMIT_EXPENSIVE", "20/minute")

    @property
    def google_signin_redirect_uri(self) -> str:
        if self.GOOGLE_SIGNIN_REDIRECT_URI:
            return self.GOOGLE_SIGNIN_REDIRECT_URI
        return f"{self.FRONTEND_URL.rstrip('/')}{self.API_V1_STR}/auth/google/callback"

    @property
    def google_connector_redirect_uri(self) -> str:
        """
        Callback for the Gmail/Drive connector consent flow.

        Defaults to the Next origin rather than this service's own port: the
        browser is what follows the redirect, and pointing it at the backend
        port meant a second, easily-forgotten redirect URI had to be
        registered with Google. Anything unregistered is refused up front
        with `Error 400: redirect_uri_mismatch`.
        """
        if self.GOOGLE_REDIRECT_URI:
            return self.GOOGLE_REDIRECT_URI
        return (
            f"{self.FRONTEND_URL.rstrip('/')}"
            f"{self.API_V1_STR}/connectors/google/oauth/callback"
        )

    @property
    def google_connect_authorization_redirect_uri(self) -> str:
        """
        Redirect URI the Gmail/Drive consent request actually sends.

        Defaults to the sign-in callback, which keeps the number of redirect
        URIs that must be registered with Google at one. Setting
        GOOGLE_REDIRECT_URI opts back into the dedicated connector callback,
        which then has to be registered too.
        """
        if self.GOOGLE_REDIRECT_URI:
            return self.google_connector_redirect_uri
        return self.google_signin_redirect_uri

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() in ("production", "prod")

    @property
    def cookie_secure(self) -> bool:
        """
        Secure is mandatory in production. It is off in development because
        the dev server is plain http and a Secure cookie would never be sent,
        which would look exactly like a broken login.
        """
        override = os.getenv("COOKIE_SECURE", "")
        if override:
            return override.lower() == "true"
        return self.is_production

    @property
    def cors_origins(self) -> list[str]:
        origins = [self.FRONTEND_URL.rstrip("/")]
        origins += [
            origin.strip().rstrip("/")
            for origin in self.CORS_ORIGINS.split(",")
            if origin.strip()
        ]
        # Preserve order, drop duplicates and empties.
        return list(dict.fromkeys(o for o in origins if o))

    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    # Where Google sends the browser back after connecting Gmail/Drive.
    # Empty means "derive it from FRONTEND_URL", which keeps it on the same
    # origin as the sign-in callback so only one redirect URI family has to
    # be registered in the Google Cloud console. Set it explicitly only to
    # override that.
    GOOGLE_REDIRECT_URI: str = os.getenv("GOOGLE_REDIRECT_URI", "")

    # Cryptography
    # No default. This key encrypts stored Google access and refresh tokens,
    # and the previous fallback was a literal committed to source *and*
    # published in .env.example, which made encryption at rest decorative.
    FERNET_KEY: str = os.getenv("FERNET_KEY", "")
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")

    @field_validator("FERNET_KEY")
    @classmethod
    def _validate_fernet_key(cls, value: str) -> str:
        if not value:
            raise ValueError(
                "FERNET_KEY must be set. Generate one with: python -c "
                '"from cryptography.fernet import Fernet; '
                'print(Fernet.generate_key().decode())"'
            )

        try:
            Fernet(value.encode())
        except Exception as exc:
            raise ValueError(
                "FERNET_KEY is not a valid Fernet key (expected 32 "
                f"url-safe base64-encoded bytes): {exc}"
            ) from exc

        return value

    # AI Models
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_MODEL: str = os.getenv("OPENROUTER_MODEL", "google/gemma-4-26b-a4b-it:free")
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
    # qwen2.5:7b (4.7GB) left near-zero VRAM headroom on this machine's 4GB
    # RTX 2050 -- confirmed via Ollama's own server.log GPU-discovery-watchdog
    # timeouts under concurrent desktop GPU/RAM load (see implementation
    # plan.md, 2026-09-13). qwen2.5:3b-instruct (1.9GB, Q4_K_M) leaves several
    # hundred MB to ~1.5GB+ of real spare VRAM instead.
    # Stage D re-selection (2026-09-22): qwen2.5:3b-instruct is faster (49 tok/s,
    # 100% GPU) but measurably cannot do the Stage D work -- on this machine it
    # extracted 0 of 2 commitments from a test email and emitted a serial chain
    # for an objective that requires a 3-way parallel fan-out. qwen3:4b-instruct
    # handled both correctly at 24 tok/s / 67% GPU. Throughput is worthless if
    # the plan is wrong, so the slower model wins for orchestration work.
    # MUST be paired with OLLAMA_NUM_CTX below: at Ollama's default 32k context
    # this model reserves 8.0GB and runs 70% on CPU; at 4096 it is 3.5GB / 67% GPU.
    OLLAMA_DEFAULT_MODEL: str = os.getenv("OLLAMA_DEFAULT_MODEL", "qwen3:4b-instruct")
    # Context window for local generation. Not a quality knob -- a VRAM knob.
    # The dev machine has a 4GB RTX 2050; see the measurements above.
    OLLAMA_NUM_CTX: int = int(os.getenv("OLLAMA_NUM_CTX", "4096"))
    # Development switch (Stage D): when false, the router is offered no cloud
    # candidates at all, so every request resolves local. This does NOT change
    # the privacy router's logic, remove the local/cloud architecture, or relax
    # any constraint -- it only empties the cloud half of the candidate set.
    # Flip to true (and set OPENROUTER_API_KEY) to restore hybrid execution.
    RUNTIME_CLOUD_ENABLED: bool = os.getenv("RUNTIME_CLOUD_ENABLED", "false").lower() in ("1", "true", "yes")

    # Project 3 RAG Settings
    EMBEDDING_PROVIDER: str = os.getenv("EMBEDDING_PROVIDER", "openai")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    EMBEDDING_DIM: int = int(os.getenv("EMBEDDING_DIM", "1536"))
    RAG_CHUNK_SIZE: int = int(os.getenv("RAG_CHUNK_SIZE", "500"))
    RAG_CHUNK_OVERLAP: int = int(os.getenv("RAG_CHUNK_OVERLAP", "100"))
    RAG_TOP_K: int = int(os.getenv("RAG_TOP_K", "5"))
    RRF_K: int = int(os.getenv("RRF_K", "60"))

    # Cache (app/cache). These were referenced throughout the cache module but
    # never declared here, so importing anything from app.cache raised
    # AttributeError at module scope and three test files could not even be
    # collected. Cache is off by default: it needs a reachable Redis.
    CACHE_ENABLED: bool = os.getenv("CACHE_ENABLED", "false").lower() == "true"
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    CACHE_NAMESPACE: str = os.getenv("CACHE_NAMESPACE", "amof")
    CACHE_SCHEMA_VERSION: str = os.getenv("CACHE_SCHEMA_VERSION", "v1")
    CACHE_DEFAULT_TTL_SECONDS: int = int(os.getenv("CACHE_DEFAULT_TTL_SECONDS", "300"))
    CACHE_RAG_TTL_SECONDS: int = int(os.getenv("CACHE_RAG_TTL_SECONDS", "900"))
    CACHE_GENERATION_TTL_SECONDS: int = int(os.getenv("CACHE_GENERATION_TTL_SECONDS", "600"))
    CACHE_MAX_RESULT_SIZE: int = int(os.getenv("CACHE_MAX_RESULT_SIZE", "1048576"))
    CACHE_SEMANTIC_ENABLED: bool = os.getenv("CACHE_SEMANTIC_ENABLED", "false").lower() == "true"
    CACHE_SEMANTIC_THRESHOLD: float = float(os.getenv("CACHE_SEMANTIC_THRESHOLD", "0.92"))

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_JSON: bool = os.getenv("LOG_JSON", "false").lower() == "true"

    # Project 4 Database Agent Settings
    DB_AGENT_ENABLED: bool = True
    DB_AGENT_RAW_SQL_ENABLED: bool = False
    DB_AGENT_DEFAULT_LIMIT: int = 20
    DB_AGENT_MAX_LIMIT: int = 100
    DB_AGENT_QUERY_TIMEOUT: float = 5.0
    DB_AGENT_MAX_SCHEMA_TABLES: int = 20

    # Project 5 AI Execution Manager Settings
    EXECUTION_MANAGER_ENABLED: bool = True
    EXECUTION_DEFAULT_TIMEOUT: float = 30.0
    EXECUTION_MAX_TIMEOUT: float = 120.0
    EXECUTION_MAX_RETRIES: int = 2
    EXECUTION_DEFAULT_MODE: str = "auto"
    EXECUTION_HISTORY_LIMIT: int = 50

    # AMOF Work (PRD v3) AI layer. Safety limits are settings, not hard-coded rules.
    # LLM enrichment is opt-in; every agent works deterministically without it.
    WORK_AI_LLM_ENABLED: bool = False
    WORK_AI_LLM_TIMEOUT: float = 20.0
    WORK_AUTOMATION_MAX_ITEMS_PER_RUN: int = 25   # blast radius: affected items per automation run
    WORK_AUTOMATION_MAX_RUNS_PER_HOUR: int = 10   # per automation rule
    WORK_RISK_STALE_DAYS: int = 7

    # Project 6 Model Runtime Gateway Settings
    RUNTIME_ENABLED: bool = True
    RUNTIME_DEFAULT_MODE: str = "auto"
    RUNTIME_DEFAULT_MODEL: str = "qwen2.5:7b"
    RUNTIME_TIMEOUT: float = 60.0
    RUNTIME_MAX_TIMEOUT: float = 120.0
    RUNTIME_MAX_TOKENS: int = 4096
    LITELLM_BASE_URL: str = os.getenv("LITELLM_BASE_URL", "http://127.0.0.1:4000")
    LITELLM_DEFAULT_MODEL: str = os.getenv("LITELLM_DEFAULT_MODEL", "openai/gpt-4o-mini")
    # llama3.2:3b was listed here but never pulled into the local Ollama
    # instance -- every router selection of it failed with HTTP 404 (Phase 10
    # audit, 2026-09-20). qwen2.5:3b-instruct is already pulled and has a
    # comparable small/fast profile; this is a deliberate experimental
    # configuration swap, not a hidden fix -- see PHASE_10.md.
    RUNTIME_ALLOWED_MODELS_LOCAL: list[str] = ["qwen2.5:7b", "qwen2.5:3b-instruct", "qwen3:4b-instruct"]
    RUNTIME_ALLOWED_MODELS_CLOUD: list[str] = ["openai/gpt-4o-mini", "google/gemma-4-26b-a4b-it:free"]

    # Cost/latency/quality profile per model, consumed by the privacy-constrained
    # router. These are the router's only view of its options.
    #
    # Local models are NOT priced at zero. The figures below amortise hardware
    # and energy over expected throughput; pricing local at zero makes the
    # router trivially prefer local and turns any reported "cost saving" into a
    # tautology. Retune per deployment: they are calibration knobs, not
    # measurements, and cloud list prices change without notice.
    RUNTIME_MODEL_PROFILES_LOCAL: dict[str, dict[str, float]] = {
        "qwen2.5:7b": {
            "cost_per_1k_input": 0.00008,
            "cost_per_1k_output": 0.00008,
            "est_latency_ms": 4200.0,
            "quality": 0.72,
        },
        "qwen2.5:3b-instruct": {
            "cost_per_1k_input": 0.00004,
            "cost_per_1k_output": 0.00004,
            "est_latency_ms": 2100.0,
            "quality": 0.58,
        },
        # est_latency_ms is MEASURED on this machine (2026-09-22): 6.9-11.2s
        # wall for short structured-output prompts at num_ctx=4096, 24 tok/s.
        # quality is a calibration knob like every other entry in this table,
        # NOT a measurement -- it is set above qwen2.5:3b-instruct because that
        # model failed both Stage D probe tasks this one passed, and it stays
        # provisional until Phase 38 measures it properly.
        "qwen3:4b-instruct": {
            "cost_per_1k_input": 0.00006,
            "cost_per_1k_output": 0.00006,
            "est_latency_ms": 7000.0,
            "quality": 0.68,
        },
    }
    RUNTIME_MODEL_PROFILES_CLOUD: dict[str, dict[str, float]] = {
        "openai/gpt-4o-mini": {
            "cost_per_1k_input": 0.00015,
            "cost_per_1k_output": 0.0006,
            "est_latency_ms": 1300.0,
            "quality": 0.86,
        },
        "google/gemma-4-26b-a4b-it:free": {
            "cost_per_1k_input": 0.0,
            "cost_per_1k_output": 0.0,
            "est_latency_ms": 1900.0,
            "quality": 0.68,
        },
    }

    # --- Privacy classifier ---
    # Per-stage confidence thresholds. A stage that does not clear its own
    # threshold abstains and the cascade falls through; if every stage
    # abstains the result is CONFIDENTIAL (fail-closed).
    # Set below the weakest detector weight (0.6). The detectors are built for
    # precision, so a fired detector should be believed; a higher threshold
    # here made the INTERNAL tier unreachable, because every INTERNAL detector
    # (weight 0.6-0.7) fell through and was escalated to CONFIDENTIAL by the
    # fail-closed default. Raising this does not make the system safer, it just
    # collapses three tiers into one.
    PRIVACY_RULE_CONFIDENCE: float = float(os.getenv("PRIVACY_RULE_CONFIDENCE", "0.60"))
    PRIVACY_KNN_CONFIDENCE: float = float(os.getenv("PRIVACY_KNN_CONFIDENCE", "0.70"))
    # Absolute cosine floor below which the nearest exemplar is treated as too
    # unlike the query to judge from. This is EMBEDDING-MODEL-SPECIFIC and must
    # be recalibrated whenever EMBEDDING_MODEL changes: absolute cosine
    # magnitudes are not comparable across models. Measured on the current model,
    # correctly-classified short queries land around 0.40-0.60 at rank 1, so a
    # floor of 0.55 rejected most of them while the class share was still a
    # confident 0.83. Calibrate with:
    #     python -m app.evaluation.privacy_metrics --sweep
    PRIVACY_KNN_MIN_SIMILARITY: float = float(os.getenv("PRIVACY_KNN_MIN_SIMILARITY", "0.35"))
    # Softmax temperature for the stage-2 k-NN vote. Lower values sharpen
    # toward nearest-neighbour-takes-all; higher values approach a linear
    # similarity-weighted vote. Calibrate with the --sweep tool whenever the
    # embedding model or the exemplar set changes.
    PRIVACY_KNN_TEMPERATURE: float = float(os.getenv("PRIVACY_KNN_TEMPERATURE", "0.10"))
    PRIVACY_JUDGE_CONFIDENCE: float = float(os.getenv("PRIVACY_JUDGE_CONFIDENCE", "0.70"))
    PRIVACY_LLM_JUDGE_ENABLED: bool = os.getenv("PRIVACY_LLM_JUDGE_ENABLED", "true").lower() == "true"
    # Empty string means "use the default local model".
    PRIVACY_JUDGE_MODEL: str = os.getenv("PRIVACY_JUDGE_MODEL", "")
    PRIVACY_JUDGE_TIMEOUT: float = float(os.getenv("PRIVACY_JUDGE_TIMEOUT", "15.0"))
    PRIVACY_MAX_SCAN_CHARS: int = int(os.getenv("PRIVACY_MAX_SCAN_CHARS", "20000"))

    # --- Answer quality judge (evaluation harness only) ---
    # Same local-only policy as the privacy classifier's stage-3 judge, for the
    # same reason: the content being judged here is a real question + a real
    # generated answer, potentially sensitive, and grading it is not a reason
    # to send it anywhere the router wouldn't otherwise have sent it.
    QUALITY_JUDGE_ENABLED: bool = os.getenv("QUALITY_JUDGE_ENABLED", "true").lower() == "true"
    QUALITY_JUDGE_MODEL: str = os.getenv("QUALITY_JUDGE_MODEL", "")
    QUALITY_JUDGE_TIMEOUT: float = float(os.getenv("QUALITY_JUDGE_TIMEOUT", "20.0"))
    QUALITY_JUDGE_MAX_CONTEXT_CHARS: int = int(
        os.getenv("QUALITY_JUDGE_MAX_CONTEXT_CHARS", "4000")
    )

    # --- Privacy constraint (the hard constraint) ---
    # The most sensitive label still permitted to leave the machine. "public" is
    # the strict default; an organisation that accepts internal data on a
    # vendor API under contract can raise this to "internal". Setting it to
    # "confidential" disables the constraint entirely and should only ever be
    # used to produce the unconstrained baseline for comparison.
    PRIVACY_MAX_CLOUD_LABEL: str = os.getenv("PRIVACY_MAX_CLOUD_LABEL", "public")
    # Minimum classifier confidence required before content may leave the
    # machine. A low-confidence "public" guess is not a basis for disclosure.
    PRIVACY_CLOUD_CONFIDENCE: float = float(os.getenv("PRIVACY_CLOUD_CONFIDENCE", "0.75"))

    # --- Router soft constraints ---
    ROUTER_LATENCY_BUDGET_MS: float = float(os.getenv("ROUTER_LATENCY_BUDGET_MS", "8000"))
    ROUTER_QUALITY_FLOOR: float = float(os.getenv("ROUTER_QUALITY_FLOOR", "0.55"))
    ROUTER_DEFAULT_OUTPUT_TOKENS: int = int(os.getenv("ROUTER_DEFAULT_OUTPUT_TOKENS", "512"))
    # Labelled exemplars backing classifier stage 2, relative to the service root.
    # v2 (Week 2): template + Faker-generated, split by template with zero
    # leakage -- see evaluation/datasets/privacy_labeling_rubric.md. v1's 51
    # hand-written items are kept on disk for diff/history but are no longer
    # what the classifier loads.
    PRIVACY_EXEMPLAR_PATH: str = os.getenv(
        "PRIVACY_EXEMPLAR_PATH", "evaluation/datasets/privacy_exemplars_v2.jsonl"
    )

    # Project 7 AMOF Supervisor & CDRP Settings
    SUPERVISOR_ENABLED: bool = True
    SUPERVISOR_DEFAULT_TIMEOUT: float = 60.0
    SUPERVISOR_MAX_TIMEOUT: float = 120.0
    SUPERVISOR_MAX_STEPS: int = 5
    SUPERVISOR_INTENT_CONFIDENCE_THRESHOLD: float = 0.70
    SUPERVISOR_SYNTHESIS_ENABLED: bool = True
    SUPERVISOR_HISTORY_LIMIT: int = 50
    CDRP_MAX_REPLANS: int = 2

    # Phase 27 & 28: Parallel execution & Decomposer settings
    SUPERVISOR_MAX_PARALLEL_STEPS: int = int(os.getenv("SUPERVISOR_MAX_PARALLEL_STEPS", "3"))
    SUPERVISOR_PARALLEL_ENABLED: bool = os.getenv("SUPERVISOR_PARALLEL_ENABLED", "true").lower() == "true"
    LOCAL_RUNTIME_MAX_CONCURRENCY: int = int(os.getenv("LOCAL_RUNTIME_MAX_CONCURRENCY", "1"))
    DECOMPOSER_MODE: str = os.getenv("DECOMPOSER_MODE", "coverage")
    # Phase 29: per-step verification mode.
    #   "off"        - skip all per-step verification (also skips final-answer verifier).
    #   "final_only" - run only the whole-answer ResponseVerifier (current default behavior).
    #   "per_step"   - run a type-specific verifier after each step AND the final verifier.
    VERIFICATION_MODE: str = os.getenv("VERIFICATION_MODE", "per_step")

    # Phase 24: Run Blackboard (shared working memory) caps.
    # A per-run cap, not global -- one run cannot exhaust another's budget.
    # Exceeding either raises (see app/supervisor/blackboard.py); the run
    # fails loudly rather than silently truncating an agent's view of state.
    BLACKBOARD_MAX_ENTRIES: int = 256
    BLACKBOARD_MAX_BYTES: int = 1_000_000

    # Project 8 Approval / HITL Settings
    APPROVALS_ENABLED: bool = True
    APPROVAL_DEFAULT_TTL_MINUTES: int = 60
    APPROVAL_MAX_TTL_MINUTES: int = 1440
    APPROVAL_AUTO_EXPIRE_ENABLED: bool = True

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()