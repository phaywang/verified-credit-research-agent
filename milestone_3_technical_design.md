# Verified Credit Research Agent - Milestone 3
## LLM-Driven ReAct Agent for Verified Credit Research

**Status**: Design phase (review only, no implementation)  
**Objective**: Upgrade M2's deterministic harness into an LLM-driven ReAct agent while maintaining auditability and numeric accuracy.

**Key Constraint**: Phase 1 acceptance requires **real Bedrock tool calling minimum closure** (invoke → receive tool_use → parse → return tool_result → multi-turn sequence) proven working before Phase 2+ ReAct logic is written.

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

### 1.2 Architecture: LLM Roles vs Deterministic Tools

**LLM Roles** (Agent decision points at each loop stage):
- **Planner**: Decompose task into retrieval strategy
- **Evidence Evaluator**: Analyze evidence sufficiency; decide retrieve/verify/synthesize
- **Query Rewriter**: Generate improved query from coverage gaps (LLM-primary + rule fallback)
- **Synthesizer**: Write brief narrative from evidence + verified facts (guardrailed)
- **Critic**: Evaluate brief semantically + numerically

**Deterministic Tools** (LLM calls these; outputs are deterministic):
- `hybrid_retrieve(query)` → ranked chunks
- `rerank(query, candidates, top_k)` → reranked chunks
- `xbrl_fact_lookup(metric, year)` → NumericFact (XBRL)
- `narrative_fact_lookup(metric, year, chunks)` → NumericFact (text)
- `verify_numeric_claim(metric, old_year, new_year)` → VerificationResult
- `calculate_change(old, new)` → {delta, pct_change, direction}
- `query_memory(topic)` → {useful_sections, successful_queries, verified_metrics}
- `write_workpaper(artifact_name, content)` → Path
- `numeric_guardrail_check(brief_text, verified_facts)` → {blocked_claims, issues}

**Clear Separation**: 
- LLM drives *what to do, when to do it, how to interpret results*
- Tools execute deterministic operations and return structured data
- **Synthesizer and Critic are LLM roles**, not tools to call (no "synthesizer" tool; LLM is the synthesizer)

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

#### Query Rewriting Tool

**`query_rewrite_helper(task: TaskSpec, coverage_gaps: List[str]) → Dict`**
- **LLM-primary rewriter** (NOT a tool that replaces LLM; tool is helper only)
- Returns deterministic rule-based fallback if LLM rewrite fails
- Output: {rewritten_query, reasoning_summary, target_years, target_sections, fallback_used: bool}
- Example: Given gaps ["2023 debt evidence", "2025 liquidity evidence"], outputs structured rewrite with proof of which sections targeted

#### Numeric Guardrail Tool

