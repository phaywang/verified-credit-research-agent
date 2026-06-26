"""Evidence sufficiency checks for the Ford debt/liquidity loop."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Dict, List

from credit_research_agent.schemas import EvidenceChunk, EvidenceCoverage, TaskSpec

if TYPE_CHECKING:
    from credit_research_agent.skills.skill_loader import ResearchSkill


DEBT_TERMS = [
    "debt payable",
    "long-term debt",
    "debt maturities",
    "company debt excluding ford credit",
    "public unsecured debt",
    "credit agreements",
    "committed credit lines",
]

LIQUIDITY_TERMS = [
    "liquidity",
    "capital resources",
    "cash equivalents",
    "marketable securities",
    "available liquidity",
    "net liquidity available",
    "committed credit",
]

MANAGEMENT_TERMS = [
    "we believe",
    "we expect",
    "primarily due to",
    "primarily",
    "reflecting",
    "explained by",
    "driven by",
    "our key priority",
    "we manage",
    "remains well capitalized",
    "management's discussion",
]

NUMERIC_RE = re.compile(r"(\$\s*\(?\d|\b\d+(?:\.\d+)?\s*(?:billion|million|%))", re.I)


def _contains_any(text: str, terms: List[str]) -> bool:
    text_lower = text.lower()
    return any(term in text_lower for term in terms)


def _add_support(support: Dict[str, List[str]], field: str, chunk_id: str) -> None:
    support.setdefault(field, [])
    if chunk_id not in support[field]:
        support[field].append(chunk_id)


def is_management_explanation(chunk: EvidenceChunk) -> bool:
    """Return true for narrative MD&A-style management explanation evidence."""

    text = chunk.text.lower()
    if chunk.section_type != "mda":
        return False
    if not _contains_any(text, MANAGEMENT_TERMS):
        return False
    # Avoid treating pure tables as management explanation: require sentence-like prose.
    sentences = re.findall(r"[A-Z][^.]{40,}\.", chunk.text)
    return len(sentences) >= 2


def check_evidence_coverage(
    task_spec: TaskSpec,
    evidence: List[EvidenceChunk],
    iteration: int = 1,
    max_iterations: int = 3,
    skill: ResearchSkill | None = None,
) -> EvidenceCoverage:
    """Check whether selected evidence covers years and debt/liquidity categories.

    If skill is provided, required evidence categories come from skill.required_evidence_categories.
    Otherwise, defaults to [debt, liquidity, management_explanation, numeric_facts].
    """

    # Determine required categories from skill or defaults
    if skill is not None:
        required_categories = set(skill.required_evidence_categories)
    else:
        required_categories = {"debt", "liquidity", "management_explanation", "numeric_facts"}

    support: Dict[str, List[str]] = {}
    required_years = set(task_spec.years)

    debt_years = set()
    liquidity_years = set()

    for chunk in evidence:
        text = chunk.text.lower()
        if chunk.fiscal_year == 2023:
            _add_support(support, "has_2023_evidence", chunk.chunk_id)
        if chunk.fiscal_year == 2025:
            _add_support(support, "has_2025_evidence", chunk.chunk_id)

        if chunk.section_type == "debt" and _contains_any(text, DEBT_TERMS):
            debt_years.add(chunk.fiscal_year)
            _add_support(support, "has_debt_evidence", chunk.chunk_id)

        if chunk.section_type in {"liquidity", "credit_facilities", "mda"} and _contains_any(
            text, LIQUIDITY_TERMS
        ):
            liquidity_years.add(chunk.fiscal_year)
            _add_support(support, "has_liquidity_evidence", chunk.chunk_id)

        if is_management_explanation(chunk):
            _add_support(support, "has_management_explanation", chunk.chunk_id)

        if NUMERIC_RE.search(chunk.text) and chunk.section_type in {
            "debt",
            "liquidity",
            "credit_facilities",
            "mda",
        }:
            _add_support(support, "has_numeric_facts", chunk.chunk_id)

    coverage = EvidenceCoverage(
        has_2023_evidence=bool(support.get("has_2023_evidence")),
        has_2025_evidence=bool(support.get("has_2025_evidence")),
        has_debt_evidence=required_years.issubset(debt_years),
        has_liquidity_evidence=required_years.issubset(liquidity_years),
        has_management_explanation=bool(support.get("has_management_explanation")),
        has_numeric_facts=bool(support.get("has_numeric_facts")),
        supporting_chunk_ids=support,
    )

    missing = []
    if 2023 in required_years and not coverage.has_2023_evidence:
        missing.append("2023 evidence")
    if 2025 in required_years and not coverage.has_2025_evidence:
        missing.append("2025 evidence")
    if not coverage.has_debt_evidence and "debt" in required_categories:
        for year in sorted(required_years - debt_years):
            missing.append(f"{year} debt evidence")
    if not coverage.has_liquidity_evidence and "liquidity" in required_categories:
        for year in sorted(required_years - liquidity_years):
            missing.append(f"{year} liquidity evidence")
    if not coverage.has_management_explanation and "management_explanation" in required_categories:
        missing.append("management explanation")
    if not coverage.has_numeric_facts and "numeric_facts" in required_categories:
        missing.append("numeric facts")

    # Check for any other required categories from skill
    if skill is not None:
        for category in required_categories:
            if category not in ["debt", "liquidity", "management_explanation", "numeric_facts"]:
                # Check if evidence contains this category
                has_category = False
                for chunk in evidence:
                    if category in [c.lower() for c in chunk.evidence_category]:
                        has_category = True
                        break
                if not has_category:
                    missing.append(f"{category} evidence")

    coverage.missing = missing
    if not missing:
        coverage.decision = "sufficient"
    elif iteration < max_iterations:
        coverage.decision = "rewrite_query"
    else:
        coverage.decision = "proceed_with_limitations"
    return coverage
