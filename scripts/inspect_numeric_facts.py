"""Inspect M2a numeric facts for reviewer validation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from credit_research_agent.verification.fact_extractor import (  # noqa: E402
    extract_numeric_facts,
    load_chunks,
)
from credit_research_agent.schemas import write_json  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--chunks",
        default="data/processed/ford_2023_2025_chunks.jsonl",
    )
    parser.add_argument(
        "--raw-root",
        default="data/raw/sec/ford",
    )
    parser.add_argument(
        "--output",
        default="runs/ford_debt_liquidity_2023_2025/numeric_facts.json",
    )
    args = parser.parse_args()

    chunks = load_chunks(Path(args.chunks))
    facts = extract_numeric_facts(chunks, Path(args.raw_root), years=(2023, 2025))
    data = [fact.to_jsonable() for fact in facts]
    write_json(Path(args.output), data)

    print(json.dumps(data, indent=2, sort_keys=True))
    print(f"\nWrote {len(data)} facts to {args.output}")


if __name__ == "__main__":
    main()