**`numeric_guardrail_check(brief_text: str, verified_facts: Dict, numeric_verification: Dict) → GuardrailResult`**
- **First layer of critic** (deterministic, before LLM semantic review)
- Scans brief for: amounts ($X billion, X%), percentages ("increased Y%"), comparative claims ("from X to Y")
- For each numeric pattern found:
  - Check: is it bound to a verified_fact ID? (`[verified: fact_id]` tag exists)
  - Check: source exists in `numeric_facts.json`?
  - **Distinguish**: financial numbers (need verification) vs metadata (year, section #, citation count — do NOT require verification)
- Returns: {blocked_claims: [List of unverified numbers], unverified_issues: [List], severity: "block|warn"}
- **Critical precision**: Regex must NOT false-positive on "2023" or "paragraph 4" or "3 sources cited"

#### Repair Tool

**`repair_brief(brief: Brief, blocked_claims: [List]) → Brief`**
- Deterministic rule engine: Removes or downgrades blocked numeric claims
- Returns: Cleaned brief (guardrail-verified, no unverified numbers)
- Tool does NOT regenerate text; strictly removal + caveat insertion ("Numeric claim removed: insufficient verification")

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

### 4.2 Neurosymbolic Guardrails: Two-Layer Critic

**Layer 1: Deterministic Numeric Guardrail**

Tool: `numeric_guardrail_check(brief_text, verified_facts, numeric_verification)` 

Scans brief for all numeric patterns:
- Dollar amounts: `$X billion`, `$X.X billion`, `$X million`
- Percentages: `X%`, `X.X%`
- Comparative claims: "increased from $X to $Y", "declined Y%"
- Changes: "decreased", "increased", "rose", "fell" + adjacent numbers

For each numeric pattern found:

```python
def check_pattern(pattern_text, verified_facts):
    # Is it a financial number (metric)? → requires verification
    if is_financial_metric(pattern_text):
        # Check: [verified: fact_id] tag exists?
        verified_id = extract_verified_tag(pattern_text)
        if verified_id:
            # Does verified_id exist in numeric_verification.json?
            if verified_id in verified_facts:
                return {"status": "verified"}
        return {"status": "blocked", "reason": "no verified source"}
    
    # Is it metadata (year, section #, count)? → do NOT require verification
    elif is_metadata(pattern_text):  # e.g., "2023", "three sources"
        return {"status": "metadata", "no_verification_needed": True}
    
    else:
        return {"status": "unknown"}
```

**Critical distinction** (must NOT false-positive):
- Verify: "Company debt **increased from $19.9B to $21.9B**" → requires [verified: ...]
- Metadata (skip): "Based on **2023** 10-K" → year is context, not claim
- Metadata (skip): "**3** sources cited" → count is metadata, not financial claim

Returns: `{blocked_claims: [List], metadata_found: [List], severity: "block|warn"}`

**Layer 2: LLM Semantic Critic**

**LLM Role: Critic** — After Layer 1 passes, LLM evaluates:

1. **Evidence sufficiency**: Do the cited chunks actually support the claim?
   - Example: Brief says "liquidity pressure increased" → do we have evidence of pressure, or just a number change?
   
2. **Inference validity**: Is the conclusion bounded by evidence, or over-interpreted?
   - Example: "Debt increased 10% year-over-year" ✓ (facts support)
   - Example: "Therefore, Ford faces near-term solvency risk" ✗ (not in evidence)

3. **Management explanation integrity**: Is MD&A quoted accurately or cherry-picked?
   - Example: Management says "Despite debt increase, liquidity remains strong" → brief must include context

4. **Limitations**: Are caveats and boundaries clear?
   - Example: "Verified from 2023 and 2025 10-K debt disclosures; does not include off-balance-sheet obligations"

LLM returns: `{semantic_issues: [List], passes_semantic_check: bool, required_repairs: [List]}`

**Critic Decision**:
```
If Layer 1 blocks (numeric_guardrail) → repair removes claim
Else if Layer 2 LLM-semantic-check fails → LLM suggests repairs
Else → brief approved
```

Both layers must pass. If both pass → brief is safe to publish.

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

Every LLM step is recorded with **summary, not raw thought**:

```json
{
  "iteration": 1,
  "step": "LLM_DECISION",
  "timestamp": "...",
  "model": "claude-opus-4-8",
  "input_tokens": 2345,
  "output_tokens": 234,
  "role": "Evidence Evaluator",
  "reasoning_summary": "Have liquidity evidence (2023 MD&A, 2025 MD&A); missing debt evidence for both years.",
  "decision_basis": [
    "Required by skill: debt + liquidity for both years",
    "Present: liquidity 2023 (MD&A), liquidity 2025 (MD&A)",
    "Gap: debt evidence missing for 2023 and 2025",
    "Action: retrieve debt facts"
  ],
  "decision": "verify_numeric_facts",
  "metadata": {
    "evidence_sections_present": ["Liquidity and Capital Resources", "MD&A"],
    "metrics_verified_so_far": []
  }
}
```

Then action step:

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
  },
  "timestamp": "...",
  "tool_call_id": "xbrl_001"
}
```

**Trace philosophy:**
- `reasoning_summary`: Concise, safe-to-share decision rationale
- `decision_basis`: Structured list of why LLM chose this action (not raw internal reasoning)
- No `thought_text` or raw LLM internal monologue (security + clarity)
- Audit trail links decisions → actions → observations; reviewers can follow logic without seeing internals

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

## 9. Implementation Roadmap: M3-Core → M3-Full

**Phase 1: Tool Calling Foundation (2-3 weeks)** — [VERIFICATION GATE]

1. **Wrap M1/M2 functions as tools** (non-breaking; logic unchanged)
   - `hybrid_retrieve` → signature + docstring
   - `rerank` → signature
   - `xbrl_fact_lookup`, `narrative_fact_lookup` → signatures
   - `verify_numeric_claim`, `calculate_change` → signatures
   - `query_memory`, `write_workpaper`, `numeric_guardrail_check` → signatures
   - **NOT**: Synthesizer, Critic (these are LLM roles, not tools)

2. **Bedrock Tool Calling Integration**
   - Adapt `financial-dd-agent/src/bedrock.py` to M3 (reuse bot3 + ChatBedrockConverse)
   - Implement `invoke_with_tools(prompt, tools)` that:
     - Sends prompt + tool definitions to Claude Opus 4.8 via Bedrock
     - Parses tool_use blocks from response
     - Invokes corresponding Python function
     - Streams result back via tool_result block
     - Supports multi-turn tool loops

3. **Trace Recording (with new structure)**
   - Extend TraceLogger for: reasoning_summary, decision_basis (not raw thought)
   - Record tool_call_id, tool input/output, timestamps

4. **Phase 1 Acceptance Gate** ⚠️ **CRITICAL**:
   - **Real Bedrock tool calling minimum closure**: Invoke → receive tool_use → parse → return tool_result → multi-turn sequence, proven working
   - Test with dummy tool (e.g., echo back query)
   - No mock LLM; use real Claude Opus 4.8
   - If this fails, stop — Phase 2+ code is blind without ground truth
   - Pass criteria: 3 consecutive multi-turn tool calls with correct parsing and result handling

### Phase 2: LLM Synthesizer + Numeric Guardrails (2-3 weeks) — [HIGH VALUE]

1. **LLM Synthesizer (replace template)**
   - Prompt design: "Write brief from evidence + verified facts; cite [verified: fact_id] for every number"
   - LLM generates markdown with inline citations
   - Input: task, evidence chunks, verified_facts.json
   - Output: Markdown brief (2-3 pages)

2. **Numeric Guardrail (Layer 1)**
   - Implement `numeric_guardrail_check()` regex + fact-lookup
   - Distinguish: financial numbers (require verification) vs metadata (year, count — skip)
   - Returns blocked_claims with high precision (no false positives on "2023")

3. **Repair Tool**
   - Deterministic removal of blocked claims
   - Add caveat insertion (no regeneration; stay simple)

4. **Phase 2 Acceptance**:
   - LLM generates brief for M2 demo task
   - Guardrail blocks any unverified numbers
   - Repair cleans brief; final version has zero unverified financials
   - Multiple runs → same verified numbers appear (deterministic)

### Phase 3: LLM Query Rewriter (2 weeks) — [M3 MUST-DO]

1. **LLM Query Rewriter (primary)**
   - Prompt: "Given evidence gaps [list], generate improved query with target_years, target_sections"
   - Output: {rewritten_query, reasoning_summary, target_years, target_sections, fallback_used: false}
   - Fallback: If LLM fails, use rule-based rewrite (M1 logic)

2. **Integration**
   - Evidence Evaluator calls LLM Query Rewriter when gaps detected
   - Re-retrieves with new query
   - Logs decision + reasoning

3. **Phase 3 Acceptance**:
   - LLM rewrites weak query into strong query
   - Rewrite reasoning is clear and auditable
   - No rule fallback needed (unless LLM API fails)

### Phase 4: ReAct Loop Controller ← **[AGENT QUALITY CHANGE POINT]** (3 weeks)

1. **ReAct State Machine**
   - THOUGHT (LLM: Evidence Evaluator) → ACTION (invoke tool) → OBSERVATION (parse result) → back to THOUGHT
   - Stopping: critic approves brief, max_iterations reached, token budget exceeded
   - Clear loop control (no infinite retries)

2. **LLM Decision Roles**
   - **Planner**: Initial strategy from task + skill + memory
   - **Evidence Evaluator**: Is evidence sufficient? Retrieve/verify/synthesize?
   - **Query Rewriter**: Generate improved query from gaps (Phase 3)
   - **Synthesizer**: Write brief from evidence + verified facts (Phase 2)
   - **Critic Layer 1**: Numeric guardrail check (deterministic)
   - **Critic Layer 2**: Semantic evaluation (LLM)

3. **Phase 4 Acceptance** ⚠️ **AGENT PROOF**:
   - Agent autonomously completes M2 demo task: query → retrieve → verify → synthesize → critic → brief
   - No human hand-off at decision points
   - Trace shows clear THOUGHT→ACTION→OBSERVATION chain
   - Agent stops on success (critic approval) or max_iterations
   - Brief is verified-clean (guardrail passed)

### Phase 5: Two-Layer Critic + Full Reflection (2 weeks) — [M3-FULL POLISH]

1. **LLM Semantic Critic (Layer 2)**
   - Implement: Evidence sufficiency, inference validity, management explanation integrity, limitations clarity
   - Returns repair suggestions or approval

2. **Critic Integration**
   - Layer 1 (deterministic guardrail) runs first; if pass → Layer 2 (LLM semantic)
   - Both must pass for brief approval

3. **Fallback Chains**
   - LLM refuses → rule fallback
   - Token budget exceeded → finalize with what's verified
   - Tool errors → graceful degradation

4. **Phase 5 Acceptance**:
   - Critic catches both numeric (guardrail) and semantic (LLM) issues
   - Multiple iterations: agent → critic feedback → repair → re-synthesize → critic → approved
   - Final brief is both numerically verified and semantically sound

---

**Milestones Summary**:
- **Phase 1-4 = M3-Core**: Full verified agent with guardrails (shippable)
- **Phase 5 = M3-Full**: Polished two-layer critic and reflection
- **Phase 1 Gate**: Real Bedrock closure (blocker for all subsequent phases)
- **Phase 4 Gate**: Agent autonomy proof (hard evidence of LLM-driven behavior)

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

## 12. Success Criteria (Acceptance Gates)

### Phase 1 Acceptance: Bedrock Tool Calling Foundation ⚠️ BLOCKER

**Gate Test** (must pass before Phase 2):
```
invoke_with_tools("What is the weather?", tools=[echo_tool])
  → LLM returns tool_use block for echo_tool
  → parse tool_use
  → invoke echo_tool(text)
  → return tool_result to LLM
  → LLM processes result
  → multi-turn (3+ tool calls): succeed
