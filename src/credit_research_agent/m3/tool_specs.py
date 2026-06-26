"""Tool specs for M3 Bedrock tool calling."""

from __future__ import annotations

import copy
from typing import Any, Dict, List

from credit_research_agent.m3.tool_registry import ToolRegistry, ToolSpec


def phase1_gate_registry() -> ToolRegistry:
    """Small registry for the real Bedrock multi-turn gate."""

    state: Dict[str, Any] = {"steps": []}

    def remember_step(step_name: str, observation: str) -> Dict[str, Any]:
        state["steps"].append({"step_name": step_name, "observation": observation})
        return {
            "recorded_steps": copy.deepcopy(state["steps"]),
            "step_count": len(state["steps"]),
        }

    def summarize_steps() -> Dict[str, Any]:
        return {
            "summary": copy.deepcopy(state["steps"]),
            "step_count": len(state["steps"]),
        }

    return ToolRegistry(
        [
            ToolSpec(
                name="remember_step",
                description="Record one short step observation. Use this exactly three times before summarizing.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "step_name": {"type": "string"},
                        "observation": {"type": "string"},
                    },
                    "required": ["step_name", "observation"],
                },
                function=remember_step,
            ),
            ToolSpec(
                name="summarize_steps",
                description="Return all recorded steps after three remember_step calls.",
                input_schema={"type": "object", "properties": {}, "required": []},
                function=summarize_steps,
            ),
        ]
    )


def ford_research_registry() -> ToolRegistry:
    """LLM-callable deterministic tools for Ford M3."""

    from credit_research_agent.m3 import deterministic_tools

    return ToolRegistry(
        [
            ToolSpec(
                name="hybrid_retrieve",
                description="Retrieve ranked Ford SEC filing evidence chunks using hybrid BM25/vector search.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "top_n": {"type": "integer", "default": 10},
                    },
                    "required": ["query"],
                },
                function=deterministic_tools.hybrid_retrieve,
            ),
            ToolSpec(
                name="xbrl_fact_lookup",
                description="Look up a high-confidence XBRL debt fact for Ford.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "metric_name": {"type": "string"},
                        "fiscal_year": {"type": "integer"},
                    },
                    "required": ["metric_name", "fiscal_year"],
                },
                function=deterministic_tools.xbrl_fact_lookup,
            ),
            ToolSpec(
                name="verify_numeric_claim",
                description="Verify a Ford metric change across two fiscal years.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "metric_name": {"type": "string"},
                        "old_year": {"type": "integer"},
                        "new_year": {"type": "integer"},
                    },
                    "required": ["metric_name", "old_year", "new_year"],
                },
                function=deterministic_tools.verify_numeric_claim,
            ),
            ToolSpec(
                name="calculate_change",
                description="Calculate absolute change, percentage change, and direction.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "old_value": {"type": "number"},
                        "new_value": {"type": "number"},
                    },
                    "required": ["old_value", "new_value"],
                },
                function=deterministic_tools.calculate_change,
            ),
            ToolSpec(
                name="query_memory",
                description="Read prior Ford debt/liquidity research memory.",
                input_schema={
                    "type": "object",
                    "properties": {"topic": {"type": "string", "default": "debt_liquidity"}},
                    "required": [],
                },
                function=deterministic_tools.query_memory,
            ),
            ToolSpec(
                name="query_rewrite_helper",
                description="Create a deterministic fallback query rewrite from coverage gaps.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "coverage_gaps": {"type": "array", "items": {"type": "string"}},
                        "company": {"type": "string", "default": "Ford"},
                        "years": {"type": "array", "items": {"type": "integer"}},
                    },
                    "required": ["coverage_gaps"],
                },
                function=deterministic_tools.query_rewrite_helper,
            ),
            ToolSpec(
                name="numeric_guardrail_check",
                description="Check brief text for unverified financial numbers.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "brief_text": {"type": "string"},
                        "verified_facts": {"type": "object"},
                    },
                    "required": ["brief_text"],
                },
                function=deterministic_tools.numeric_guardrail_check,
            ),
            ToolSpec(
                name="write_workpaper",
                description="Write an auditable workpaper artifact.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "artifact_name": {"type": "string"},
                        "content": {},
                    },
                    "required": ["artifact_name", "content"],
                },
                function=deterministic_tools.write_workpaper,
            ),
        ]
    )
