"""Static plan generation for the Milestone 1 Ford demo."""

from __future__ import annotations

from credit_research_agent.schemas import Plan, TaskSpec


def create_plan(task_spec: TaskSpec, max_retrieval_iterations: int = 3) -> Plan:
    """Create the deterministic research plan used by the loop controller."""

    years = " ".join(str(year) for year in task_spec.years)
    filing_types = " ".join(task_spec.filing_types)
    initial_query = (
        f"Ford {years} {filing_types} debt liquidity risk long-term debt "
        "liquidity capital resources credit facilities management discussion"
    )

    return Plan(
        objective=(
            "Compare Ford debt and liquidity risk evidence between the requested "
            "comparison years."
        ),
        research_steps=[
            "Retrieve debt evidence for both years",
            "Retrieve liquidity and capital resources evidence for both years",
            "Retrieve management explanations from MD&A or liquidity sections",
            "Check whether evidence covers both years and required categories",
            "Rewrite targeted queries for missing categories",
            "Synthesize only cited conclusions",
        ],
        initial_query=initial_query,
        max_retrieval_iterations=max_retrieval_iterations,
    )

