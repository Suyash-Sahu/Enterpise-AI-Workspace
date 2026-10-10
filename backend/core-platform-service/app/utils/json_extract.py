import json


def extract_json(text: str) -> dict | None:
    """
    Best-effort extraction of a JSON object from an LLM completion that may
    wrap it in prose or markdown fences. Returns None (never raises) on
    anything that doesn't clearly parse, so callers can fall back safely.

    Shared by app/supervisor/decomposer.py (ATGO) and
    app/agents/meeting_agent.py (Phase 7) -- previously duplicated as
    decomposer.py's private `_extract_json`.
    """
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None
