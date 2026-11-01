---
name: deep-research
description: >-
  Conduct systematic deep research on technical topics with source verification,
  triangulation, and citation-backed reports. Use when the user asks for deep
  research, comprehensive analysis, technology comparison, trend analysis, state
  of the art review, or architecture evaluation. Not for simple lookups,
  debugging, or questions answerable with 1-2 searches.
---

# Deep Research

## Core Purpose

Deliver citation-backed, verified research reports through a structured
multi-phase pipeline. Every factual claim must be traceable to a source.

**Autonomy Principle:** Operate independently through retrieval and synthesis.

> **CRITICAL — Phase 0 is mandatory.** Your FIRST response to the user MUST
> be clarifying questions based on ambiguity analysis (Phase 0). Do NOT run
> any searches, launch any subagents, or begin Phase 1 until the user has
> answered. Skipping Phase 0 is the single most common failure mode of this
> skill. Even for precise prompts, confirm your assumptions before starting.

After Phase 0, pause **zero** more times: all subsequent phases (1 through 5)
run **without pausing**. Show the research plan (Phase 1) in the output for
transparency, but do not wait for confirmation — proceed directly to retrieval.

---

## Decision Tree

```
Request received
├── Simple lookup (1-2 searches enough)?  → STOP: use normal WebSearch
├── Debugging / code fix?                 → STOP: use standard agent mode
└── Complex analysis needed?              → CONTINUE ↓

Depth selection
├── standard → 2-3 subagents, ~4.000 words,  phases 0-1-2-3-[QG]-3.1-3.5-4-5  [DEFAULT]
└── deep     → 4-6 subagents, 6.000+ words,  phases 0-1-2-3-[QG]-2-3-3.1-3.5-4-5

[QG] = Quality Gate: skip next wave if source targets already met
```

If the user does not specify depth, default to **standard**.

---

## Agent Architecture

This skill uses a **lead-agent / subagent** pattern. The main (lead) agent
orchestrates the pipeline; subagents handle retrieval, verification, and
(in deep mode) synthesis. Every phase has a clear owner.

### Agent Roles

| Role | Agent | Purpose |
|------|-------|---------|
| **Orchestrator** | Main agent | Clarify, scope, plan, triangulate, critique, write report |
| **Retrieval** | Subagent (Role 1) | Broad search across assigned key areas (Wave 1) |
| **Gap-Fill** | Subagent (Role 2) | Targeted search for specific evidence gaps (Wave 2+) |
| **Verification** | Subagent (Role 3) | Citation spot-check: do sources support their claims? |
| **Synthesis** | Subagent (Role 4) | Draft area summaries with citations (deep only) |

### Agent Assignment per Phase

| Phase | Standard | Deep |
|-------|----------|------|
| 0 Clarify | Main | Main |
| 1 Scope | Main | Main |
| 2 Retrieve (Wave 1) | 2-3 Retrieval SA | 4 Retrieval SA |
| 2b Retrieve (Wave 2+) | 1 Gap-Fill SA | 1-2 Gap-Fill SA |
| 3 Triangulate | Main | Main |
| 3.1 Citation Check | 1 Verification SA | 1 Verification SA |
| 3.5 Outline Refine | Main | Main |
| 4 Critique | Main | Main |
| 5 Write Report | Main | Main (assisted by 1 Synthesis SA) |

**Key design decisions:**
- The **Verification Agent runs as a subagent in both standard and deep**,
  freeing the main agent's tool-call budget for coordination and writing.
- The **Gap-Fill Agent** has a sharper prompt than the generic Retrieval
  Agent — it knows what is missing and searches specifically for that.
- In **deep mode**, a Synthesis Agent pre-drafts area summaries before the
  main agent writes the final report. This reduces the main agent's
  synthesis load and produces more consistent cross-referencing.
- The main agent **never runs WebSearch/WebFetch in Phase 2**. All retrieval
  is delegated to subagents so the main agent preserves its tool-call
  budget for Phases 3-5.

### Subagent Model Selection

Use `model: "fast"` for Retrieval (Role 1) and Gap-Fill (Role 2) subagents
— they search and extract, no deep reasoning needed. This reduces cost and
latency. Use the default model (no `model` parameter) for Verification
(Role 3) and Synthesis (Role 4) subagents, which require careful judgment.

