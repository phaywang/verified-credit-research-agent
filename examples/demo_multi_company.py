#!/usr/bin/env python3
"""Demo: Multi-company, multi-theme extensibility.

Shows that the same M3 agent architecture works for:
- Ford debt/liquidity (existing)
- Apple leverage analysis (new)
- Microsoft solvency assessment (new)

All without code changes - only configuration + data.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from credit_research_agent.task_generator import get_generator as get_task_gen
from credit_research_agent.brief_generator import (
    BriefGenerator, VerifiedMetricsSet, MetricResult
)
from credit_research_agent.config_loader import get_loader


def demo_task_generation():
    """Demonstrate dynamic task generation for different companies/themes."""
    print("=" * 80)
    print("DEMO 1: Dynamic Task Generation")
    print("=" * 80)
    print()

    gen = get_task_gen()

    examples = [
        ("ford", "debt_liquidity"),
        ("apple", "leverage_analysis"),
        ("microsoft", "solvency_assessment"),
    ]

    for company_id, theme_id in examples:
        task_spec = gen.generate_task_spec(company_id, theme_id)
        print(f"✓ {task_spec.company} ({task_spec.ticker})")
        print(f"  Theme: {task_spec.risk_theme}")
        print(f"  Question: {task_spec.question[:80]}...")
        print(f"  Years: {task_spec.years}")
        print(f"  Evidence categories: {len(task_spec.required_evidence)}")
        print()


def demo_apple_leverage():
    """Demonstrate Apple leverage analysis brief generation."""
    print("=" * 80)
    print("DEMO 2: Apple Inc. - Leverage Analysis")
    print("=" * 80)
    print()

    # Example: Apple leverage metrics (realistic 2023-2024 comparison)
    apple_metrics = VerifiedMetricsSet(
        company_name="Apple Inc.",
        fiscal_years=[2023, 2024],
        metrics={
            2023: [
                MetricResult(
                    metric_name="total_debt",
                    fiscal_year=2023,
                    value=106.9,
                    unit="USD billions",
                    status="verified",
                    source="XBRL",
                ),
                MetricResult(
                    metric_name="shareholders_equity",
                    fiscal_year=2023,
                    value=63.1,
                    unit="USD billions",
                    status="verified",
                    source="XBRL",
                ),
                MetricResult(
                    metric_name="interest_expense",
                    fiscal_year=2023,
                    value=3.3,
                    unit="USD billions",
                    status="verified",
                    source="XBRL",
                ),
            ],
            2024: [
                MetricResult(
                    metric_name="total_debt",
                    fiscal_year=2024,
                    value=110.5,
                    unit="USD billions",
                    status="verified",
                    source="XBRL",
                ),
                MetricResult(
                    metric_name="shareholders_equity",
                    fiscal_year=2024,
                    value=70.6,
                    unit="USD billions",
                    status="verified",
                    source="XBRL",
                ),
                MetricResult(
                    metric_name="interest_expense",
                    fiscal_year=2024,
                    value=3.5,
                    unit="USD billions",
                    status="verified",
                    source="XBRL",
                ),
            ],
        },
    )

    gen = BriefGenerator()
    brief = gen.generate_brief(
        "Apple Inc.",
        "leverage_analysis",
        apple_metrics,
        evidence_narrative=(
            "Apple's debt strategy reflects investment in capital allocation and "
            "shareholder returns while maintaining investment-grade credit quality. "
            "The company continues to leverage favorable credit markets to optimize its "
            "capital structure."
        ),
    )

    print(brief)
    print()


def demo_microsoft_solvency():
    """Demonstrate Microsoft solvency assessment brief generation."""
    print("=" * 80)
    print("DEMO 3: Microsoft Corporation - Solvency Assessment")
    print("=" * 80)
    print()

    # Example: Microsoft solvency metrics (realistic 2023-2024 comparison)
    microsoft_metrics = VerifiedMetricsSet(
        company_name="Microsoft Corporation",
        fiscal_years=[2023, 2024],
        metrics={
            2023: [
                MetricResult(
                    metric_name="current_assets",
                    fiscal_year=2023,
                    value=185.0,
                    unit="USD billions",
                    status="verified",
                    source="XBRL",
                ),
                MetricResult(
                    metric_name="current_liabilities",
                    fiscal_year=2023,
                    value=91.0,
                    unit="USD billions",
                    status="verified",
                    source="XBRL",
                ),
                MetricResult(
                    metric_name="operating_cash_flow",
                    fiscal_year=2023,
                    value=72.0,
                    unit="USD billions",
                    status="verified",
                    source="XBRL",
                ),
            ],
            2024: [
                MetricResult(
                    metric_name="current_assets",
                    fiscal_year=2024,
                    value=198.0,
                    unit="USD billions",
                    status="verified",
                    source="XBRL",
                ),
                MetricResult(
                    metric_name="current_liabilities",
                    fiscal_year=2024,
                    value=99.0,
                    unit="USD billions",
                    status="verified",
                    source="XBRL",
                ),
                MetricResult(
                    metric_name="operating_cash_flow",
                    fiscal_year=2024,
                    value=78.0,
                    unit="USD billions",
                    status="verified",
                    source="XBRL",
                ),
            ],
        },
    )

    gen = BriefGenerator()
    brief = gen.generate_brief(
        "Microsoft Corporation",
        "solvency_assessment",
        microsoft_metrics,
        evidence_narrative=(
            "Microsoft's strong liquidity position reflects robust operating cash flows "
            "and disciplined working capital management. Current liabilities remain well "
            "below current assets, supporting short-term financial flexibility."
        ),
    )

    print(brief)
    print()


def demo_configuration_validation():
    """Demonstrate that all companies and themes are properly configured."""
    print("=" * 80)
    print("DEMO 4: Configuration Validation")
    print("=" * 80)
    print()

    loader = get_loader()

    # Companies
    companies = loader.load_companies()
    print(f"✓ Configured Companies: {len(companies)}")
    for cid, cfg in companies.items():
        print(f"  - {cid}: {cfg.name} ({cfg.ticker}), sector: {cfg.sector}")
    print()

    # Risk themes
    themes = loader.load_risk_themes()
    print(f"✓ Configured Risk Themes: {len(themes)}")
    for tid, cfg in themes.items():
        print(f"  - {tid}: {cfg.description}")
        print(f"    Metrics: {len(cfg.key_metrics)}, Sections: {len(cfg.required_sections)}")
    print()

    # Metrics
    metrics = loader.load_metrics()
    print(f"✓ Configured Metrics: {len(metrics)}")
    metric_list = list(metrics.keys())
    print(f"  {', '.join(metric_list[:10])}...")
    print()

    # Skills
    print("✓ Configured Skills:")
    for theme_id in themes.keys():
        skill_id = theme_id.replace("_analysis", "_research")
        try:
            skill = loader.load_skill(skill_id)
            lines = len(skill.split("\n"))
            print(f"  - {skill_id}: {lines} lines")
        except FileNotFoundError:
            print(f"  - {skill_id}: NOT FOUND")
    print()


def main():
    """Run all demos."""
    print()
    print("╔" + "=" * 78 + "╗")
    print("║" + " VERIFIED CREDIT RESEARCH AGENT — MULTI-COMPANY EXTENSIBILITY DEMO ".center(78) + "║")
    print("╚" + "=" * 78 + "╝")
    print()

    try:
        demo_configuration_validation()
        demo_task_generation()
        demo_apple_leverage()
        demo_microsoft_solvency()

        print("=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print()
        print("✓ Configuration system successfully enables:")
        print("  - 3+ companies with zero code changes")
        print("  - 4+ risk themes with zero code changes")
        print("  - Dynamic task generation for any (company, theme) combination")
        print("  - Automatic brief synthesis with theme-specific logic")
        print("  - Configuration-driven metrics and evidence requirements")
        print()
        print("To add a new company/theme:")
        print("  1. Add entry to configs/companies.yaml or configs/risk_themes.yaml")
        print("  2. (For new theme) Create skill markdown in configs/skills/")
        print("  3. Run task_generator.generate_task_spec() — no code changes needed")
        print()
        print("✓ M3 ReAct agent can process any generated task without modification")
        print()

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
