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
from credit_research_agent.evaluation.metrics import compute_evaluation_summary
from credit_research_agent.memory.research_memory import (
    MemoryRunSummary,
    ResearchMemory,
    section_boosts_from_memory,
    select_initial_query,
)
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
from credit_research_agent.skills.skill_loader import load_debt_liquidity_skill
from credit_research_agent.verification.fact_extractor import extract_numeric_facts
from credit_research_agent.verification.fact_store import FactStore
from credit_research_agent.verification.numeric_claim_extractor import propose_numeric_claims
from credit_research_agent.verification.numeric_verifier import verify_numeric_claims
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
        use_memory: bool = True,
        memory_path: Path | None = None,
        skill_path: Path | None = None,
    ) -> None:
        self.run_id = run_id
        self.force_rewrite_demo = force_rewrite_demo
        self.use_memory = use_memory
        self.memory_path = memory_path or Path("memory/research_memory.json")
        self.skill_path = skill_path or Path("skills/debt_liquidity_research/SKILL.md")

    def _initial_query(self, plan_query: str, topic_memory=None) -> str:
        # If memory is enabled and has successful query, use it
        if self.use_memory and topic_memory and topic_memory.successful_queries:
            return topic_memory.successful_queries[-1]

        # Otherwise, use weak demo query if force_rewrite_demo is on
        if self.force_rewrite_demo:
            return "Ford 2023 10-K liquidity cash credit facilities"

        # Default to plan query
        return plan_query

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

        # READ_MEMORY: Load memory and select initial query
        memory = ResearchMemory(self.memory_path)
        memory.load()
        topic_memory = memory.get_topic_memory("Ford Motor Company", "debt_liquidity")
        memory_used = self.use_memory and topic_memory is not None
        selected_query = self._initial_query(plan.initial_query, topic_memory)
        boosts = section_boosts_from_memory(topic_memory, self.use_memory)

        trace.log_step(
            TraceStep(
                state="READ_MEMORY",
                summary="Loaded research memory and selected initial query.",
                parameters={
                    "memory_used": memory_used,
                    "memory_path": str(self.memory_path),
                    "selected_initial_query": selected_query,
                    "useful_sections": topic_memory.useful_sections if topic_memory else [],
                    "section_boosts": boosts,
                },
            )
        )

        # LOAD_SKILL: Load and parse skill file
        skill = None
        try:
            if self.skill_path.exists():
                skill = load_debt_liquidity_skill(self.skill_path)
                trace.log_step(
                    TraceStep(
                        state="LOAD_SKILL",
                        summary="Loaded debt/liquidity research skill.",
                        parameters={
                            "skill_path": str(self.skill_path),
                            "skill_name": skill.name,
                            "required_evidence_categories": skill.required_evidence_categories,
                            "require_verified_numeric_conclusions": skill.require_verified_numeric_conclusions,
                        },
                    )
                )
        except Exception:
            pass  # If skill loading fails, continue without it

        query = selected_query

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
            # Only use year filter on first iteration when memory is not being used
            # (memory provides strong queries that don't need the filter to demonstrate rewrite)
            filters = RetrievalFilters(years=[2023]) if self.force_rewrite_demo and iteration == 1 and not memory_used else None
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
                skill=skill,
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

        numeric_facts = extract_numeric_facts(
            chunks,
            DATA_DIR / "raw" / "sec" / "ford",
            years=task_spec.years,
        )
        write_json(
            workspace.artifact_path("numeric_facts"),
            [fact.model_dump(mode="json") for fact in numeric_facts],
        )
        trace.log_step(
            TraceStep(
                state="EXTRACT_NUMERIC_FACTS",
                tools_called=["xbrl_candidate_mapping", "narrative_regex", "source_classification"],
                summary="Extracted XBRL debt facts and classified liquidity text facts.",
                outputs={"numeric_facts_path": str(workspace.artifact_path("numeric_facts"))},
                parameters={
                    "facts_extracted": len(numeric_facts),
                    "high_confidence_facts": sum(1 for fact in numeric_facts if fact.confidence == "high"),
                    "review_required_facts": sum(1 for fact in numeric_facts if fact.review_required),
                },
            )
        )

        fact_store = FactStore()
        fact_store.add_facts(numeric_facts)
        numeric_claims = propose_numeric_claims(task_spec, fact_store)
        write_json(
            workspace.artifact_path("numeric_claims"),
            [claim.model_dump(mode="json") for claim in numeric_claims],
        )
        trace.log_step(
            TraceStep(
                state="PROPOSE_NUMERIC_CLAIMS",
                summary="Proposed deterministic comparison claims from extracted fact pairs.",
                outputs={"numeric_claims_path": str(workspace.artifact_path("numeric_claims"))},
                parameters={"claims_proposed": len(numeric_claims)},
            )
        )

        verification_results = verify_numeric_claims(numeric_claims, fact_store)
        write_json(
            workspace.artifact_path("numeric_verification"),
            [result.model_dump(mode="json") for result in verification_results],
        )
        trace.log_step(
            TraceStep(
                state="VERIFY_NUMERIC_CLAIMS",
                tools_called=["calculate_change", "calculate_percentage_change", "direction"],
                summary="Verified candidate numeric comparison claims deterministically.",
                outputs={"numeric_verification_path": str(workspace.artifact_path("numeric_verification"))},
                parameters={
                    "verified_claims": sum(1 for result in verification_results if result.status == "verified"),
                    "non_verified_claims": sum(1 for result in verification_results if result.status != "verified"),
                },
            )
        )

        final_answer = synthesize_final_answer(
            task_spec,
            all_evidence,
            coverage,
            str(workspace.artifact_path("trace_log")),
            verification_results=verification_results,
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

        numeric_source_chunk_ids = {
            fact.source_chunk_id
            for fact in numeric_facts
        }
        critic_report = critique_answer(
            final_answer,
            all_evidence,
            extra_allowed_chunk_ids=numeric_source_chunk_ids,
            verification_results=verification_results,
        )
        review_required_count = sum(1 for fact in numeric_facts if fact.review_required)
        if review_required_count:
            critic_report.notes.append(
                f"Excluded {review_required_count} review-required low-confidence fact(s) from numeric conclusion sentences."
            )
        critic_report.notes.append(
            "Deferred company_debt_maturities_next_twelve_months because no validated total-bucket XBRL mapping is implemented."
        )
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
            repaired_report = critique_answer(
                final_answer,
                all_evidence,
                extra_allowed_chunk_ids=numeric_source_chunk_ids,
                verification_results=verification_results,
            )
            write_json(workspace.artifact_path("critic_report"), repaired_report)
            trace.log_step(
                TraceStep(
                    state="REPAIR",
                    summary="Removed unsupported claims and rewrote final answer artifact.",
                    outputs={"final_answer_path": str(workspace.artifact_path("final_answer"))},
                )
            )
            critic_report = repaired_report

        evaluation_summary = compute_evaluation_summary(
            final_answer,
            verification_results,
            coverage,
        )
        write_json(workspace.artifact_path("evaluation_summary"), evaluation_summary)
        trace.log_step(
            TraceStep(
                state="EVALUATE",
                summary="Computed simple M2a evaluation metrics.",
                outputs={"evaluation_summary_path": str(workspace.artifact_path("evaluation_summary"))},
                parameters=evaluation_summary.model_dump(mode="json"),
            )
        )

        # UPDATE_MEMORY: Persist successful query and useful sections
        if self.use_memory:
            verified_metrics = [
                result.metric_name
                for result in verification_results
                if result.status == "verified"
            ]
            # Use the last successful query: if there were rewrites, use the last rewritten query
            # Otherwise use the initial selected query
            successful_query_to_save = (
                query_rewrites[-1]["new_query"] if query_rewrites else selected_query
            )
            memory_summary = MemoryRunSummary(
                company="Ford Motor Company",
                ticker="F",
                risk_theme="debt_liquidity",
                successful_query=successful_query_to_save,
                failed_queries=[r["old_query"] for r in query_rewrites],
                useful_sections=[chunk.section_name for chunk in all_evidence if chunk.section_name],
                verified_metrics=verified_metrics,
                evidence_path=str(workspace.artifact_path("evidence_table")),
            )
            memory_update = memory.update_from_run(memory_summary)
            memory.save()
            write_json(workspace.artifact_path("memory_update"), {
                "successful_queries_added": memory_update.successful_queries_added,
                "useful_sections_added": memory_update.useful_sections_added,
                "verified_metrics_added": memory_update.verified_metrics_added,
            })
            trace.log_step(
                TraceStep(
                    state="UPDATE_MEMORY",
                    summary="Updated research memory with successful query and useful sections.",
                    parameters={
                        "successful_queries_added": memory_update.successful_queries_added,
                        "useful_sections_added": memory_update.useful_sections_added,
                        "verified_metrics_added": memory_update.verified_metrics_added,
                    },
                )
            )

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
