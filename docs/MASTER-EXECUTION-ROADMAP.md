# BorsTerminal — Master Execution Roadmap

**Status:** Active master roadmap  
**Date:** 2026-10-07  
**Priority:** This document defines the execution order for the remaining major BorsTerminal work.

> This roadmap is intentionally sequential. For high-risk analytical features, do not start the next item until the current item has been researched, implemented, tested, externally/referentially checked, and explicitly accepted.

---

## 0. Mission and priority hierarchy

The objective is to make BorsTerminal:

1. Data-correct and market-realistic
2. Verified against trusted external references
3. Faithful to the canonical FTS methodology
4. Visually useful directly on the chart
5. Easy enough for a new user to understand
6. Powerful enough for advanced users
7. Extensible toward automation, trading bots, and local ML

### Strategic priority

**The FTS Strategy tab is currently the most important product area.**

Engineering time, research time, UX refinement, chart work, testing, and validation should be disproportionately concentrated on:

- استراتژی FTS
- FTS Funnel
- FTS Process / Stage presentation
- FTS technical and fundamental decisions
- FTS chart annotations
- Master/Portfolio integration of FTS results

The goal is not merely to have an FTS tab that exists. It should become the core decision-support workspace of BorsTerminal.

Do not spend major effort polishing secondary screens while the Strategy FTS workflow, calculations, chart overlays, or parity are still uncertain.

---


# Completeness gates — cross-cutting work that cannot be skipped

The roadmap is not complete merely because the visible feature list is complete. The following foundations are mandatory release gates across Desktop and Android.

## A. Runtime / backend / database integrity

Before declaring a release stable:

- Remove or isolate obsolete backend/runtime processes that can conflict with the current application.
- Verify exactly which backend process/database/snapshot the application is using.
- Verify API routes used by every consumer.
- Eliminate duplicate or shadow implementations that can produce different answers.
- Verify startup/shutdown and offline/online state transitions.
- Verify the canonical data source for market, candle, fundamental, order-book, and FTS outputs.
- Record database/snapshot version and freshness.
- Never declare a data-source issue resolved without reproducing it and identifying the actual cause.

## B. TSETMC consumer-integration completeness

The TSETMC data work is not complete when a backend field exists.

For every newly added/changed TSETMC field:

**source → parser → storage → API → Desktop consumer → Android consumer → UI/result → validation**

must be traced end-to-end.

A field that exists in the database but is not consumed correctly by the application is considered incomplete.

## C. Desktop / Android canonical synchronization

Desktop and Android must be continuously checked for semantic drift.

Required:

- Android must incorporate accepted canonical main-branch engine changes.
- Shared calculations should have one canonical implementation where practical.
- Mobile-only adapters may transform transport/rendering but must not reinterpret FTS semantics.
- Each aggregate Android release must declare its base main commit and mobile-specific commits.
- The final APK must be built from the intended commit and verified against that exact source.
- Offline snapshot freshness must be checked before release.
- Known missing-data or partial-history cases must be visible rather than silently presented as complete.

## D. Chart-engine browser-level integration

A chart feature is not complete because its TypeScript/Python unit tests pass.

For both chart engines and all important drawing tools:

- Verify the actual browser integration path.
- Verify the renderer receives the canonical backend data.
- Verify overlays are visible on the real chart.
- Verify coordinate/time/price mapping.
- Verify zoom/pan behavior.
- Verify daily versus weekly timeframe semantics.
- Verify adjusted versus unadjusted data semantics.
- Verify drawing persistence/interaction where applicable.
- Verify no runtime fetch path points to an unavailable server in offline/mobile contexts.

Use browser-level evidence for acceptance, not source-code inspection alone.

## E. Data freshness / snapshot integrity

For every offline or baked dataset:

- Record build timestamp.
- Record latest candle/data timestamp.
- Record symbol/universe count.
- Record row counts for major datasets.
- Verify that build-time and runtime data dates are internally consistent.
- Detect stale snapshots automatically where practical.
- Investigate unexplained gaps in symbol history.
- Do not treat an intentionally omitted raw table as a missing-data bug without checking the snapshot contract.

## F. Release engineering gate

Every Desktop/Android release must have:

