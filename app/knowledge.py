from pathlib import Path


KNOWLEDGE_FILE = Path("data/knowledge.md")


def load_knowledge() -> str:
    if not KNOWLEDGE_FILE.exists():
        return ""

    return KNOWLEDGE_FILE.read_text(
        encoding="utf-8"
    )