### Source Credibility Tiers

Subagents (Retrieval + Gap-Fill) tag every source with a credibility tier
at extraction time. This costs zero extra tool calls — the agent already
reads the URL, author, and content. Phase 3 uses the tiers for confidence
assignment.

| Tier | Label | Examples |
|------|-------|----------|
| **1** | Authoritative | Peer-reviewed journals (arxiv, ACM, IEEE), official documentation, established research labs (Microsoft Research, Google Research), recognized industry authorities (Fowler, Thoughtworks Radar, DORA/State of DevOps) |
| **2** | Credible | Engineering blogs from established companies (Netflix, Spotify, Airbnb tech blogs), conference talks (QCon, STAREAST, SeleniumConf), well-known practitioners with published track record |
| **3** | Supplementary | Personal blogs, Medium posts, Reddit/HN discussions, vendor marketing content, undated articles, sources with no identifiable author |

**Tagging rule:** Each source in the source list gets a `Tier: 1/2/3` tag.
Phase 3 uses tiers for confidence: **`[High]` requires at least one Tier 1
or Tier 2 source. Three Tier 3 sources alone = `[Medium]` maximum.**

---

## Tool Constraints & Subagent Strategy

A single agent turn has limited tool-call budget and a finite context window.
**Subagents bypass these limits:** each subagent (spawned via the `Task` tool)
gets its own tool budget and isolated context. Run multiple subagents in
parallel by issuing several `Task` calls in a single message.

### Scaling with Subagents

| Depth | Subagents | Effective tool calls | Source target |
|-------|-----------|----------------------|---------------|
| standard | 2-3 parallel | ~75 | 15-25 |
| deep | 4 parallel | ~100 | 30-50 |

### How it works

1. **Phase 0 + 1** run on the **main agent** (clarify, scope, plan).
2. **Phase 2** splits key areas across **parallel subagents**. Each subagent
   gets a clear brief:
   - Assigned key areas (e.g. "Areas 1-2" vs. "Areas 3-4")
   - The search terms relevant to its areas
   - Instructions to return a structured source list with extracts
3. Main agent **collects** subagent results, deduplicates sources, runs
   Phase 3 (triangulate), and identifies gaps.
4. If gaps remain, a **second wave** of Gap-Fill subagents fills them.
5. **Phase 3.1** delegates citation spot-check to a Verification subagent.
6. **Phase 5** (write) runs on the main agent. In deep mode, a Synthesis
   subagent pre-drafts area summaries first.

### Subagent prompt templates

#### Role 1: Retrieval Agent (Wave 1 — both depths)

```
You are a research retrieval agent. Your task:

Topic: [research question]
Your assigned areas:
  - [Area N]: [sub-questions]
  - [Area M]: [sub-questions]

Search terms to start with: [list]

Budget: max 8 WebSearch + 5 WebFetch calls. If you have not found
sufficient sources after these calls, return what you have — do not
loop indefinitely. Keep your full response under 2000 words.

Source credibility tiers — assign one per source based on domain,
author, and content signals:
  Tier 1 (authoritative): Peer-reviewed, official docs, research labs,
    recognized authorities (Fowler, DORA, Thoughtworks Radar)
  Tier 2 (credible): Established company engineering blogs, conference
    talks, well-known practitioners
  Tier 3 (supplementary): Personal blogs, Medium, Reddit/HN, vendor
    marketing, undated or anonymous content

Instructions:
1. Run 4-6 WebSearch calls (parallel where possible).
2. For the 3-5 most relevant results, fetch full pages with WebFetch.
3. For each source, extract:
   - Core argument / key data points (2-3 sentences)
   - Author, publication, date
   - Credibility tier (1, 2, or 3)
   - Direct quotes worth citing (if any)
4. For EACH assigned area, write a 3-sentence TAKEAWAY that distills
   the consensus across sources. This takeaway is the main deliverable
   — the lead agent will use it directly as a building block for
   synthesis. Place it before the source list.
5. Return the area takeaways followed by a numbered source list.
   Number sources starting from [START_INDEX] (provided by lead agent).

   ## Area Takeaways
   **[Area N]:** [3-sentence distillation]
   **[Area M]:** [3-sentence distillation]

   ## Sources
   [START_INDEX] Author — Title — URL — Date accessed — Tier: N
   Summary: ...
   Key quotes: ...

Do NOT write the final report. Return takeaways + source list only.
```