**source commit → tests → build → artifact → checksum → install/run verification → release/tag verification**

No step is implied by another.

Claims such as "built", "released", or "verified" require evidence.

## G. Documentation/source-of-truth hygiene

Before implementing or changing a formula:

- Identify the canonical source.
- Identify conflicting/stale documents.
- Resolve conflicts explicitly.
- Do not mix an old report/spec into a current rule without authorization.
- Preserve owner rulings when they are declared canonical.
- Record meaningful rule changes in the authoritative documentation before changing production logic.

## H. Research/reference discipline

When an external product is used as a reference:

- TradersArena is the primary market/UI parity reference where observable.
- TSE/TSETMC is the primary market-data provenance/reference.
- Rahavard may be used as a technical/chart reference, including visual/indicator behavior available through the user's subscription.
- PDFs and internal docs remain authoritative for BorsTerminal-specific methodology.
- External research explains implementation techniques; it does not silently become a BorsTerminal rule.

For difficult technical features, preserve a research record containing source, date, observation, interpretation, and confidence.

---

# Cross-cutting UX requirement — Stable numeric transitions

Live market numbers must change **smoothly and truthfully**.

Current undesirable behavior: when a value changes, the UI may show strange intermediate numbers before reaching the real value. This is not acceptable.

Example:

1990 → 1993

The user should perceive a calm transition toward 1993, not unrelated or exaggerated transient values.

## Required behavior

- The displayed value must start from the last valid displayed value and converge to the newest authoritative value.
- Intermediate animation values must be mathematically interpolated between old and new values.
- Never generate intermediate numbers outside the old/new interval merely for visual effect.
- For an upward change, the visible transition must not temporarily move downward; for a downward change, it must not temporarily move upward, except when a newer authoritative market tick supersedes the current target.
- Rapid incoming ticks should be coalesced so the user sees a stable transition rather than dozens of competing animations.
- A new authoritative value should update the animation target cleanly rather than restarting from an unrelated number.
- Invalid, stale, null, or semantically incompatible values must not participate in the animation.
- The final rendered number must exactly equal the authoritative value after the transition.
- Formatting, separators, decimals, signs, and units must remain correct throughout the transition.
- Important live figures such as price, volume, value, trade count, queue size, and other rapidly changing metrics should use a consistent transition system rather than independent ad-hoc animations.
- The transition must remain lightweight and must not increase CPU usage significantly during live market updates.
- Respect reduced-motion/accessibility preferences without changing numeric correctness.

## Acceptance

Validate with real rapid market updates and deterministic test sequences such as:

1990 → 1993
1993 → 1990
1990 → 1990
1990 → 2040
2040 → 1990
multiple rapid ticks before an animation completes
null/stale/invalid tick between valid values

The visual result must be calm, monotonic where mathematically appropriate, free of fabricated intermediate values, and end exactly at the latest valid value.

This is a **global UX requirement**, not a cosmetic feature limited to one screen.

---

# 1. P0 — 100% verified parity with TradersArena

**This is the first major gate.**

The objective is to establish a reproducible parity baseline between BorsTerminal and TradersArena wherever TradersArena exposes observable/reference behavior.

This phase comes before new trading automation or advanced ML.

## 1.1 Market data parity

Verify, symbol-by-symbol and field-by-field where applicable:

- Last price
- Close price
- Previous close/reference price
- Open/first price
- High/low
- Volume
- Value
- Trade count
- Buy/sell queues
- Real/legal-person flow
- Market status
- Board/tape state
- Price limits
- Instrument status/classification

No field should be mapped merely because its name appears similar.

## 1.2 Candle parity

Verify against the reference/chart behavior:

- Raw OHLC
- Adjusted OHLC
- Corporate-action handling
- Display close versus adjustment basis
- Daily candles
- Weekly candles
- Missing candles
- Date/session alignment
- Latest candle
- Historical candles
- Volume

Special attention:

- LAST versus CLOSE
- Adjustment basis versus display basis
- Corporate actions/share changes
- Candle integrity around adjustment events

## 1.3 Technical parity

Verify:

- Weekly/daily trend state
- MA/indicator values
- Swing points
- BOS/CHoCH
- Volume behavior
- Support/resistance
- Breakout conditions
- Chart calculations

