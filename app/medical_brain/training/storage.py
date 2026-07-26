"""Persist and stream generated clinical case banks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

from app.medical_brain.training.generator import generate_case, total_case_capacity
from app.medical_brain.training.types import GeneratedClinicalCase

DEFAULT_BANK_PATH = Path("data/training/clinical_cases.jsonl")
DEFAULT_SAMPLE_PATH = Path("data/training/clinical_cases_sample.jsonl")


def write_cases_jsonl(
    path: Path,
    cases: Iterator[GeneratedClinicalCase],
    *,
    limit: int | None = None,
) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as f:
        for case in cases:
            f.write(json.dumps(case.to_dict(), ensure_ascii=False) + "\n")
            count += 1
            if limit and count >= limit:
                break
    return count


def read_cases_jsonl(path: Path, *, limit: int | None = None) -> Iterator[dict]:
    if not path.exists():
        return iter(())
    def _iter():
        with path.open(encoding="utf-8") as f:
            for i, line in enumerate(f):
                if limit and i >= limit:
                    break
                line = line.strip()
                if line:
                    yield json.loads(line)
    return _iter()


def generate_bank(
    path: Path | None = None,
    *,
    count: int | None = None,
    start_index: int = 0,
) -> tuple[Path, int]:
    """Write case bank to JSONL. Returns (path, count written)."""
    from app.medical_brain.training.generator import generate_cases

    dest = path or DEFAULT_BANK_PATH
    n = count or total_case_capacity()
    written = write_cases_jsonl(dest, generate_cases(n, start_index=start_index), limit=n)
    return dest, written


def bank_metadata() -> dict:
    cap = total_case_capacity()
    return {
        "total_capacity": cap,
        "meets_100k_target": cap >= 100_000,
        "format": "jsonl",
        "default_path": str(DEFAULT_BANK_PATH),
    }