#### Role 2: Gap-Fill Agent (Wave 2+ — both depths)

```
You are a targeted gap-fill agent. Your task:

Topic: [research question]
KNOWN GAP: [specific area/claim that lacks evidence]
What we already have: [brief summary of existing sources for this area]
What we need: [specific type of evidence missing — e.g. opposing view,
quantitative data, case study, newer source]

Search terms to start with: [list — tailored to the gap]

Budget: max 5 WebSearch + 3 WebFetch calls.

Source credibility tiers — assign one per source:
  Tier 1 (authoritative): Peer-reviewed, official docs, research labs,
    recognized authorities
  Tier 2 (credible): Established company engineering blogs, conference
    talks, well-known practitioners
  Tier 3 (supplementary): Personal blogs, Medium, Reddit/HN, vendor
    marketing, undated or anonymous content

Instructions:
1. Search specifically for the missing evidence. Do NOT re-cover
   areas that already have sufficient sources.
2. Try alternative framings if direct searches fail (synonyms,
   broader/narrower scope, different language).
3. If the gap cannot be filled after your budget, state this
   explicitly — do NOT pad with tangentially related sources.
4. Number sources starting from [START_INDEX].

Return in the same format as the Retrieval Agent (takeaway + sources
with tier tags).
```

#### Role 3: Verification Agent (Phase 3.1 — both depths)

```
You are a citation verification agent. Your task:

Budget: max 10 WebFetch calls. Keep your response under 1500 words.

You will receive a list of claims paired with their cited sources.
For each claim–source pair:
1. Fetch the source URL with WebFetch (or use the provided extract).
2. Locate the passage that supposedly supports the claim.
3. Rate the match:
   - SUPPORTED — the source directly states or strongly implies the claim.
   - PARTIAL — the source is related but does not fully support the claim.
   - UNSUPPORTED — the source does not support the claim, or contradicts it.
4. For PARTIAL / UNSUPPORTED, suggest a corrected claim or flag for removal.

Return a verification table:
| # | Claim (short) | Source [N] | Rating | Notes |
```

#### Role 4: Synthesis Agent (Phase 5 — deep only)

```
You are a research synthesis agent. Your task:

Budget: no external tool calls needed. Keep your response under 3000 words.

You will receive:
- A deduplicated source list with extracts covering [N] key areas
- Area takeaways from retrieval agents
- Confidence labels from triangulation

For each key area:
1. Identify the consensus view across sources.
2. Note contradictions or minority positions.
3. Draft 2-3 paragraphs of **report-ready prose** with inline [N]
   citations. The lead agent will incorporate these directly into
   the final report — write at publication quality.
4. Flag any area where evidence is thin or one-sided.

Return structured summaries per key area. Do NOT write the executive
summary, TL;DR, action plan, or methodology — the lead agent handles those.
```

### Merge Protocol (Main Agent — after each wave)

When subagent results come back, the main agent merges them as follows:

1. **Renumber sources** — each subagent uses a START_INDEX to avoid
   collisions, but verify there are no gaps or duplicates. The final
   bibliography must be a clean sequential [1], [2], [3]... list.
2. **Deduplicate by URL** — if two subagents found the same source,
   keep the richer extract. Update all [N] references accordingly.
3. **Reconcile conflicting takeaways** — if two subagents produced
   contradictory takeaways for overlapping areas, do NOT silently
   pick one. Instead, note the contradiction as a finding for Phase 3
   (triangulation). Both perspectives must surface in the report.
4. **Preserve tier tags** — carry over the credibility tier from the
   subagent output into the master source list.
5. **Update the master source list** before proceeding to the next phase.

### Additional optimization tips

- **Be selective with WebFetch** — only fetch pages whose search snippet
  looks highly relevant. Not every hit needs a full page load.