Every mismatch must be classified as:

BUG / DATA DIFFERENCE / SEMANTIC DIFFERENCE / REFERENCE LIMITATION / UNVERIFIED

Never silently normalize a mismatch.

## 1.4 Order-book/tape parity

Compare:

- Depth
- Queues
- Best bid/ask
- Volume/value
- Market activity
- Observable execution state

Do not fabricate fields that are unavailable.

## 1.5 Parity test protocol

Use a fixed benchmark universe, multiple dates, and both ordinary symbols and difficult/edge-case symbols.

Every parity claim needs evidence.

## 1.5 Filter formula source-of-truth and TSE validation

The filter definitions stored as TXT files under `docs/` are **locked canonical inputs** for the corresponding filter formulas.

Current filter reference files include:

- `docs/الگوی ساعت.txt`
- `docs/حجم مشکوک.txt`
- `docs/فیلتر جت.txt`
- `docs/نقطه زنی.txt`
- `docs/ورود پول هوشمند.txt`
- `docs/ورود پول هوشمند و کد به کد حقوقی به حقیقی.txt`
- `docs/کف روبی صف فروش.txt`

### Hard rule

For every filter:

- Use the referenced TXT file as the canonical formula source.
- Do not add thresholds, conditions, variables, weights, exclusions, time windows, or extra logic that are not supported by that source.
- Do not remove or alter a documented condition merely to increase the number of results.
- Do not silently reinterpret a formula because another website or implementation uses a different convention.
- Any required interpretation or ambiguity must be documented first and resolved against evidence before implementation.
- UI labels and result explanations must correspond to the actual canonical formula.

## 1.6 Configurable filter parameters without changing the canonical formula

The source TXT files remain the canonical definition of each filter, but the application must expose a clear **parameter/settings layer** for values that are legitimately configurable.

This means:

- **Formula structure is locked.**
- **User-configurable parameters are editable.**
- **Canonical/default values come from the TXT source.**
- A changed value is a **configuration override**, not a silent modification of the source formula.

### Required settings model

Every configurable filter parameter should have:

- Parameter name
- Human-readable label
- Type
- Unit
- Minimum/maximum allowed value where meaningful
- Default/canonical value
- Current user value
- Source reference (TXT file / section when applicable)
- Description of what changing it affects
- Reset-to-default action

Example:

```
Volume threshold
Default: 2.0x
Current: 2.5x
Source: docs/حجم مشکوک.txt
[Reset to default]
```

### Where settings must exist

The settings architecture must be available from both:

**تابلوخوانی**
- Keep and improve the existing filter-settings capability.
- Make every configurable field discoverable and understandable.
- Show whether a value is default or customized.
- Make reset-to-default immediate and reliable.

**Strategy FTS**
- Provide an equivalent settings/configuration area for parameters that are explicitly configurable within FTS.
- Clearly separate canonical FTS rules from user-tunable parameters.
- Do not expose parameters that would change a non-configurable FTS rule.

### Presets

Support versioned/user-selectable presets where practical:

- Canonical / Default
- Custom
- Potential future named presets

The **Canonical / Default** preset must always represent the documented source-of-truth configuration.

### Auditability

Every result should be traceable to:

```
Formula version
+
Parameter set/version
+
Current parameter values
+
Data timestamp
```

The UI should make it possible to answer:

**"Why did this symbol match this filter/FTS condition?"**

If a user changes a parameter, the result should visibly indicate that the analysis is using a custom configuration.

### Hard boundary

User settings may change only parameters explicitly designated as configurable.

They must not be used to:

- Add a new condition
- Remove a mandatory condition
- Change the logical structure of the filter
- Override a hard FTS rejection
- Invent a new indicator/threshold not supported by the source
- Turn an unsupported formula into an apparently official/canonical rule

If a value is not explicitly configurable by the source/specification, it stays fixed until the source-of-truth documentation is formally changed.

---

### TSE/TSETMC validation

Filter results must be validated inside the `تابلوخوانی` / market-board experience against observable TSE/TSETMC data.

For each filter, create a repeatable validation set containing:

