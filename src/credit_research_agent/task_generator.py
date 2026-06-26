"""Generic task generator for multi-company, multi-theme research tasks.

Replaces hardcoded task generation (planner.py) with configuration-driven approach.
Enables dynamic task creation from company + risk_theme without code changes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

from credit_research_agent.config_loader import get_loader
from credit_research_agent.schemas import TaskSpec
from credit_research_agent.sec_integration import (
    SECCompanyLookup,
    CompanyNotFoundError,
)

logger = logging.getLogger(__name__)


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
        self.sec_lookup = SECCompanyLookup()

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

    def generate_task_spec_universal(
        self,
        ticker: str,
        risk_theme_id: str,
        comparison_years: Optional[List[int]] = None,
    ) -> TaskSpec:
        """Generate TaskSpec for any stock ticker with auto-CIK lookup.

        This method supports ANY US stock ticker, not just pre-configured companies.
        If the company is pre-configured, uses cached config (faster).
        If new, looks up CIK from SEC EDGAR (slightly slower, but works universally).

        Args:
            ticker: Stock ticker (e.g., "AAPL", "TSLA", "JPM")
            risk_theme_id: Risk theme (e.g., "leverage_analysis")
            comparison_years: Fiscal years (defaults to [2023, 2024])

        Returns:
            TaskSpec ready for M3 ReAct agent

        Raises:
            CompanyNotFoundError: If ticker not found in SEC EDGAR
        """
        ticker_upper = ticker.upper()

        # Try to find in pre-configured companies first (faster)
        try:
            # Check if this ticker exists in config
            company_id = self._find_company_id_by_ticker(ticker_upper)
            logger.info(f"Found {ticker_upper} in pre-configured companies")
            return self.generate_task_spec(
                company_id, risk_theme_id, comparison_years
            )
        except ValueError:
            # Not in pre-configured, do SEC lookup
            logger.info(f"{ticker_upper} not pre-configured, looking up in SEC EDGAR")
            cik = self.sec_lookup.get_cik_by_ticker(ticker_upper)
            company_info = self.sec_lookup.get_company_info(cik)

            # Use provided years or defaults
            if comparison_years is None:
                comparison_years = company_info.fiscal_years_available[-2:]

            # Get theme config
            theme = self.loader.get_risk_theme(risk_theme_id)

            # Generate question
            question = self._generate_question(
                company=company_info.name,
                risk_theme=theme.description,
                years=comparison_years,
            )

            # Create TaskSpec with SEC-fetched data
            return TaskSpec(
                question=question,
                company=company_info.name,
                ticker=ticker_upper,
                cik=company_info.cik,
                risk_theme=risk_theme_id,
                filing_types=["10-K"],  # SEC-based defaults to 10-K
                years=comparison_years,
                required_evidence=theme.required_evidence_categories,
            )

    def _find_company_id_by_ticker(self, ticker: str) -> str:
        """Find company ID in config by ticker.

        Args:
            ticker: Stock ticker (e.g., "AAPL")

        Returns:
            Company ID from config (e.g., "apple")

        Raises:
            ValueError: If ticker not found in config
        """
        # Try to find ticker in all configured companies
        try:
            # Iterate through all company configs
            company_ids = ["ford", "apple", "microsoft", "tesla"]  # Known configured companies
            for company_id in company_ids:
                try:
                    company = self.loader.get_company(company_id)
                    if company.ticker == ticker:
                        return company_id
                except Exception:
                    # Company not found, continue
                    pass
        except Exception:
            pass

        raise ValueError(f"Ticker {ticker} not found in configured companies")

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
