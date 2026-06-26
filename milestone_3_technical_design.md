# Verified Credit Research Agent - Milestone 3
## LLM-Driven ReAct Agent for Financial Analysis

**Status**: Design phase (review only, no implementation)  
**Objective**: Upgrade M2's deterministic harness into an LLM-driven ReAct agent while maintaining auditability and numeric accuracy.

---

## Executive Summary

Milestone 3 injects Claude LLM into the completed M1+M2 harness skeleton using **ReAct (Reasoning + Acting)** pattern. The architecture preserves all M1/M2 components and extends them with LLM decision-making at key junctures while enforcing **neurosymbolic guardrails** — LLM drives reasoning/planning/synthesis; deterministic tools compute and verify numerics. Every LLM-generated number must be verified or sourced from facts.

### Evolution

```
M1: Rule-driven retrieval loop (Level 0)
    ↓
M2: Deterministic verification + memory/skill config (Level 1)
    ↓
M3: LLM-driven ReAct loop + tool use + neurosymbolic guardrails (Level 2)
    
From: "Run a canned retrieval query → verify facts → synthesize"
To:   "LLM reasons about evidence → decides what to retrieve/verify → 
       adjusts strategy → synthesizes with guardrails"
```

---

## 1. Architecture: LLM-Augmented Harness

### 1.1 Full Pipeline with M3 Additions

```
User Question
    ↓
Task Spec Parser (M1, unchanged)
    ↓
READ_MEMORY → LOAD_SKILL (M2, unchanged)
    ↓
LLM PLANNER [NEW]  
    - Reasons: What evidence is needed? Which tools to invoke?
    - Outputs: Research plan + initial retrieval targets
    ↓
HYBRID_RETRIEVAL (M1: BM25 + Vector + RRF, tool-ified for LLM)
    ↓
RERANK (M1, tool-ified)
    ↓
LLM EVIDENCE EVALUATOR [NEW]
    - Thinks: Is evidence sufficient? What's missing?
    - Decides: Rewrite query or proceed to verification?
    - Runs QUERY_REWRITE tool if needed (M1 rule engine, now tool)
    ↓
NUMERIC VERIFICATION (M2: deterministic, tool-ified)
    - xbrl_fact_lookup(metric, year)
    - verify_numeric_claim(claim)
    - calculate_change(old, new) → (delta, pct_change, direction)
    ↓
LLM SYNTHESIZER [UPGRADED from M2]
    - Reasons: How to write conclusions from verified facts?
    - Generates: Credit brief with verified numeric insights
    - Guardrail: Numbers must come from verification results
    ↓
LLM CRITIC / REFLECTION [UPGRADED from M2]
    - Evaluates: Are claims supported? Any numeric inconsistencies?
    - Decides: Accept brief or invoke REPAIR tool?
    ↓
REPAIR (M2 rule engine, tool-ified if needed)
    ↓
Workpaper + Trace + Final Brief (M2, enhanced with LLM trace steps)
```

### 1.2 Component Status Matrix

| Component | M1 | M2 | M3 | Notes |
|-----------|----|----|----|----|
| Task Parser | ✓ | ✓ | ✓ | Unchanged |
| Memory Reader | - | ✓ | ✓ | Upgraded: LLM reads memory to inform strategy |
| Skill Loader | - | ✓ | ✓ | Unchanged; LLM reads skill rules |
| **Planner** | Rule | Rule | **LLM** | New: LLM decomposes research task |
| Hybrid Retriever | ✓ | ✓ | Tool | Tool-ified for LLM invocation |
| Reranker | ✓ | ✓ | Tool | Tool-ified for LLM invocation |
| **Evidence Evaluator** | Rule | Rule | **LLM** | New: LLM reasons sufficiency, decides rewrite |
| Query Rewriter | Rule | Rule | Tool | Stays deterministic; LLM calls it when needed |
| Numeric Extraction | - | ✓ | Tool | XBRL/narrative extractors as tool set |
| Numeric Verification | - | ✓ | Tool | Deterministic calculations, never LLM-driven |
| **Synthesizer** | Template | Template | **LLM** | Upgraded: LLM generates prose, guardrailed |
| **Critic** | Rule | Rule | **LLM** | Upgraded: LLM evaluates, with repair fallback |
| Repair | - | Rule | Tool | Stays deterministic |
| Trace Logger | ✓ | ✓ | Enhanced | Records LLM thought/action/observation steps |