```

Criteria:
- Real Bedrock API call (not mock)
- Correct tool_use block parsing
- Result handling returns to LLM
- No errors; clean closure
- **If this fails: stop; Phase 2+ code is blind**

### Phase 2 Acceptance: LLM Synthesis + Numeric Guardrails

- LLM generates brief for M2 task (Ford debt/liquidity 2023→2025)
- Guardrail blocks any unverified numbers ($X billion without [verified: ...])
- Repair removes blocked claims; brief is clean
- Trace shows tool calls with reasoning_summary + decision_basis (not raw thought)
- Multiple runs → numeric conclusions are deterministic

### Phase 4 Acceptance: Full ReAct Agent ← **AGENT PROOF**

- Agent autonomously completes M2 task end-to-end
- No human hand-off at decision points
- Trace shows THOUGHT→ACTION→OBSERVATION loop
- Agent stops on success (critic approval) or max_iterations
- Brief passes both Layer 1 (numeric) and Layer 2 (semantic) guardrails
- Evidence, verification, synthesis, and criticism are all agent-driven

### Phase 5 Acceptance: M3-Full (Polish)

- Two-layer critic (deterministic + LLM) working together
- Agent handles semantic issues via repair-resynthesis loop
- Fallback chains (LLM refusal, token budget) degrade gracefully
- Full M2 task completed with verified-clean + semantically-sound brief

### M3 Success = M3-Core Acceptance (Phases 1-4)

- Phases 1-4 complete: **M3-Core accepted** (shippable verified agent with guardrails)
- Phase 5 refinements are enhancements, not requirements
- Ready to compare with M2: same task, real agent vs rule engine

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
