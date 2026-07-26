#!/usr/bin/env python3
"""Generate clinical case bank — 100,000+ unique cases."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.medical_brain.training.generator import total_case_capacity, verify_capacity
from app.medical_brain.training.seeds.catalog import seed_count
from app.medical_brain.training.storage import bank_metadata, generate_bank


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate world-class clinical case bank")
    parser.add_argument("--count", type=int, default=None, help="Number of cases (default: full capacity)")
    parser.add_argument("--output", type=str, default=None, help="Output JSONL path")
    parser.add_argument("--verify-only", action="store_true", help="Verify capacity without writing")
    args = parser.parse_args()

    cap = total_case_capacity()
    meta = bank_metadata()
    print(f"Case generator capacity: {cap:,} unique cases")
    print(f"Seed count: {seed_count()} ({seed_count() // 23} avg per specialty)")
    print(f"100k target met: {verify_capacity(100_000)}")

    if args.verify_only:
        return 0 if verify_capacity(100_000) else 1

    path = Path(args.output) if args.output else None
    dest, written = generate_bank(path, count=args.count)
    print(f"Written {written:,} cases to {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
