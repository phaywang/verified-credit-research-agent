"""XBRL fact inventory for SEC companyfacts.

The inventory layer scans all annual companyfacts for a fiscal year first,
then downstream metric resolution decides which facts are safe to use. This is
more robust than assuming a single metric-to-tag mapping will hold for every
issuer and year.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from credit_research_agent.sec_integration import XBRLParser


def normalize_companyfact_value(value: Any) -> float | None:
    """Convert a companyfacts value to float and normalize large USD values to millions."""
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return None

    if abs(numeric_value) > 1_000_000:
        numeric_value = numeric_value / 1_000_000
    return numeric_value


@dataclass
class XBRLFact:
    """Best annual fact for one XBRL concept in one fiscal year."""

    concept: str
    namespace: str
    value: float | None
    raw_value: Any
    unit: str
    fiscal_year: int
    form: str
    fp: str
    filed: str
    end: str
    source: str = "SEC companyfacts"
    is_zero: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Return JSON-serializable fact metadata for trace logs."""
        return {
            "concept": self.concept,
            "namespace": self.namespace,
            "value": self.value,
            "raw_value": self.raw_value,
            "unit": self.unit,
            "fiscal_year": self.fiscal_year,
            "form": self.form,
            "fp": self.fp,
            "filed": self.filed,
            "end": self.end,
            "source": self.source,
            "is_zero": self.is_zero,
        }


@dataclass
class XBRLFactInventory:
    """Annual inventory of available SEC companyfacts."""

    fiscal_year: int
    facts: List[XBRLFact]

    @property
    def by_concept(self) -> Dict[str, XBRLFact]:
        """Map local concept name to fact."""
        return {fact.concept: fact for fact in self.facts}

    def find_by_concept(self, concepts: List[str]) -> XBRLFact | None:
        """Return the first inventory fact matching candidate concepts in priority order."""
        concept_map = self.by_concept
        for concept in concepts:
            local_name = concept.split(":")[-1]
            fact = concept_map.get(local_name)
            if fact is not None:
                return fact
        return None

    def search_concepts(self, terms: List[str]) -> List[XBRLFact]:
        """Search concept names for related facts."""
        normalized_terms = [term.lower() for term in terms if term and len(term) >= 3]
        if not normalized_terms:
            return []

        matches = []
        for fact in self.facts:
            concept_lower = fact.concept.lower()
            if any(term in concept_lower for term in normalized_terms):
                matches.append(fact)
        return sorted(matches, key=lambda fact: fact.concept)

    def summary(self) -> Dict[str, Any]:
        """Return compact inventory summary for trace logs."""
        return {
            "fiscal_year": self.fiscal_year,
            "fact_count": len(self.facts),
            "concepts_sample": [fact.concept for fact in self.facts[:20]],
        }


class XBRLFactInventoryBuilder:
    """Build annual XBRL fact inventories from SEC companyfacts JSON."""

    def __init__(self, parser: XBRLParser | None = None):
        self.parser = parser or XBRLParser()

    def build(self, companyfacts: Dict[str, Any], fiscal_year: int) -> XBRLFactInventory:
        """Build an annual inventory using the parser's existing 10-K fact selection."""
        inventory_facts: List[XBRLFact] = []
        facts = companyfacts.get("facts", {})

        for namespace, namespace_facts in facts.items():
            for concept, concept_data in namespace_facts.items():
                selected = self.parser._extract_companyfact(
                    {namespace: {concept: concept_data}},
                    concept,
                    fiscal_year,
                )
                if selected is None:
                    continue

                raw_value = selected.get("val")
                normalized_value = normalize_companyfact_value(raw_value)
                inventory_facts.append(
                    XBRLFact(
                        concept=concept,
                        namespace=namespace,
                        value=normalized_value,
                        raw_value=raw_value,
                        unit=selected.get("unit", ""),
                        fiscal_year=fiscal_year,
                        form=selected.get("form", ""),
                        fp=selected.get("fp", ""),
                        filed=selected.get("filed", ""),
                        end=selected.get("end", ""),
                        is_zero=raw_value == 0 or normalized_value == 0,
                    )
                )

        return XBRLFactInventory(
            fiscal_year=fiscal_year,
            facts=sorted(inventory_facts, key=lambda fact: (fact.namespace, fact.concept)),
        )