- **Leverage WebSearch summaries** — the tool returns snippets. Use these
  as lightweight sources when a full fetch adds no value.
- **Follow citation chains** — if a good article references another source,
  have a subagent search for that source directly.
- **Deduplicate** — subagents may find the same source. Merge in Phase 3.

### Error handling

- **WebSearch returns no results:** Rephrase with broader terms or try
  alternative language. After 3 failed attempts on the same area, note
  the gap explicitly and move on — do not loop indefinitely.
- **WebFetch timeout / 403 / paywall:** Fall back to the WebSearch snippet
  as a lightweight source. Mark it `[snippet only]` in the source list so
  the triangulation phase knows it is lower-quality evidence.
- **Subagent returns empty or poor results:** Launch a replacement subagent
  with revised search terms. Do not retry the identical prompt.
- **Entire wave fails** (all subagents return empty, e.g. due to rate
  limiting or API errors): **Graceful degradation** — produce a reduced
  report using whatever sources have been collected so far. Run Phase 3
  (triangulate) on available evidence, note the degradation in the
  Methodology section, and set all affected sections to `[Low]` confidence.
  If zero sources exist, inform the user and stop.
- **Phase 0 or Phase 1 rejected by user:** Revise scope or plan based on
  user feedback. Do not skip phases or proceed without confirmation.
- **Tool-call budget running low:** Prioritize remaining areas by
  importance. Prefer finishing with fewer but well-triangulated claims
  over broad but shallow coverage.

---

## Phases

### Pre-Phase — CONTEXT LOADING (always)

Before starting a new research run, perform two checks:

**1. Research context file:**
Search for `RESEARCH_CONTEXT.md` in the project root first. If not found,
run a single Glob for `**/RESEARCH_CONTEXT.md`. If it exists, load it.
This file contains persistent user preferences for research (e.g. default
audience, recurring constraints, known terminology). Use it to pre-fill
Phase 0 dimensions — only ask about dimensions the context file does not
already answer.

**2. Existing report check:**
Search for `DEEP_RESEARCH_*.md` files using Glob.
- If a match exists: inform the user, state the file's last-modified date,
  and ask whether to **update** (use existing report as baseline, fill gaps)
  or **replace** (full new run).
- If no match: proceed to Phase 0.

### Phase 0 — CLARIFY (always — MANDATORY first response)

> **STOP.** Do not call WebSearch, WebFetch, or Task before completing this
> phase. Your first message to the user must be clarifying questions — nothing
> else. This is the only user-facing pause in the entire pipeline.

Analyze the user's query for **ambiguity** across five dimensions. For each
dimension where the query is ambiguous, generate **one** clarifying question.
Skip dimensions where the query is already specific.

| # | Dimension | Ask when… | Example question |
|---|-----------|-----------|------------------|
| 1 | **SCOPE** | The topic boundary could be interpreted broadly or narrowly | "Meinst du alle QA-Rollen oder nur Test-Automation?" |
| 2 | **GOAL** | It's unclear what decision or deliverable the research supports | "Soll das eine Entscheidungsvorlage sein oder Wissensaufbau?" |
| 3 | **AUDIENCE** | The reader's technical depth is unknown | "Wer liest den Report — dein Team, Lewis, oder extern?" |
| 4 | **CONSTRAINTS** | Unstated limitations could change the research direction | "Gibt es Tech-Stack-, Budget- oder Timeline-Vorgaben?" |
| 5 | **ASSUMPTIONS** | The query contains implicit assumptions that should be validated | "Du gehst von X aus — soll ich das hinterfragen oder als gegeben nehmen?" |

**Rules:**
- Generate **1-5 questions** (only for ambiguous dimensions).
- If all five dimensions are unambiguous, state which assumptions you are
  making and ask a single confirmation: "Ich verstehe den Scope als X —
  korrekt?" Never skip Phase 0 entirely.
- If a `RESEARCH_CONTEXT.md` was loaded in the Pre-Phase, use it to resolve
  known dimensions before asking.

**Present the questions and STOP. Wait for answers before proceeding.**

### Phase 1 — SCOPE

