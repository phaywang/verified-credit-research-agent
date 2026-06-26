"""Agentic retrieval loop controller for Milestone 1."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

from credit_research_agent.agent.critic import critique_answer, repair_answer
from credit_research_agent.agent.evidence_checker import check_evidence_coverage
from credit_research_agent.agent.planner import create_plan
from credit_research_agent.agent.query_rewriter import rewrite_query, rewrite_reason
from credit_research_agent.agent.synthesizer import synthesize_final_answer
from credit_research_agent.agent.task_parser import parse_task
from credit_research_agent.config import DATA_DIR, DEFAULT_RUN_ID
from credit_research_agent.retrieval.chunk_store import load_chunks_jsonl
from credit_research_agent.retrieval.hybrid_retriever import HybridRetriever, RetrievalFilters
from credit_research_agent.retrieval.reranker import Reranker
from credit_research_agent.schemas import (
    CriticReport,
    EvidenceChunk,
    EvidenceCoverage,
    FinalMetrics,
    RetrievalResult,
    TraceStep,
    write_json,
)
from credit_research_agent.workpapers.run_workspace import RunWorkspace, create_run_workspace
from credit_research_agent.workpapers.trace_logger import TraceLogger


DEFAULT_QUESTION = (
    "How did Ford's debt and liquidity risk change from 2023 to 2025, "
    "and what evidence supports the change?"
)


class LoopController:
    def __init__(
        self,
        run_id: str = DEFAULT_RUN_ID,
        force_rewrite_demo: bool = False,
    ) -> None:
        self.run_id = run_id
        self.force_rewrite_demo = force_rewrite_demo

    def _initial_query(self, plan_query: str) -> str:
        if not self.force_rewrite_demo:
            return plan_query
        return "Ford 2023 10-K liquidity cash credit facilities"

    def _retrieval_sizes(self, iteration: int) -> Tuple[int, int]:
        if self.force_rewrite_demo and iteration == 1:
            return 8, 3
        return 40, 12

    def _dedupe_evidence(self, evidence: List[EvidenceChunk]) -> List[EvidenceChunk]:
        by_id: Dict[str, EvidenceChunk] = {}
        for chunk in sorted(evidence, key=lambda item: item.reranker_score, reverse=True):
            by_id.setdefault(chunk.chunk_id, chunk)
        return sorted(by_id.values(), key=lambda item: item.reranker_score, reverse=True)

    def run(self, question: str = DEFAULT_QUESTION) -> RunWorkspace:
        workspace = create_run_workspace(self.run_id)
        task_spec = parse_task(question)
        plan = create_plan(task_spec)
        query = self._initial_query(plan.initial_query)

        workspace.write_task(question)
        workspace.write_task_spec(task_spec)
        workspace.write_plan(plan)

        trace = TraceLogger(
            run_id=workspace.run_id,
            task=question,
            task_spec_path=str(workspace.artifact_path("task_spec")),
            artifacts=workspace.relative_artifacts(),
        )
        trace.log_step(
            TraceStep(
                state="PLAN",
                summary="Created deterministic Ford debt/liquidity research plan.",
                outputs={"plan_path": str(workspace.artifact_path("plan"))},
            )
        )

        chunk_path = DATA_DIR / "processed" / "ford_2023_2025_chunks.jsonl"
        chunks = load_chunks_jsonl(chunk_path)
        retriever = HybridRetriever(chunks)
        reranker = Reranker(retriever.embedder)

        all_retrieved: List[RetrievalResult] = []
        all_evidence: List[EvidenceChunk] = []
        query_rewrites = []
        coverage = EvidenceCoverage()
        iterations_run = 0

        for iteration in range(1, plan.max_retrieval_iterations + 1):
            iterations_run = iteration
            top_n, top_k = self._retrieval_sizes(iteration)
            state = "RETRIEVE" if iteration == 1 else "RETRIEVE_AGAIN"
            filters = RetrievalFilters(years=[2023]) if self.force_rewrite_demo and iteration == 1 else None
            candidates = retriever.retrieve(query, top_n=top_n, filters=filters)
            all_retrieved.extend(candidates)
            trace.log_step(
                TraceStep(
                    state=state,
                    iteration=iteration,
                    query=query,
                    tools_called=["bm25_search", "vector_search", "rrf_fusion"],
                    parameters={
                        "top_n": top_n,
                        "rrf_k": retriever.rrf_k,
                        "filters": filters.__dict__ if filters else None,
                    },
                    top_chunks=[candidate.chunk_id for candidate in candidates[:10]],
                    summary=f"Retrieved {len(candidates)} fused candidates.",
                )
            )

            evidence = reranker.rerank(query, candidates, top_k=top_k)
            all_evidence = self._dedupe_evidence(all_evidence + evidence)
            trace.log_step(
                TraceStep(
                    state="RERANK",
                    iteration=iteration,
                    query=query,
                    tools_called=["local_embedding_reranker"],
                    parameters={"top_k": top_k},
                    top_chunks=[chunk.chunk_id for chunk in evidence],
                    summary=f"Reranked to {len(evidence)} evidence chunks.",
                )
            )

            coverage = check_evidence_coverage(
                task_spec,
                all_evidence,
                iteration=iteration,
                max_iterations=plan.max_retrieval_iterations,
            )
            trace.log_step(
                TraceStep(
                    state="EVIDENCE_CHECK",
                    iteration=iteration,
                    coverage=coverage.model_dump(mode="json"),
                    missing=coverage.missing,
                    decision=coverage.decision,
                    summary="Checked evidence coverage using year metadata, section metadata, and substantive content signals.",
                )
            )

            if coverage.decision != "rewrite_query":
                break

            old_query = query
            query = rewrite_query(task_spec, old_query, coverage, iteration)
            reason = rewrite_reason(coverage)
            query_rewrites.append(
                {
                    "iteration": iteration,
                    "old_query": old_query,
                    "new_query": query,
                    "missing": coverage.missing,
                    "reason": reason,
                }
            )
            trace.log_step(
                TraceStep(
                    state="QUERY_REWRITE",
                    iteration=iteration,
                    old_query=old_query,
                    new_query=query,
                    missing=coverage.missing,
                    reason=reason,
                    summary="Rewrote query to target missing evidence coverage.",
                )
            )

        write_json(
            workspace.artifact_path("retrieved_chunks"),
            [result.model_dump(mode="json") for result in all_retrieved],
        )
        write_json(
            workspace.artifact_path("reranked_chunks"),
            [chunk.model_dump(mode="json") for chunk in all_evidence],
        )
        write_json(
            workspace.artifact_path("evidence_table"),
            [chunk.model_dump(mode="json") for chunk in all_evidence],
        )
        write_json(workspace.artifact_path("evidence_coverage"), coverage)
        write_json(workspace.artifact_path("query_rewrites"), query_rewrites)

        final_answer = synthesize_final_answer(
            task_spec,
            all_evidence,
            coverage,
            str(workspace.artifact_path("trace_log")),
        )
        workspace.artifact_path("final_answer").write_text(
            final_answer.markdown,
            encoding="utf-8",
        )
        trace.log_step(
            TraceStep(
                state="SYNTHESIZE",
                summary="Generated deterministic cited credit research brief.",
                outputs={"final_answer_path": str(workspace.artifact_path("final_answer"))},
            )
        )

        critic_report = critique_answer(final_answer, all_evidence)
        write_json(workspace.artifact_path("critic_report"), critic_report)
        trace.log_step(
            TraceStep(
                state="CRITIC",
                decision="repair" if critic_report.needs_repair else "finalize",
                summary="Checked final answer claims against retrieved evidence chunk IDs.",
                outputs={"critic_report_path": str(workspace.artifact_path("critic_report"))},
            )
        )

        if critic_report.needs_repair:
            final_answer = repair_answer(final_answer, critic_report)
            workspace.artifact_path("final_answer").write_text(
                final_answer.markdown,
                encoding="utf-8",
            )
            repaired_report = critique_answer(final_answer, all_evidence)
            write_json(workspace.artifact_path("critic_report"), repaired_report)
            trace.log_step(
                TraceStep(
                    state="REPAIR",
                    summary="Removed unsupported claims and rewrote final answer artifact.",
                    outputs={"final_answer_path": str(workspace.artifact_path("final_answer"))},
                )
            )
            critic_report = repaired_report

        metrics = FinalMetrics(
            citation_coverage=(
                1.0
                if final_answer.claims and not critic_report.unsupported_claims
                else 0.0
            ),
            evidence_coverage_passed=coverage.decision == "sufficient",
            unsupported_claim_count=len(critic_report.unsupported_claims),
            retrieval_iterations=iterations_run,
            rewrite_count=len(query_rewrites),
            substitution_used=False,
        )
        trace.log_step(
            TraceStep(
                state="FINALIZE",
                summary="Finalized workpaper artifacts and trace log.",
                outputs={
                    "final_answer_path": str(workspace.artifact_path("final_answer")),
                    "trace_log_path": str(workspace.artifact_path("trace_log")),
                },
            )
        )
        trace.finalize(metrics, loop_iterations=iterations_run)
        trace.write(workspace.artifact_path("trace_log"))
        return workspace
