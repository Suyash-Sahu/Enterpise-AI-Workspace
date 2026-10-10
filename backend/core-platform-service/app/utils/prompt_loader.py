from pathlib import Path

PROMPT_DIR = (
    Path(__file__).parent.parent
    / "prompts"
)


def load_prompt(
    name: str,
) -> str:

    with open(
        PROMPT_DIR / f"{name}.txt",
        encoding="utf-8",
    ) as f:

        return f.read()