1. Restate the research question in one sentence, incorporating Phase 0 answers.
2. Break the topic into **4-7 key areas**, each with 3-5 sub-questions.
3. Draft **10-15 search terms** — vary:
   - Language (English + German or domain language)
   - Specificity (broad term + narrow term)
   - Recency markers (e.g. "2025", "2026")
   - **Perspective** — for each key area, include at least one search term
     from a critical or opposing viewpoint (e.g. "[technology] criticism",
     "[approach] failure cases", "[tool] alternatives comparison",
     "[concept] risks drawbacks"). This prevents one-sided retrieval.
4. State the chosen depth (standard / deep).
5. **Assign key areas to subagents** — split areas evenly, assign
   START_INDEX ranges so source numbering won't collide (e.g. Subagent A
   starts at [1], Subagent B at [20], Subagent C at [40]).
6. **Show the plan in the output** for transparency, then **proceed
   immediately** to Phase 2. Do not wait for user confirmation.

### Phase 2 — RETRIEVE (parallel subagents + iterative rounds)

**Wave 1:**
1. Split the key areas from Phase 1 across **2-4 Retrieval subagents**
   (one Task call each, launched in a single message for parallel execution).
2. Each subagent gets:
   - Its assigned key areas + sub-questions
   - Relevant search terms from the Phase 1 plan
   - Its START_INDEX for source numbering
   - The Retrieval Agent prompt template (Role 1)
3. Wait for all subagents to return.
4. **Merge results** using the Merge Protocol (see above).
5. Proceed to Phase 3 (Triangulate) without pausing.

**Wave 2 (if gaps found after Phase 3):**
1. Launch 1-2 **Gap-Fill subagents** (Role 2) targeting thin areas only.
   Each gets: the specific gap, existing sources summary, and what's needed.
2. Merge results into the master source list.
3. Run Phase 3 again.

**Wave 3 (deep mode only, if still gaps):**
1. One final Gap-Fill subagent wave for remaining holes.
2. Final merge + triangulation.

**Source targets after all waves:**

| Depth | Waves | Subagents total | Sources |
|-------|-------|-----------------|---------|
| standard | 1-2 | 2-4 | 15-25 |
| deep | 2-3 | 4-6 | 30-50 |

**Search strategy (applies to all subagents):**
- Alternate broad and narrow queries.
- If a search returns poor results, rephrase — don't repeat the same query.
- Try both English and German terms for EU/DACH-relevant topics.
- Add year qualifiers ("2025", "2026") to find recent content.
- Follow citation chains: if a source references another, search for it.
- **Depth vs. breadth:** If early results reveal that a sub-area is
  well-covered (3+ strong sources), shift remaining tool calls to
  under-covered areas. Do not keep fetching more sources for areas
  that already have high-confidence evidence.

### Phase 3 — TRIANGULATE (after each retrieval round)

1. For each key claim, check: is it supported by **2+ independent sources**?
2. Assign **confidence levels** using both source count and credibility tiers:
   - `[High]` — 3+ independent sources agree, **with at least one Tier 1
     or Tier 2 source**
   - `[Medium]` — 2 sources agree (any tier), or 1 highly authoritative
     Tier 1 source, or 3+ Tier 3 sources agreeing (cap: cannot exceed Medium)
   - `[Low]` — single source only, or only Tier 3 sources with fewer than 3
3. Apply **tiered recency rules**:
   - **Trends, tooling, benchmarks** — strict <18 months. Discard older sources.
   - **Methodology foundations** (e.g. Fowler, Google Testing Blog, Microsoft
     Research, seminal papers) — allowed regardless of age. Mark as
     `[foundational]` in the source list.
   - **In between** — allow up to 36 months if no newer source covers the
     same claim. Note the age explicitly in the report.
4. Note contradictions between sources — these become findings, not errors.
5. Identify **thin areas** (any key area with <2 sources or no `[High]` claims)
   → feed back into the next Phase 2 round via Gap-Fill subagents.

### Quality Gate (between waves)

After each triangulation, check whether another retrieval wave is needed:

```
All key areas have ≥2 sources?
  AND source target met (15+ standard, 30+ deep)?
  AND no key area is entirely [Low] confidence?
  AND at least 1 source per key area represents a critical/opposing view?
    → YES: skip remaining waves, proceed to Phase 3.1
    → NO:  run next wave with Gap-Fill subagents, targeting thin areas only
```