- Symbols that should match
- Symbols that should not match
- Edge cases
- Required raw TSE/TSETMC fields
- Expected filter output
- Actual BorsTerminal output
- Timestamp/date of the comparison

The comparison must verify both:

1. **Formula correctness** — the filter uses exactly the conditions defined by its TXT source.
2. **Data correctness** — the input fields in BorsTerminal correspond to the relevant TSE/TSETMC fields and semantics.

Any mismatch must be classified as:

`FORMULA BUG / DATA MAPPING BUG / TSE-TSETMC DIFFERENCE / TIMING DIFFERENCE / SOURCE AMBIGUITY / UNVERIFIED`

No filter is considered complete merely because it returns plausible-looking symbols.

### Acceptance gate per filter

Filters are processed **one at a time**:

**Read TXT → map every condition → implement → unit test → run against TSE/TSETMC → inspect results in تابلوخوانی → record evidence → ACCEPT → next filter**

Do not batch-implement all filters and then assume they are correct.
Do not move to the next filter after a failed or unverified one.


### Exit gate

Phase 1 is complete only when:

- Major field semantics are documented
- Candle semantics are locked
- Technical classifications are verified
- Known mismatches are either fixed or explicitly accepted
- A repeatable parity test exists
- No important discrepancy is hidden by UI presentation

**No PASS without evidence.**

---

# 2. P0 — سرخطی / execution timing and queue workspace

After market parity, implement the real product workflow for سرخطی.

## 2.1 Product definition

The first production goal is timing/queue intelligence and queue management, not simulated broker execution.

Scope:

- Queue observation
- Symbol selection
- Timing state
- Rank/position information where measurable
- Latency display
- Queue monitoring
- Readiness state
- Order-preparation workflow

Actual order submission requires a verified broker integration and must not be represented as real execution before that exists.

## 2.2 Required investigation

Research and verify:

- TSETMC market mechanics
- Official exchange rules
- Order timing constraints
- Queue behavior
- Cancellation/replacement semantics
- Network latency implications
- Broker API capabilities
- Operational and legal limits

Research must distinguish documented facts from inference.

## 2.3 Implementation

Build behind a stable contract:

Market state → timing engine → queue state → user action

Potential outputs:

- Queue detected
- Queue side
- Estimated position/rank
- Order timing window
- Latency
- Stale-state warning
- Action readiness

## 2.4 Safety contract

Until a real broker integration is validated:

- No fake “order submitted” state
- No fake execution confirmation
- No claims of guaranteed first-in-queue success
- Mock mode must be clearly labeled
- Paper/simulation mode must be separated from live mode

### Exit gate

سرخطی is accepted only when:

- Market inputs are verified
- Timing calculations are deterministic
- Latency/state failures are visible
- Live versus mock behavior is explicit
- Browser/device behavior is tested
- No UI claim implies an execution that did not occur

---

# 3. P0 — ربات معامله‌گر / automated trading

Only after market and timing foundations are trustworthy.

This is a separate system from the analytical FTS engine.

## 3.1 Scope

Eventually support:

- Strategy definition
- Entry condition
- Invalidation/stop condition
- Position sizing
- Exposure limits
- Risk limits
- Order preparation
- Broker adapter
- Order state machine
- Execution logs
- Audit trail
- Kill switch
- Paper trading
- Live trading

## 3.2 Architecture

Strategy → Signal/Setup → Risk Engine → Execution Planner → Broker Adapter → Order State Machine → Audit/Reconciliation

FTS remains an analytical/rule source; the trading robot must have explicit risk and execution contracts.

## 3.3 Mandatory controls

- Hard exposure limits
- Duplicate-order protection
- Stale-data protection
- Broker disconnect handling
- Partial-fill handling
- Cancellation handling
- Reconciliation
- Emergency stop
- Complete event logs

### Exit gate

No live trading until paper/simulation behavior is verified and broker integration is independently validated.

---

# 4. P0/P1 — FTS Strategy chart intelligence

## The most important long-term workstream

This phase receives **very high investment**.

The objective is to make every important FTS analytical conclusion visible, auditable, and understandable directly on the chart.

### Critical execution rule

Do not implement all overlays at once.

Use exactly this cycle:

