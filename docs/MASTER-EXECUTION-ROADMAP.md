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