---

## 2. ReAct Control Flow

### 2.1 High-Level ReAct Loop

```
THOUGHT (LLM internal reasoning):
  "What evidence do I have so far? What's missing? 
   Can I verify the claim, or should I retrieve more?"

ACTION (LLM decides which tool to invoke):
  - If insufficient evidence → invoke hybrid_retrieve
  - If evidence present → invoke xbrl_fact_lookup or verify_numeric_claim
  - If ready to write → invoke synthesize
  - If critique needed → invoke critic

OBSERVATION (Tool result):
  - Retrieval returns chunks + citations
  - Verification returns status (verified/unsupported/low_confidence)
  - Synthesis returns brief text (guardrail-checked)
  - Critique returns repair suggestions or approval

THOUGHT (LLM reflects on observation):
  "Given this result, do I have enough to conclude? 
   Should I revise the query and retrieve again?"

→ Loop until STOP decision: brief is complete and verified.
```

### 2.2 Detailed ReAct Decision Tree

```
START: LLM receives task spec, memory, skill, prior evidence

LOOP (max_iterations = 3):
  ┌─ THOUGHT: Analyze current evidence state
  │   - Which sectors/years covered?
  │   - Which metrics verified?
  │   - Are there gaps aligned to skill requirements?
  │   - Can I make conclusions with what I have?
  │
  ├─ DECISION: Next action?
  │   ├─ If: Critical evidence gap (missing year/section)
  │   │    → ACTION: hybrid_retrieve(refined_query)
  │   │       OBSERVATION: New chunks + reranked evidence
  │   │       THOUGHT: Is evidence now sufficient?
  │   │
  │   ├─ If: Enough evidence, need to verify numerics
  │   │    → ACTION: xbrl_fact_lookup(metric, year) for each metric
  │   │       OBSERVATION: Fact with confidence/source
  │   │       If: Both years available
  │   │          → ACTION: verify_numeric_claim(old_value, new_value)
  │   │             OBSERVATION: Verification result (verified/unsupported)
  │   │
  │   ├─ If: Evidence sufficient, ready to write brief
  │   │    → ACTION: synthesize(task, evidence, verified_facts)
  │   │       OBSERVATION: Brief markdown + inline verification status
  │   │       → ACTION: critic(brief, verification_results)
  │   │          OBSERVATION: Critique with repair suggestions or APPROVED
  │   │          If: Repairs needed → invoke repair tool → resynthesizes
  │   │          Else → STOP: Return brief
  │   │
  │   └─ If: Evidence insufficient after max_iterations
  │        → STOP: Return brief with limitations note
  │
  └─ Loop back to THOUGHT with updated evidence
```

### 2.3 Stopping Conditions

- **Success**: Critic approves brief (all claims supported/verified)
- **Iterations exhausted**: max_iterations reached → return brief with "limited evidence" caveat
- **Numeric mismatch**: LLM tries to include unverified number → critic blocks → repair tool fixes → resynthesizes
- **User timeout**: Configurable token budget per run (fallback: return partial brief)

---

## 3. Tool Layer Definition

### 3.1 Tool Catalogue (LLM-Callable)

Each tool is a Python function wrapped for Bedrock tool-use schema.

#### Retrieval Tools