**One feature → research → source-of-truth check → algorithm → chart rendering → tests → real-symbol validation → acceptance → next feature**

A feature that is not accepted does not become the foundation for the next feature.

---

# 5. FTS reference hierarchy

For every FTS analytical feature, use this research order.

### Primary sources

- docs/FTS_SPEC.md
- docs/fts-notes/OWNER_RULINGS.md
- docs/جزوه FTS.pdf

### Technical/chart sources

- docs/CANDLE-CONTRACT.md
- docs/CHART-FOUR-PAGES-PARITY.md
- docs/CHART-PARITY-REFERENCE.md
- Relevant technical/chart PDFs in docs/

### External research

Use credible external references to understand implementation techniques and compare conventions, but never use external material to silently rewrite BorsTerminal’s canonical FTS rules.

### Research record

For each feature record:

- Source
- Page/section
- Rule interpretation
- Algorithm choice
- Assumptions
- Edge cases
- Test examples
- Known limitations

---

# 6. Sequential FTS chart backlog

## 6.1 FTS trend structure

First prove on-chart:

- Weekly trend
- Daily trend
- HH/HL
- LH/LL
- Range/neutral
- Structural swing points

The chart must show what the engine actually used.

**Acceptance:** for a fixed symbol/date, displayed trend structure matches engine output and the source-of-truth rule.

---

## 6.2 Canonical swing detector

Build/lock one reusable swing representation.

Requirements:

- Deterministic
- No lookahead for live use
- Explicit confirmation semantics
- Stable historical interpretation
- Reusable by Fibonacci, BOS/CHoCH, double-top/bottom, and other modules

**Acceptance:** benchmark symbols show expected swings with documented reasoning.

---

## 6.3 BOS / CHoCH

Draw:

- Break of structure
- Change of character
- Relevant level
- Confirmation candle/time

Do not show an event unless the underlying engine confirms it.

**Acceptance:** chart marker, backend event, and textual FTS stage agree.

---

## 6.4 FTS Fibonacci

Only after the swing detector is accepted.

Focus specifically on the FTS-defined Fibonacci workflow.

Requirements:

- Identify the correct completed structural impulse
- Select deterministic anchors
- Use the FTS convention and log-scale behavior where required
- Draw the required FTS zones
- Expose anchor time and price
- Avoid arbitrary highest/lowest lookback anchoring
- Avoid lookahead/repaint
- Run the Daily Down branch where the FTS rules require Fibonacci + CHoCH

Required FTS zones:

- 33–40%
- 61.8–70%
- Base 1.0

**Acceptance:** for each benchmark symbol, A/B anchors are visible, zone values are correct, branch is correct, backend and chart agree, and no future leakage exists.

---

## 6.5 Pullback / Jet

After Fibonacci, draw/identify:

- Pullback context
- Jet context
- Historical/static resistance
- Breakout
- Confirmation
- Valid entry window
- Up to 3 working-day entry context where canonical rules require it

Historical jet markers must follow canonical semantics and must not infer unavailable future information.

---

## 6.6 Double Bottom / Bottom structure

Implement and validate:

- Structural low
- Confirmation
- Neckline/relevant level
- Breakout
- Invalidation
- Relation to the daily neutral/down branches as specified by FTS

---

## 6.7 Support/Resistance and FTS points

Render the levels actually used by the FTS process:

- Structural support
- Resistance
- Key historical levels
- Relevant point-hunt context

Do not add decorative levels that the decision engine did not use.

---

## 6.8 Moving-average conditions

Draw and validate:

- MA14 daily
- MA21 volume-related condition
- MA52 weekly
- MA100 daily/weekly

Especially the documented MA14 full-candle exit condition.

The chart must make the exact condition auditable rather than merely drawing generic moving averages.

---

## 6.9 Volume / confirmation

Render:

- Relevant volume behavior
- Volume ratio/context
- MA21 volume relation
- Breakout confirmation volume where used

Do not use undocumented thresholds.

---

## 6.10 Fundamental evidence inside Strategy FTS

Connect fundamental evidence to the technical setup without mixing their semantics.

Show, where appropriate:

