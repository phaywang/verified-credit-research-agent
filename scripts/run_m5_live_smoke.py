#!/usr/bin/env python3
"""Run live SEC companyfacts smoke checks for M5.

This script intentionally calls SEC's live APIs. It is not part of the default
unit test suite because sandbox and CI environments may block sec.gov.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from credit_research_agent.universal_analyzer import UniversalCreditAnalyzer


DEFAULT_CASES = [
    ("AAPL", "leverage_analysis", [2023, 2024]),
    ("TSLA", "leverage_analysis", [2023, 2024]),
    ("NVDA", "leverage_analysis", [2024, 2025]),
]


def parse_case(raw: str) -> tuple[str, str, List[int]]:
    """Parse CASE as TICKER:THEME:YEAR,YEAR."""
    try:
        ticker, theme, years_raw = raw.split(":", 2)
        years = [int(part.strip()) for part in years_raw.split(",") if part.strip()]
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "case must be formatted as TICKER:THEME:YEAR,YEAR"
        ) from exc

    if not ticker or not theme or not years:
        raise argparse.ArgumentTypeError(
            "case must include ticker, theme, and at least one year"
        )
    return ticker.upper(), theme, years


def summarize_result(ticker: str, theme: str, years: List[int], result) -> Dict[str, Any]:
    metric_counts = {str(year): len(metrics) for year, metrics in result.metrics.items()}
    concepts = sorted(
        {
            metric.xbrl_concept
            for metrics in result.metrics.values()
            for metric in metrics
            if metric.xbrl_concept
        }
    )
    return {
        "ticker": ticker,
        "theme": theme,
        "years": years,
        "status": result.status,
        "company": result.company,
        "error": result.error,
        "metric_counts": metric_counts,
        "total_metrics": sum(metric_counts.values()),
        "has_verified_changes": "## Verified Changes" in result.brief,
        "concepts": concepts,
        "trace_steps": [step.get("step") for step in result.trace],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--case",
        action="append",
        type=parse_case,
        help="Live smoke case formatted as TICKER:THEME:YEAR,YEAR.",
    )
    parser.add_argument(
        "--min-metrics",
        type=int,
        default=4,
        help="Minimum metric count required per case.",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        help="Optional path to write the smoke summary JSON.",
    )
    args = parser.parse_args()

    cases = args.case or DEFAULT_CASES
    analyzer = UniversalCreditAnalyzer()
    summaries = []
    failures = []

    for ticker, theme, years in cases:
        result = analyzer.analyze(ticker, theme, years)
        summary = summarize_result(ticker, theme, years, result)
        summaries.append(summary)

        if result.status != "success":
            failures.append(f"{ticker}: status={result.status} error={result.error}")
        if summary["total_metrics"] < args.min_metrics:
            failures.append(
                f"{ticker}: expected at least {args.min_metrics} metrics, "
                f"got {summary['total_metrics']}"
            )
        if not summary["has_verified_changes"]:
            failures.append(f"{ticker}: generated brief lacks Verified Changes section")

    output = {
        "status": "fail" if failures else "pass",
        "case_count": len(summaries),
        "failures": failures,
        "summaries": summaries,
    }

    print(json.dumps(output, indent=2, sort_keys=True))

    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(json.dumps(output, indent=2, sort_keys=True), encoding="utf-8")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