**`hybrid_retrieve(query: str, top_n: int = 40) → List[Chunk]`**
- Invokes M1 HybridRetriever (BM25 + vector + RRF)
- Returns ranked chunks with chunk_id, section_type, fiscal_year, text, citation
- LLM calls when evidence gap detected

**`rerank(query: str, candidates: List[Chunk], top_k: int = 12) → List[Chunk]`**
- Applies M1 Reranker
- Returns top-k reranked evidence
- Called automatically after retrieve (LLM doesn't invoke directly; part of retrieve pipeline)

#### Evidence Verification Tools

**`xbrl_fact_lookup(metric_name: str, fiscal_year: int) → Fact | None`**
- Queries M2 fact store for XBRL debt metrics
- Returns NumericFact (value, unit, source, confidence)
- LLM calls for each metric needed

**`narrative_fact_lookup(metric_name: str, fiscal_year: int, evidence_chunks: List[Chunk]) → Fact | None`**
- Extracts liquidity facts from retrieved narrative chunks
- Returns NumericFact with high_confidence requirement
- LLM calls for narrative-only metrics

**`verify_numeric_claim(metric_name: str, old_year: int, new_year: int) → VerificationResult`**
- Deterministic: Calls M2 NumericVerifier
- Returns status (verified/unsupported/low_confidence) + calculations
- LLM never modifies logic; only calls and interprets result

**`calculate_change(old_value: float, new_value: float) → Dict[str, float]`**
- Deterministic: Returns {delta, pct_change, direction}
- Never invoked by LLM directly; used internally by verify_numeric_claim
- Exposed for transparency in trace

#### Memory / Skill Tools

**`query_memory(topic: str = "debt_liquidity") → Dict[str, Any]`**
- Returns: {useful_sections, successful_queries, verified_metrics}
- LLM reads this early in research; informs retrieval strategy
- No write; memory updates happen post-run

**`load_skill() → ResearchSkill`**
- Returns: {required_evidence_categories, required_sections, rules}
- LLM reads to understand evidence expectations
- No modification by LLM

#### Synthesis / Evaluation Tools

**`synthesize_draft(task: TaskSpec, evidence: List[Chunk], verified_facts: List[VerificationResult]) → Brief`**
- LLM calls to generate initial draft
- Input: task spec, retrieved chunks, verified numeric results
- Output: Markdown brief with inline [citations] and [verification status]
- Guardrail: Template includes "Source: [verified_fact_id]" for every number

**`critic_evaluate(brief: Brief, verification_results: List[VerificationResult]) → CriticResult`**
- Checks: Every number in brief has corresponding verified fact
- Returns: {approved: bool, unsupported_claims: [List], repair_suggestions: [List]}
- If unsupported numbers found → suggests repair (regenerate that section)
- LLM reviews result and decides: accept or invoke repair

**`repair_brief(brief: Brief, unsupported_claims: [List]) → Brief`**
- Deterministic rule engine: Removes unsupported claims, rewrites section
- Returns: Cleaned brief (no unverified numbers)
- LLM can then resynthesizes if needed, or accepts repaired brief

#### Utility Tools

**`write_workpaper(artifact_name: str, content: Any) → Path`**
- Writes numeric_facts, numeric_verification, evaluation_summary to run workspace
- Called by system (not LLM) post-loop

**`get_trace_snapshot() → Dict`**
- Returns current trace state (for LLM to review mid-loop if needed)
- Not used in baseline; available for advanced debugging

### 3.2 Bedrock Tool Calling Schema

Example tool definition for Bedrock `tool_use` block:

```json
{
  "toolUseBlock": {
    "toolUseId": "retrieve_001",
    "name": "hybrid_retrieve",
    "input": {
      "query": "Ford 2023 2025 10-K debt long-term debt maturities liquidity",
      "top_n": 40
    }
  }
}
```

LLM returns structured tool calls; loop invokes each and streams result back via `tool_result` block.

---

## 4. Neurosymbolic Guardrails: The Key Differentiator

### 4.1 Core Principle

```
LLM decides WHAT, WHERE, HOW to say it.
Deterministic tools decide IF it's numerically true.

Every number in final brief must be:
  (a) Generated by deterministic tools, OR
  (b) Cited from verified facts, OR
  (c) Blocked by critic
```

### 4.2 The Guardrail Pipeline

**Guardrail 1: Synthesis Template**

Synthesizer prompt includes:

```markdown
You are writing a credit research brief. Rules:
1. For EVERY numeric claim, cite the source:
   "Company debt decreased from $19.9B [verified: xbrl_fact_2023_debt] 
    to $21.9B [verified: xbrl_fact_2025_debt]"
2. If you cannot cite a source, do NOT state the number.
3. Mark uncertain claims with [LOW_CONFIDENCE: reason].
```

→ Forces LLM to cite before stating; makes unverified numbers visible.

**Guardrail 2: Critic Verification**

Critic regex-scans brief for:
- `[verified: ...]` tags
- `[LOW_CONFIDENCE: ...]` tags
- Numeric values without tags (red flag)

```python
def critic_check(brief_text: str, verified_facts: Dict[str, bool]) -> CriticResult:
    # Find all numeric patterns in brief
    # For each, check: is source in verified_facts[source_id]?
    # If: not verified AND not low_confidence → add to unsupported_claims
```

Blocks brief if: "Found $42B without verified source"

**Guardrail 3: Repair Enforcement**

If critic finds unsupported claims:
```
repair_brief(brief, unsupported_claims):
  for claim in unsupported_claims:
    if claim.type == "numeric":
      REMOVE claim from brief
      ADD: "[Numeric claim removed: insufficient verification]"
  return repaired_brief
```

LLM **cannot override** repair; final brief is guaranteed clean.

**Guardrail 4: Trace Auditability**

Every numeric value in final brief links back to:
- Tool call that extracted it
- Verification step that certified it
- Trace entry proving LLM made that decision

Example trace step:

```json
{
  "state": "LLM_DECISION",
  "thought": "Debt increased from 2023 to 2025; need to verify delta",
  "action": "verify_numeric_claim",
  "tool_call": {
    "metric": "company_debt_excluding_ford_credit",
    "old_year": 2023,
    "new_year": 2025
  },
  "observation": {
    "status": "verified",
    "delta": 1.975,
    "verified_fact_2023_id": "F_2023_debt_001",
    "verified_fact_2025_id": "F_2025_debt_003"
  }
}
```

Audit trail is complete; reviewer can trace every number.

### 4.3 Guardrail Violations & Recovery

| Violation | Detection | Recovery |
|-----------|-----------|----------|
| LLM invents number without source | Critic regex scan | Repair removes claim |
| Cited source doesn't exist | Fact store lookup fails | Critic flags; repair removes |
| Verification says "low_confidence" but brief says "certain" | Critic finds mismatch | Repair downgrades to caveat |
| LLM claims "delta increased 50%" but facts show "decreasing" | Critic compares direction | Repair removes claim; resynthesizes |

---

## 5. ReAct Prompts & LLM Behavior

### 5.1 System Prompt (Base)

```markdown
You are an AI credit research analyst. Your task is to analyze a company's 
debt and liquidity risk by retrieving evidence from SEC filings, verifying 
numeric facts using deterministic tools, and writing a brief.

**Critical Rules:**
1. Think step-by-step. Before acting, state what you know and what you need.
2. Use ONLY the tools provided. Do NOT invent calculations.
3. Every number in your final brief MUST be verified by a tool.
4. If you cannot verify a number, do NOT state it.
5. If the critic rejects your brief, accept the repair and integrate feedback.
6. You have a max of 3 retrieval iterations. After that, write what you have.

**Available Tools:**
- hybrid_retrieve(query) → [Chunk]
- xbrl_fact_lookup(metric, year) → Fact | None
- verify_numeric_claim(metric, old_year, new_year) → VerificationResult
- synthesize_draft(task, evidence, verified_facts) → Brief
- critic_evaluate(brief, verification_results) → CriticResult
- repair_brief(brief, unsupported_claims) → Brief

Go.
```

### 5.2 In-Loop Prompts

**Evidence Evaluator Prompt (LLM decides: retrieve more or verify?)**

```markdown
Current State:
- Retrieved evidence: {list of section_types and fiscal_years}
- Required by skill: {required_evidence_categories}
- Iterations used: {current} / 3

Question: Should I:
(a) Retrieve more evidence (if gaps exist), OR
(b) Verify the numeric facts I have, OR
(c) Write the brief (if I have enough)?

Reason through the gaps. Then decide ONE action.
```

**Synthesis Prompt**

```markdown
Using the retrieved evidence and verified facts below, write a brief that:

1. Summarizes key findings on debt/liquidity risk change from 2023 to 2025.
2. Cites every piece of evidence: [chunk_id](url)
3. For numeric claims, cites verified facts: [verified: fact_id]
4. Marks uncertain claims: [LOW_CONFIDENCE: reason]
5. Does NOT state any number without a verified source.

Verified facts:
{verified_facts.to_dict()}

Evidence chunks:
{evidence.summary()}

Output: Markdown brief (2-3 pages).
```

### 5.3 Prompt Injection Prevention

- Tool inputs are parameterized (user query → escaped before use)
- Tool outputs are parsed as JSON, not raw text eval
- LLM tool calls are parsed by schema validator (Bedrock), not string parsing
- Trace is immutable (write-only workpaper)

---

## 6. LLM Failure & Budget Fallback

### 6.1 Failure Modes

| Failure | Detection | Fallback |
|---------|-----------|----------|
| LLM refuses task ("I can't analyze financial data") | API returns refusal | Return error brief; suggest filtering settings |
| Tool returns error (e.g., XBRL fact not found) | Catch exception | LLM notes absence; continues with other facts |
| LLM hallucination (e.g., "debt grew 500%") | Critic catches unverified number | Repair removes; ask LLM to resynthesizes without that claim |
| LLM exceeds token budget mid-loop | Monitor input_tokens + output_tokens | Finish current tool call; skip remaining iterations; write brief from what's verified |
| Critic → Repair → LLM still invents numbers (loop) | Repair called twice without improvement | Force brief (no more retries); add warning to output |

### 6.2 Token Budget & Fallback

```python
def run_agent(task, max_tokens=100000):
    tokens_used = 0
    for iteration in range(max_iterations):
        # LLM thinks + decides action
        response = llm.invoke(prompt, max_tokens=8000)
        tokens_used += response.usage.total_tokens
        
        if tokens_used > max_tokens * 0.8:
            # Warn: approaching limit
            log("Token budget 80% used; will stop after this action")
        
        if tokens_used > max_tokens:
            # Stop: invoke synthesize NOW with current evidence
            log("Token limit exceeded; finalizing brief")
            brief = synthesize_draft(task, evidence, verified_facts)
            return brief
        
        # Continue loop
    return brief
```

Graceful degradation: Brief is always delivered, but completeness may vary.

---

## 7. LLM Reasoning Trace

Every LLM step is recorded:

```json
{
  "iteration": 1,
  "step": "LLM_THOUGHT",
  "timestamp": "...",
  "model": "claude-opus-4-8",
  "input_tokens": 2345,
  "output_tokens": 234,
  "thought_text": "I have 2023 and 2025 liquidity evidence from MD&A. I need debt facts for both years. I should call xbrl_fact_lookup for company_debt_excluding_ford_credit.",
  "metadata": {
    "evidence_sections_present": ["Liquidity and Capital Resources", "MD&A"],
    "metrics_verified_so_far": []
  }
}
```

Then:

```json
{
  "iteration": 1,
  "step": "LLM_ACTION",
  "action": "xbrl_fact_lookup",
  "input": {"metric_name": "company_debt_excluding_ford_credit", "fiscal_year": 2023},
  "observation": {
    "status": "found",
    "value": 19.944,
    "unit": "USD billions",
    "source_detail": {"selected_concept": "DebtLongtermAndShorttermCombinedAmountCompanyExcludingFordCredit"}
  }
}
```

Full audit trail lets reviewers follow LLM's reasoning (and catch errors).

---

## 8. Testing Strategy

### 8.1 What NOT to Test

- LLM accuracy (too variable; not in scope)
- LLM reasoning quality (subjective)
- Whether brief is "good" (requires domain expert)

### 8.2 What TO Test (Guardrails & Determinism)

**Unit Tests**

- Fact lookup returns correct XBRL concepts ✓ (M2)
- Verification calculations are deterministic ✓ (M2)
- Critic regex correctly finds unverified numbers ✓ (new)
- Repair deterministically removes unsupported claims ✓ (new)
- Tool calling schema is valid (Bedrock accepts it) ✓ (new)

**Integration Tests**

- Full ReAct loop with mock LLM (deterministic responses):
  - LLM decides to retrieve → tool returns chunks ✓
  - LLM decides to verify → tool returns verified fact ✓
  - LLM invokes synthesize → returns brief with [verified: ...] tags ✓
  - Critic validates tags → approves or rejects ✓
  
- Guardrail enforcement:
  - LLM writes unverified number → critic catches it ✓
  - Repair removes it → brief is clean ✓
  
- Trace completeness:
  - Every LLM thought/action logged ✓
  - Every tool call traced ✓
  - Trace links numbers back to verification ✓

**Negative Tests**

- Token budget exceeded → brief generated (not timeout) ✓
- Tool returns error → LLM continues with other facts ✓
- LLM refuses task → graceful error response ✓
- Fact store missing metric → LLM notes absence; continues ✓

**Acceptance Test (End-to-End)**

Run same task 3 times with different LLM seeds:
- All three produce valid briefs (no hallucinated numbers)
- All three trace logs are audit-able
- Numeric conclusions are deterministic (same verified facts → same conclusions, even if wording differs)

---

## 9. Implementation Roadmap

### Phase 1: Tool Calling Foundation (1-2 weeks)

1. **Wrap M1/M2 functions as tools**
   - `hybrid_retrieve` → signature + docstring
   - `xbrl_fact_lookup` → signature
   - `verify_numeric_claim` → signature
   - others (synthesize, critic, repair)

2. **Bedrock Tool Calling Integration**
   - Implement `invoke_with_tools()` that:
     - Sends prompt + tool definitions to Claude Opus via Bedrock
     - Parses tool_use blocks from response
     - Invokes corresponding Python function
     - Streams result back to LLM
   - Reuse `financial-dd-agent` patterns (if available) or build from Bedrock docs

3. **Trace Recording**
   - Extend TraceLogger to log LLM steps (thought/action/observation)
   - Capture tool calls + results

4. **Tests**: Tool calling works end-to-end (mock LLM)

### Phase 2: ReAct Loop (2-3 weeks)

1. **ReAct State Machine**
   - Implement loop: THOUGHT → ACTION → OBSERVATION → back to THOUGHT
   - Stopping conditions: success (critic approves), max_iterations, token budget

2. **LLM Decision Points**
   - Evidence Evaluator: Should retrieve more or verify?
   - Synthesis: Generate brief from verified facts
   - Critic: Evaluate brief for guardrail violations

3. **Fallback Handling**
   - Token budget exceeded → finalize gracefully
   - Tool errors → log and continue
   - LLM refuses → return error brief

4. **Tests**: ReAct loop converges (with mock LLM deterministic responses)

### Phase 3: Neurosymbolic Guardrails (1-2 weeks)

1. **Critic Guardrail**
   - Regex scan brief for unverified numbers
   - Check citation tags: `[verified: fact_id]` must exist in fact store

2. **Repair Tool**
   - Remove unsupported claims
   - Regenerate brief sections (or simple removal + caveat)

3. **Synthesis Prompt**
   - Enforce `[verified: ...]` citation requirement
   - Add `[LOW_CONFIDENCE: ...]` for uncertain facts

4. **Tests**: Critic blocks hallucinated numbers; repair removes them

### Phase 4: LLM Synthesis & Reflection (2 weeks)

1. **LLM Synthesizer (replace template)**
   - LLM writes prose brief (not template-driven)
   - Guardrail: Must cite verified facts

2. **LLM Critic (replace rule-based)**
   - LLM evaluates: Are claims supported?
   - Guardrail: Deterministic numeric check (critic tool, not LLM opinion)

3. **Integration**
   - Synthesizer + Critic work end-to-end
   - Repair loop handles unsupported claims

4. **Tests**: Synthesizer respects guardrails; critic catches violations

### Phase 5: Integration & Acceptance (1 week)

1. **Full M3 End-to-End**
   - Same task as M2 demo
   - Run with real Claude (via Bedrock)
   - Verify: Brief is generated, trace is complete, numbers are verified

2. **Acceptance Tests**
   - Multiple runs same task → deterministic conclusions
   - Trace audit trail is complete
   - Guardrails enforce (no unverified numbers in final brief)

3. **Documentation**
   - ReAct prompt engineering guide
   - Tool calling patterns
   - Troubleshooting guardrail failures

---

## 10. Comparison to Original Harness Design

### Original Vision (from M1/M2 PRD)

> Deterministic retrieval loop with numeric verification and audit trail.

### M3 Realization

| Aspect | Original | M1 | M2 | M3 |
|--------|----------|----|----|-----|
| Retrieval | BM25 + Vector | ✓ | ✓ | ✓ Tool-ified |
| Reranking | Local embedding | ✓ | ✓ | ✓ Tool-ified |
| Evidence Evaluation | Rule-based sufficiency check | ✓ | ✓ | **LLM + Guardrail** |
| Query Rewrite | Rule-based (coverage gaps) | ✓ | ✓ | ✓ Rule engine (now a tool) |
| Numeric Verification | Deterministic calculations | - | ✓ | ✓ **Tool-only** |
| Brief Synthesis | Template-driven | Template | Template | **LLM + Verification** |
| Critic/Reflection | Rule-based | Rule | Rule | **LLM + Guardrail** |
| Memory/Skills | - | - | ✓ | ✓ LLM-aware |
| Trace/Auditability | Full logging | ✓ | ✓ | ✓ **LLM steps traced** |

M3 **completes the vision**: LLM-driven reasoning + decisions, guardrails protect numeric integrity, full audit trail.

---

## 11. MCP (Model Context Protocol) — Roadmap Item, Not M3

### Current State

- All M1/M2 tools are Python functions
- M3 wraps them for Bedrock tool calling
- LLM invokes via Bedrock API (not MCP yet)

### Future (Post-M3 Acceptance)

Create MCP server exposing:
- `hybrid_retrieve` (read-only; search)
- `verify_numeric_claim` (read-only; deterministic)
- Tool definitions match Bedrock schema (smooth upgrade)

MCP allows:
- Other LLMs (Claude via Claude.ai, external Claude instances) to call same tools
- Integration with other agents / multi-agent workflows
- Standardized tool discovery

**Decision**: Defer MCP to post-M3. M3 focuses on ReAct + guardrails (Bedrock native). MCP is a scaling play, not a core differentiator. Resume brief does not include MCP.

---

## 12. Success Criteria (Acceptance)

### Minimum Viable M3

1. **Tool calling works**
   - Bedrock tool_use → Python function → result to LLM ✓
   - All major tools wrapped (retrieve, xbrl_lookup, verify, synthesize, critic) ✓

2. **ReAct loop completes**
   - LLM reasons → decides action → observes result → repeats ✓
   - Loop respects max_iterations and token budget ✓

3. **Guardrails enforce**
   - Every number in final brief is verified or cited ✓
   - Critic catches hallucinated numbers ✓
   - Repair removes unsupported claims ✓

4. **Trace is complete**
   - Every LLM thought/action logged ✓
   - Numbers can be traced back to verification ✓
   - Audit trail is reviewable ✓

5. **M2 demo task works**
   - Same task (Ford debt/liquidity 2023→2025) as M2 ✓
   - Brief is generated, numeric conclusions verified ✓
   - Trace is clean and auditable ✓

### Plus (Nice to Have, Not Required)

- LLM-driven query rewrite (currently rule-based) — deferred
- Multi-step reasoning prompts — refined over time
- LLM memory/skill influence on strategy — low priority

---

## 13. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| LLM hallucination (invents numbers) | Brief is wrong | Guardrail: Critic blocks; repair removes |
| Tool calling errors / parsing fails | Loop breaks | Fallback: Catch exception; finalize brief |
| Token budget exceeded | Incomplete brief | Graceful: Return what's verified; add caveat |
| LLM gets stuck in repeat loop (calls same tool) | Timeout | Max iterations; detect repeated actions |
| Bedrock API errors | Loop fails | Retry logic (exponential backoff); fallback |
| Trace bloat (too verbose) | Storage/perf issues | Summarize non-critical steps; store JSON (compact) |

---

## 14. Next Steps (Post-Design Review)

1. **User review** of this design (especially ReAct flow + guardrails)
2. **Address feedback** → refine architecture
3. **Start Phase 1** (tool wrapping + Bedrock integration)
4. **Checkpoint**: Phase 1 acceptance (tool calling works)
5. **Continue Phases 2-5** in sequence

---

## Appendix: ReAct Prompt Example (Full)

```markdown
You are an expert credit analyst. Analyze this company's debt and liquidity risk.

CRITICAL RULES:
1. Think before acting. Say what you know, what you need, and which tool to call.
2. Use ONLY provided tools. Never invent calculations or facts.
3. Every number you write must be verified by a tool. If you can't verify, don't write it.
4. If the critic rejects your brief, accept the repair without argument.
5. You have 3 retrieval iterations. After that, finalize based on what you have.

TASK:
How did {company}'s {risk_theme} change from {year1} to {year2}? What evidence supports it?

AVAILABLE TOOLS:
1. hybrid_retrieve(query: str) → List[Chunk]
   - Retrieves evidence from SEC filings
   - Returns chunks with section_type, fiscal_year, text, citation
   
2. xbrl_fact_lookup(metric: str, year: int) → Fact | None
   - Looks up XBRL debt metrics
   - Returns value, unit, source, confidence
   
3. verify_numeric_claim(metric: str, year1: int, year2: int) → VerificationResult
   - Calculates delta and verifies claim
   - Returns status (verified/unsupported) + calculations
   
4. synthesize_draft(task: str, evidence: List, verified_facts: List) → Brief
   - Generates brief from evidence and facts
   - Must cite every number: [verified: fact_id]
   
5. critic_evaluate(brief: str, verified_facts: List) → CriticResult
   - Checks brief for unverified numbers
   - Returns {approved, unsupported_claims, repairs}
   
6. repair_brief(brief: str, unsupported_claims: List) → Brief
   - Removes unsupported claims, cleans brief
   - Returns verified-clean brief

START:

Current memory: {memory}
Skill requirements: {skill.required_evidence_categories}
Current evidence: {evidence_summary}

THOUGHT: What evidence do I have? What am I missing?

[Your reasoning here]

ACTION: [Which tool to call? {tool_name: args}]

Proceed.
```

---

**Design Complete. Ready for review.**