- Blocker status
- Key canonical metrics
- Relevant quarterly changes
- Source/date
- Reason for pass/reject

Do not move fundamental rules into chart algorithms.

---

## 6.11 Full FTS Process visualization

After individual modules are accepted, connect them into one coherent chart/process experience:

Weekly → Daily → Branch → Structure → BOS/CHoCH / Pullback / Fib / Jet / Pattern → Fundamental confirmation → FTS result

The chart should answer:

**“Why did FTS reach this decision?”**

---

# 7. FTS chart acceptance protocol

Every FTS feature must pass all of these before the next feature begins.

### Research pass

Read canonical docs, relevant FTS PDF pages, relevant technical/chart PDFs, current implementation, and external references when needed.

### Algorithm pass

Define inputs, outputs, formulas, state transitions, edge cases, and no-lookahead rules.

### Backend pass

The canonical result exists in one place.

### Frontend pass

The chart renders the backend result without silently recomputing the decision.

### Test pass

Unit, integration, and real-symbol benchmark tests.

### Visual pass

Browser screenshot/manual inspection.

### Regression pass

Existing FTS behavior remains stable.

### Acceptance record

Store the verified result before proceeding to the next FTS feature.

---

# 8. P1 — Advanced UI/UX

## Designed for beginners without weakening expert workflows

The design goal:

**A new user understands what to do next without training, while an experienced user can reach advanced information quickly.**

## 8.1 Strategy FTS gets the strongest UX investment

The FTS Strategy workspace should become the flagship experience.

Priorities:

- Clear hierarchy
- Obvious next step
- Readable decision state
- Explainable reasons
- Chart + decision context together
- Minimal navigation friction
- Beginner explanations
- Expert details on demand
- Responsive desktop/tablet/mobile layout

## 8.2 Progressive disclosure

Do not expose every technical detail simultaneously.

Example flow:

FTS PASS → چرا؟ → Trend → Structure → Setup → Fib/CHoCH evidence → Fundamental evidence → Raw technical details

Advanced information remains available without overwhelming first-time users.

## 8.3 First-use experience

Build a lightweight onboarding/help layer explaining:

- Market
- Technical
- Fundamental
- Strategy FTS
- Master
- Portfolio
- Chart controls
- Key FTS decision states

Clarity is more important than visual effects.

## 8.4 Responsive behavior

Validate at:

- 1366×768
- 1920×1080
- Tablet widths
- Common Android portrait widths
- Common Android landscape widths

Do not rely solely on CSS tests; use real browser/device visual validation.

## 8.5 Mobile priorities

Android must preserve the same canonical analytical semantics as Desktop.

Systematically validate:

- Portrait navigation
- Sidebar/inspector behavior
- Chart availability
- Full symbol universe navigation
- Tape usability
- FTS stage navigation
- Funnel visibility
- Offline/online state
- Data freshness indicators

Android is a client of canonical engines, not a separate interpretation of FTS.

---

# 9. P1 — Data freshness and release integrity

Every release must make clear:

- Data snapshot date
- Build date
- Application version
- Source/database version
- Offline snapshot freshness
- Stale-data conditions

Never silently present stale historical data as current.

Every release candidate should have:

- Tests
- Build result
- Exact commit SHA
- Artifact checksum where appropriate
- Release/tag verification
- Installed-version verification

---

# 10. P1 — Full-universe and performance quality

Where the product concept requires the full universe, do not solve scale problems by silently shrinking the universe.

Preferred architecture:

- Full dataset
- Virtualization/pagination
- Indexed search
- Efficient filtering
- Bounded rendering
- Explicit user-selected limits where appropriate

For the FTS Funnel especially:

- Preserve the full candidate universe
- Use virtualization
- Avoid hidden 60/120-symbol caps unless explicitly part of a canonical rule

Performance optimization must not remove analytical capability.

---

# 11. P2 — Master / Portfolio integration

After the core Strategy FTS workspace is strong:

- Make FTS evidence visible in Master
- Preserve canonical decision provenance
- Connect selection/watch state
- Integrate risk/exposure context
- Show technical/fundamental evidence without duplicate calculations

Master must consume canonical engine outputs rather than becoming a second FTS engine.

---

# 12. P2 — Local ML Engine

