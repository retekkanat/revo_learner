"""Helpers that read evidence records for the daily checks. They never print a record's content."""

from __future__ import annotations

import json
import re
from pathlib import Path

# Twelve digits that stand alone, as an account number does; digits joined to letters,
# underscores or hyphens belong to a request identifier or a digest.
ACCOUNT_NUMBER = re.compile(r"(?<![\w-])\d{12}(?![\w-])")
ACCESS_KEY_ID = re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")


def read_json(folder: Path, name: str):
    path = folder / name
    assert path.is_file(), f"{name} is missing from {folder}; run the cell that writes it"
    return json.loads(path.read_text(encoding="utf-8"))


def read_lines(path: Path) -> list[dict]:
    assert path.is_file(), f"{path.name} is missing; run the cells that write it"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def work_folder(evidence: Path) -> Path:
    """The evidence folder is `work/evidence/<initials>/`, so `work/` is two levels up."""
    return evidence.parents[1]


def secrets_in(folder: Path) -> list[str]:
    """Return the files that hold an account number or an access key identifier."""
    found = []
    for path in sorted(folder.rglob("*")):
        if path.is_file() and path.suffix in {".json", ".jsonl", ".md", ".txt"}:
            text = path.read_text(encoding="utf-8", errors="replace")
            if ACCOUNT_NUMBER.search(text) or ACCESS_KEY_ID.search(text):
                found.append(path.name)
    return found
