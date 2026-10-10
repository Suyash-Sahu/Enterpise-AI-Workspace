import os


class ServiceURLs:

    CORE = os.getenv(
        "CORE_SERVICE_URL",
        "",
    )

    CONNECTOR = os.getenv(
        "CONNECTOR_SERVICE_URL",
        "",
    )

    RETRIEVAL = os.getenv(
        "RETRIEVAL_SERVICE_URL",
        "",
    )

    DATABASE_AGENT = os.getenv(
        "DATABASE_AGENT_SERVICE_URL",
        "",
    )

    EXECUTION = os.getenv(
        "EXECUTION_MANAGER_URL",
        "",
    )

    RUNTIME = os.getenv(
        "RUNTIME_SERVICE_URL",
        "",
    )

    ORCHESTRATION = os.getenv(
        "ORCHESTRATION_SERVICE_URL",
        "",
    )