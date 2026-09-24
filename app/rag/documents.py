from pathlib import Path


RUNBOOK_DIR = Path("data/runbooks")


def load_documents() -> list[dict]:
    documents = []

    for file_path in RUNBOOK_DIR.glob("*.md"):
        documents.append(
            {
                "id": file_path.stem,
                "source": str(file_path),
                "text": file_path.read_text(encoding="utf-8"),
                "metadata": {
                    "type": "runbook",
                    "service": file_path.stem.split("-high-errors")[0],
                },
            }
        )

    return documents