This prevents wasting tool calls when coverage is already sufficient.

### Phase 3.1 — CITATION SPOT-CHECK (both depths)

After triangulation passes, delegate citation verification to a
**Verification subagent** (Role 3). This frees the main agent's tool-call
budget and catches the most common failure mode of deep-research systems
(empirically measured at 40–80% citation accuracy across commercial tools).

1. Select the **5–10 highest-impact claims** in the collected evidence —
   prioritize claims that drive the report's main conclusions.
2. Send the claims + their cited source URLs/extracts to the Verification
   subagent.
3. When the subagent returns its verification table, process the results:
   - **SUPPORTED** — keep as-is.
   - **PARTIAL** — reformulate the claim to match what the evidence says.
   - **UNSUPPORTED** — launch a single Gap-Fill subagent to find a
     replacement source for this specific claim (max 3 WebSearch +
     2 WebFetch). If no replacement found, downgrade to `[Low]`.
4. Log any corrections in the Methodology Appendix of the final report.

### Phase 3.5 — OUTLINE REFINEMENT (both depths)

After triangulation is complete, compare the planned report structure (from
Phase 1) against the actual evidence collected:

1. **Review fit**: Do the planned sections match what the evidence supports?
2. **Adapt if needed**:
   - Add sections for unexpected but well-evidenced findings.
   - Demote or merge sections with insufficient evidence.
   - Reorder by evidence strength and importance.
3. **Document changes**: Note what changed and why (evidence-driven, not
   speculative). Include in the Methodology Appendix of the final report.

**Guardrails:**
- Adaptation must be driven by evidence already collected.
- Do not add sections without supporting sources.
- Do not abandon the original research question — stay on topic.
- Maximum 50% structural change. If evidence pushes beyond 50%:
  1. **Standard mode:** Note the mismatch in Methodology, apply the
     best-fitting structure within the 50% limit, and flag the scope
     issue in Open Questions.
  2. **Deep mode:** **Pause and show the user** the revised outline with
     a short explanation of why the evidence diverges from the original
     scope. Ask whether to (a) proceed with the new focus, (b) narrow
     back to the original scope, or (c) split into two reports. This is
     the **only additional user checkpoint** beyond Phase 0.

### Phase 4 — CRITIQUE (both depths)

Before writing the final report, run a self-critique by asking these
red-team questions about the collected evidence:

1. **What's missing?** — Are there perspectives, geographies, or source types
   (academic, industry, community) that are underrepresented?
2. **What could be wrong?** — Which claims rest on weak evidence? Are there
   logical leaps between sources and conclusions?
3. **What would a skeptic say?** — If someone disagreed with the main findings,
   what would their strongest argument be?

**If critique reveals a critical gap** (not just a nuance):
- Launch 1 Gap-Fill subagent to fill the gap (assign next available
  START_INDEX from the master source list).
- Time-box to 5 tool calls maximum.
- Do NOT restart the full pipeline.

**Output**: A short internal note (not included in the final report) listing:
- Gaps found and whether they were addressed
- Remaining caveats to mention in the report's "Open Questions" section

### Phase 5 — SYNTHESIZE & WRITE

**Deep mode only:** Before writing, launch a **Synthesis subagent** (Role 4)
with the full source list, area takeaways, and confidence labels. The
subagent returns report-ready prose per key area. The main agent incorporates
these into the final report structure.

**Standard mode:** The main agent writes directly from the area takeaways and
source extracts collected during Phases 2-3.

Create the output file: `DEEP_RESEARCH_[TOPIC].md`

#### Required Structure

