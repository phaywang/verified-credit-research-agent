import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class MemoryRunSummary:
    """Summary of a completed run to persist in memory."""
    company: str
    ticker: str
    risk_theme: str
    successful_query: str
    failed_queries: list[str]
    useful_sections: list[str]
    verified_metrics: list[str]
    evidence_path: str


@dataclass
class MemoryUpdate:
    """Changes made to memory from a run."""
    successful_queries_added: int = 0
    useful_sections_added: int = 0
    verified_metrics_added: int = 0


@dataclass
class TopicMemory:
    """Memory for a specific company and risk theme."""
    useful_sections: list[str] = field(default_factory=list)
    successful_queries: list[str] = field(default_factory=list)
    failed_queries: list[str] = field(default_factory=list)
    prior_evidence_paths: list[str] = field(default_factory=list)
    verified_metrics: list[str] = field(default_factory=list)
    last_updated: str = ""


class ResearchMemory:
    """Persistent memory for research runs."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._data: dict = {}
        self._loaded = False

    def load(self) -> dict:
        """Load memory from disk."""
        if not self.path.exists():
            self._data = {}
            self._loaded = True
            return {}

        with open(self.path, "r", encoding="utf-8") as f:
            self._data = json.load(f)
        self._loaded = True
        return self._data

    def get_topic_memory(self, company: str, risk_theme: str) -> TopicMemory | None:
        """Retrieve memory for a company and risk theme."""
        if not self._loaded:
            self.load()

        if company not in self._data:
            return None

        company_data = self._data[company]
        if risk_theme not in company_data:
            return None

        topic_data = company_data[risk_theme]
        return TopicMemory(
            useful_sections=topic_data.get("useful_sections", []),
            successful_queries=topic_data.get("successful_queries", []),
            failed_queries=topic_data.get("failed_queries", []),
            prior_evidence_paths=topic_data.get("prior_evidence_paths", []),
            verified_metrics=topic_data.get("verified_metrics", []),
            last_updated=topic_data.get("last_updated", ""),
        )

    def update_from_run(self, summary: MemoryRunSummary) -> MemoryUpdate:
        """Update memory from a run summary."""
        if not self._loaded:
            self.load()

        if summary.company not in self._data:
            self._data[summary.company] = {}

        company_data = self._data[summary.company]
        if summary.risk_theme not in company_data:
            company_data[summary.risk_theme] = {
                "useful_sections": [],
                "successful_queries": [],
                "failed_queries": [],
                "prior_evidence_paths": [],
                "verified_metrics": [],
            }

        topic = company_data[summary.risk_theme]
        update = MemoryUpdate()

        # Add successful query if not already present
        if summary.successful_query and summary.successful_query not in topic["successful_queries"]:
            topic["successful_queries"].append(summary.successful_query)
            update.successful_queries_added = 1

        # Add failed queries
        for query in summary.failed_queries:
            if query and query not in topic["failed_queries"]:
                topic["failed_queries"].append(query)

        # Add useful sections
        for section in summary.useful_sections:
            if section and section not in topic["useful_sections"]:
                topic["useful_sections"].append(section)
                update.useful_sections_added += 1

        # Add verified metrics
        for metric in summary.verified_metrics:
            if metric and metric not in topic["verified_metrics"]:
                topic["verified_metrics"].append(metric)
                update.verified_metrics_added += 1

        # Add evidence path
        if summary.evidence_path and summary.evidence_path not in topic["prior_evidence_paths"]:
            topic["prior_evidence_paths"].append(summary.evidence_path)

        # Update timestamp
        topic["last_updated"] = datetime.utcnow().isoformat()

        return update

    def save(self) -> None:
        """Save memory to disk."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)


def select_initial_query(
    plan_query: str,
    topic_memory: TopicMemory | None,
    use_memory: bool,
) -> str:
    """Select the initial query for retrieval.

    If memory is enabled and available, use the best prior successful query.
    Otherwise, use the plan query.
    """
    if not use_memory or topic_memory is None:
        return plan_query

    if topic_memory.successful_queries:
        return topic_memory.successful_queries[-1]

    return plan_query


def section_boosts_from_memory(
    topic_memory: TopicMemory | None,
    use_memory: bool,
) -> dict[str, float]:
    """Create section boost hints from memory.

    If memory is enabled and has useful sections, boost those sections
    for retrieval. Otherwise, return empty boosts.
    """
    if not use_memory or topic_memory is None:
        return {}

    boosts = {}
    for section in topic_memory.useful_sections:
        section_lower = section.lower()
        if "liquidity" in section_lower:
            boosts["liquidity"] = 1.5
        if "debt" in section_lower:
            boosts["debt"] = 1.5
        if "commitment" in section_lower:
            boosts["commitment"] = 1.3
        if "management" in section_lower:
            boosts["management"] = 1.2

    return boosts
