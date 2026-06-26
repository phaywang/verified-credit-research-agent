"""Generic task generator for multi-company, multi-theme research tasks.

Replaces hardcoded task generation (planner.py) with configuration-driven approach.
Enables dynamic task creation from company + risk_theme without code changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from credit_research_agent.config_loader import get_loader
from credit_research_agent.schemas import TaskSpec


@dataclass
class ResearchTask:
    """A concrete research task for a specific (company, risk_theme, years)."""
    company_id: str
    risk_theme_id: str
    comparison_years: List[int]
    question: str
    evidence_requirements: List[str]
    required_sections: List[str]


class TaskGenerator:
    """Generate research tasks from configuration."""

    def __init__(self):
        self.loader = get_loader()

    def generate_task(
        self,
        company_id: str,
        risk_theme_id: str,
        comparison_years: List[int] | None = None,
    ) -> ResearchTask:
        """Generate a research task for a (company, risk_theme) pair.

        Args:
            company_id: e.g., "ford", "apple", "microsoft"
            risk_theme_id: e.g., "debt_liquidity", "leverage_analysis"
            comparison_years: fiscal years to compare, defaults to company config

        Returns:
            ResearchTask with question, evidence requirements, sections
        """
        # Load configs
        company = self.loader.get_company(company_id)
        theme = self.loader.get_risk_theme(risk_theme_id)

        # Use provided years or company's configured years
        if comparison_years is None:
            comparison_years = company.fiscal_years[-theme.comparison_years:]

        # Generate natural language question
        question = self._generate_question(
            company=company.name,
            risk_theme=theme.description,
            years=comparison_years,
        )

        return ResearchTask(
            company_id=company_id,
            risk_theme_id=risk_theme_id,
            comparison_years=comparison_years,
            question=question,
            evidence_requirements=theme.required_evidence_categories,
            required_sections=theme.required_sections,
        )

    def generate_task_spec(
        self,
        company_id: str,
        risk_theme_id: str,
        comparison_years: List[int] | None = None,
    ) -> TaskSpec:
        """Generate a TaskSpec suitable for M3 ReAct agent.

        Args:
            company_id: e.g., "ford"
            risk_theme_id: e.g., "debt_liquidity"
            comparison_years: defaults to company config

        Returns:
            TaskSpec ready for loop controller
        """
        task = self.generate_task(company_id, risk_theme_id, comparison_years)
        company = self.loader.get_company(company_id)

        # Create TaskSpec
        return TaskSpec(
            question=task.question,
            company=company.name,
            ticker=company.ticker,
            cik=company.cik,
            risk_theme=risk_theme_id,
            filing_types=company.filing_types,
            years=task.comparison_years,
            required_evidence=task.evidence_requirements,
        )

    @staticmethod
    def _generate_question(company: str, risk_theme: str, years: List[int]) -> str:
        """Generate a natural language research question.

        Args:
            company: Company name (e.g., "Ford Motor Company")
            risk_theme: Theme description (e.g., "Debt level changes...")
            years: Fiscal years to compare

        Returns:
            Natural language question
        """
        if len(years) == 2:
            return f"How has {company}'s {risk_theme} changed from {years[0]} to {years[1]}, and what evidence supports the change?"
        else:
            return f"What is {company}'s {risk_theme} as of {years[-1]}? What evidence supports this assessment?"


# Global generator instance
_generator: TaskGenerator | None = None


def get_generator() -> TaskGenerator:
    """Get or create the global task generator."""
    global _generator
    if _generator is None:
        _generator = TaskGenerator()
    return _generator


def reset_generator() -> None:
    """Reset the global generator (for testing)."""
    global _generator
    _generator = None