```markdown
# Deep Research: [Topic]
> Generated [YYYY-MM-DD] | Depth: [standard/deep] | Sources: [N]

## TL;DR
(2-3 sentences: the decision-relevant bottom line. What should the reader
do or know? Written for stakeholders who will not read the full report.)

## Executive Summary
(200-400 words — key findings, no fluff)

## 1. Status Quo [Confidence: High/Medium/Low]
(Current state of practice, with citations [N])

## 2. Emerging Trends [Confidence: High/Medium/Low]
(What is gaining traction in the last 6-12 months, with citations [N])

## 3. Critical Assessment [Confidence: High/Medium/Low]
(Why trends fail in practice, known trade-offs, risks, with citations [N])

## 4. Action Plan
- [ ] [Action 1 — one sentence, concrete and actionable]
- [ ] [Action 2 — ...]
- [ ] ...
(Reference codebase / architecture-documentation.md where applicable)

## 5. Open Questions & Caveats
(What could not be conclusively answered — include unresolved
contradictions and findings flagged by the Critique phase)

## Methodology
(Depth chosen, number of subagents, waves run, outline changes if any,
citation corrections from Phase 3.1, degradation notes if applicable)

## Bibliography
[1] Author — Title — URL — Accessed YYYY-MM-DD — Tier: N
[2] ...

## Source Extracts
(Raw data from subagents — preserved for follow-up sessions)

### [1] Title
- **Summary:** [2-3 sentence extract]
- **Key quotes:** [direct quotes used in the report]
- **Source type:** [academic / industry / blog / docs / community]
- **Credibility tier:** [1 / 2 / 3]

### [2] Title
- ...
```

#### Confidence Labels

Each main section gets a confidence label based on Phase 3 triangulation:

| Label | Meaning |
|-------|---------|
| `[High]` | Core claims backed by 3+ independent, credible sources (at least one Tier 1 or 2) |
| `[Medium]` | Claims backed by 2 sources, or 1 highly authoritative source, or 3+ Tier 3 only |
| `[Low]` | Single-source claims or limited evidence — treat as directional |

Use the labels inline for individual claims too when they diverge from the
section's overall confidence (e.g. a `[High]` section may contain one
`[Low]` sub-claim).

#### Section guidelines

| Section | Focus |
|---------|-------|
| TL;DR | 2-3 sentences: decision-relevant bottom line for stakeholders who won't read the full report |
| Status Quo | Established patterns, current best practice, market adoption |
| Emerging Trends | Conference talks, blog posts, GitHub activity, community buzz |
| Critical Assessment | Failure modes, scalability concerns, complexity trade-offs |
| Action Plan | Markdown checklist (`- [ ]`). Each item: one concrete, actionable step. Tie to **this** project; reference architecture-documentation.md if relevant |
| Open Questions | Honest gaps, unresolved contradictions, Critique-phase caveats |
| Methodology | Transparency: how the research was conducted |
| Source Extracts | Raw subagent data (summary, key quotes, source type, credibility tier per source). Enables follow-up sessions without re-fetching |

---

## Quality Rules

| Rule | Detail |
|------|--------|
| Citation | Every factual claim uses `[N]`, resolved in Bibliography |
| Triangulation | Major claims backed by 2+ independent sources |
| Confidence | Every section labeled `[High]`, `[Medium]`, or `[Low]`; `[High]` requires ≥1 Tier 1/2 source |
| No fabrication | Never invent URLs, authors, or publication names |
| Recency | Tiered: trends/tooling <18 months; methodology foundations allowed regardless of age (mark `[foundational]`); in-between up to 36 months with age noted |
| Prose-first | >=80% flowing text; bullet lists only for enumerations. Exception: Action Plan uses a checklist. |
| Source count | standard: 15-25, deep: 30-50 |
| Minimum length | standard: 4.000 words, deep: 6.000+ |
| Contradictions | Surface them explicitly — don't silently pick a side |
| Critique | Both depths: run Phase 4 red-team before writing |
| Code snippets | Include when they illustrate a pattern; always attribute the source |
| Output language | Write the report in the language of the user's request. Search terms remain multilingual. |
| Citation verify | Both depths: run Phase 3.1 spot-check via Verification subagent |

---

## Output

- Save report to project root: `DEEP_RESEARCH_[TOPIC].md`
- If the topic is project-specific, also note relevant architecture-documentation.md sections.
- After writing, do a self-check: scan for `[N]` references without a matching
  Bibliography entry. Fix before delivering.

---

## When NOT to Use

- Simple factual questions → one WebSearch call is enough.
- Debugging or code fixes → standard agent mode.
- Questions about *this* codebase only → use codebase search tools.