The ML Engine is documented separately in docs/ML-ENGINE-ROADMAP.md.

ML begins only after data and feature contracts are trustworthy enough to avoid learning corrupted semantics.

Priority:

1. Reproducible dataset
2. Feature schema
3. Labels/outcomes
4. Walk-forward validation
5. Baseline models
6. Specialized models
7. Ensemble
8. ML Lab
9. Production ranking

ML remains a complement to deterministic FTS.

---

# 13. P3 — Advanced automation and research

Longer-term:

- Strategy optimizer
- Similarity search
- Regime discovery
- Anomaly detection
- Advanced execution research
- Broker adapters
- Strategy replay
- Automated research reports
- Local ML training workflows
- Model registry
- Validated historical outcome collection

---


# 13.5. Backlog governance — no work may remain undocumented

Every new audit finding, bug, parity gap, research question, or requested feature must be classified into this roadmap before implementation.

Each tracked item should have:

- Priority: P0 / P1 / P2 / P3
- Scope: Desktop / Android / Shared
- Source/reference
- Current state
- Acceptance criteria
- Validation method
- Dependencies
- Final status: PASS / FAIL / BLOCKED / UNVERIFIED

Agents must not create an unofficial parallel roadmap in chat or in ad-hoc notes.

When an audit discovers an issue that is not already represented here:

**record it → classify it → assign its place in the sequence → implement → validate → update status**

This is the mechanism intended to prevent repeated prompts and forgotten work.


# 14. Work discipline — how agents must execute this roadmap

## 14.1 No giant mixed prompts for analytical work

Do not ask an agent to implement many unrelated analytical features at once.

Use:

**Research → Implement → Test → Verify → Accept → Next**

## 14.2 One analytical feature at a time

Especially inside Strategy FTS chart work.

Do not implement Fib + CHoCH + Double Bottom + Jet in one pass and then claim all are done.

Each feature gets its own evidence and acceptance record.

## 14.3 Research before implementation

For every difficult feature:

- Inspect current repository
- Inspect source-of-truth docs
- Inspect PDFs
- Inspect relevant external references
- Map current code
- Define exact behavior
- Then code

## 14.4 No fabricated validation

Use:

- PASS
- FAIL
- BLOCKED
- UNVERIFIED

“Tests were not run” is never equivalent to PASS.

## 14.5 No silent rule invention

Never invent thresholds, indicators, Fib anchors, scoring rules, trading rules, portfolio weights, or market-status semantics.

Ambiguity must be documented and resolved through evidence.

---

# 15. Master priority order

The intended high-level sequence is:

1. TradersArena parity
2. سرخطی / execution timing
3. ربات معامله‌گر
4. FTS chart intelligence — one feature at a time
5. Full Strategy FTS integration
6. Advanced UI/UX
7. Master / Portfolio refinement
8. Local ML Engine
9. Advanced automation / research

### Important exception

Bug fixes, security issues, data-corruption issues, broken releases, and critical Android/Desktop regressions can interrupt this sequence because they are reliability blockers.

Feature work that is not on the critical path should not repeatedly interrupt the current priority.

---

# 16. Final product target

The long-term target is a BorsTerminal where:

- Market data has verified external parity
- Candle semantics are canonical and reproducible
- Technical outputs are trustworthy
- سرخطی is a real timing/queue workspace
- Automated trading has explicit risk/execution controls
- Strategy FTS is the flagship analytical workspace
- Every important FTS decision can be explained and drawn on the chart
- FTS chart features have been individually researched and accepted
- Desktop and Android share canonical semantics
- The UI is approachable for beginners
- Advanced users can access full detail
- ML provides statistical evidence without replacing deterministic FTS
- Every production claim is backed by evidence

## Current strategic instruction

Until this roadmap is superseded:

**Strategy FTS = highest product investment priority.**

When choosing between polishing a secondary feature and improving Strategy FTS correctness, research depth, chart intelligence, explainability, usability, or validation, prefer Strategy FTS unless there is a critical reliability blocker elsewhere.

The desired end state is a **deep, trustworthy, visually explainable FTS decision system** integrated into the rest of BorsTerminal—not merely a collection of disconnected features.
