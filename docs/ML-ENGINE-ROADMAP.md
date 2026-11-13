# BorsTerminal ML Engine — Long-Term Roadmap

**Status:** Owner-approved technical-first architecture; implementation remains phase-gated.  
**Architecture update:** 2026-11-13  
**Runtime:** Go + Tauri + local SQLite. **Research/training:** owner-controlled Python Research Plane; temporary Colab/Kaggle GPU only for explicitly approved jobs.  
**Supersedes:** the earlier "ranking first" sequence and the old ML phase order in this document.

## 1. Vision

BorsTerminal should eventually contain a **local Machine Learning Engine** as a first-class analytical engine.

This is **not** a plan to depend on an online AI model or an external inference API.

The target architecture is a local engine composed of multiple algorithms and specialized models that can learn from historical BorsTerminal data and provide statistical evidence alongside the existing deterministic engines.

The execution order is deliberately **technical-first; opportunity discovery is the final consumer**:

```
Reference Archive (immutable)
          ↓
Operational Technical DB ── read-only Go data service
          ↓
Technical correctness + FTS four-page parity
          ↓
Canonical deterministic features / Market Signal Journal
          ↓
Point-in-Time Feature Store + versioned outcome labels
          ↓
┌───────────────────────────────────────────────────────────┐
│ 1. Pattern quality models                                 │
│ 2. Five-state market regime + symbol context              │
│ 3. Volatility, downside and liquidity-risk models         │
│ 4. Candle-sequence / probabilistic path forecasting       │
└───────────────────────────────────────────────────────────┘
          ↓
Walk-forward validation → calibrated outputs → paper research
          ↓
Final Opportunity Discovery / ranking / portfolio context
```

FTS remains a separate deterministic methodology and is not an ML target to be replaced. The five canonical fundamental axes already implemented in BorsTerminal are reused as time-correct features; they are not redefined by the ML layer.

## 2. Core architectural rule

### ML does not replace FTS

FTS remains a **deterministic rule engine** based on its canonical source-of-truth documents and owner rulings.

ML is a separate statistical-learning layer.

Therefore:

- FTS rules remain authoritative for FTS decisions.
- ML may score, rank, classify, estimate probabilities, or identify statistical patterns.
- ML must not silently override a hard FTS rejection.
- ML outputs must be explainable enough to show which features/models contributed to the result.
- A failure or removal of an ML model must not break the deterministic trading/analysis engines.

Conceptually:

```
FTS = "Is this setup permitted by the rules?"
ML  = "How statistically strong is a permitted setup?"
```

### Runtime / Research separation and database-serving contract

- The Rahavard reference archive is an immutable, cold source of historical evidence. It is not copied wholesale into every client runtime.
- Build a separately versioned **Operational Technical DB** from the archive. The Phase 4.9.7 estimate of roughly 5.2 GB is a planning estimate only; it is not an accepted artifact until the database is built, measured, integrity-checked and benchmarked.
- Keep the existing market.db and codal.db contracts intact. The Go runtime receives a dedicated, explicit **read-only** connection to the operational technical database; it must not write to the source database or silently merge it into market.db.
- Preserve raw candles, adjusted candles, adjustment basis/factors, corporate-action events, trading-session calendar, instrument identity/crosswalk, source provenance and schema version. Never fabricate OHLCV or fill unknown values with zero.
- Future candles and corporate-action updates must not depend on the owner's Rahavard account. Use the approved local source pipeline (TSETMC/CODAL and verified official inputs); use Rahavard's historical adjusted series only as a reference corpus for validation.
- Go is the product runtime. Python is restricted to owner-side research, dataset generation, model training and offline validation. Model artifacts cross into Go only through an explicit, versioned and validated inference contract; no arbitrary Python plugin or training process is shipped to client runtime.
- research.db and research artifacts stay outside Producer snapshots and outside client/user databases, following docs/opportunity-center/04-TECHNICAL-ARCHITECTURE.md.

**Database connection acceptance gate:** schema/identity mapping, row counts and checksums, raw/adjusted basis, corporate-action semantics, missing/duplicate handling, representative symbol parity, query latency, memory use, generation/version switching and read-only enforcement must all pass before technical development or ML consumes the new DB.

## 3. Final integrated target: opportunity ranking comes last

Opportunity ranking is an important final product capability, **not the first model to train**.

Before ranking can be trusted, BorsTerminal must have verified technical data, complete deterministic technical analysis, the canonical FTS chart/methodology path, valid pattern outcomes, a validated five-state regime model, risk/volatility estimates and calibrated candle-path forecasts.

Only after those specialist outputs pass independent out-of-sample validation should a final ranker combine them with market, tape and the five existing fundamental FTS axes.

Example:

```
Symbol    FTS        Trend      ML Score
-----------------------------------------
فولاد     PASS       UP             91
شپنا      PASS       UP             84
خودرو     PASS       DOWN           63
...
```

The model should answer questions such as:

- Which FTS-approved setups historically behaved better?
- Which symbols have a higher probability of achieving a defined outcome over N trading days?
- Which technical/fundamental/order-flow combinations historically produced stronger outcomes?

The output should preferably be a probability, score, or rank rather than an unconditional price target.

Example:

```
Probability of positive return in 10 sessions: 72%
Probability of breakout confirmation:           68%
Setup quality score:                            82/100
```

## 4. Planned model families

The ML Engine should support multiple algorithms/models rather than one monolithic model.

### 4.1 Pattern and technical-structure models — first learning target

The deterministic technical engine remains responsible for **detecting and geometrically describing** patterns. ML estimates their statistical quality, context and conditional outcomes; it does not replace the detector or rewrite canonical FTS rules.

Start with pattern-level classification/ranking using versioned pattern events and point-in-time features:

- Double top / double bottom; head-and-shoulders and inverse; triple top/bottom.
- Flags and pennants; ascending, descending and symmetrical triangles.
- Rising/falling wedges; channels and rectangles.
- Breakout, failed breakout, retest/pullback and continuation/reversal structures.
- FTS-specific structures: weekly/daily trend, Jet, corrective pullback, Fibonacci zones, CHoCH and the setups explicitly defined in the FTS source material.

Candidate models: Logistic Regression / calibrated classifiers as baselines, then LightGBM and CatBoost. Neural sequence classifiers (small 1D-CNN/GRU/Transformer) are later challengers only when they beat these baselines out of sample.

The model should estimate outcomes such as probability of confirmation, invalidation, target-before-stop, and conditional MFE/MAE. It must use the detector's formation/confirmation timestamp, not a retrospectively identified pattern anchor.

### 4.2 Five-state market-regime models — second learning target

The regime system must distinguish **market-wide regime** from **individual-symbol regime**. The five-state market taxonomy to test is:

1. Directional bullish market.
2. Directional bearish market.
3. Range / neutral market.
4. Liquidity contraction / low-participation market.
5. Shock / limit-locked / dislocated market.

These are initial research definitions, not hard-coded truths. Their boundaries and precedence must be tested against the Iranian market's breadth, index structure, value/volume, order-book and queue participation, realized volatility and cross-sectional dispersion. If the evidence cannot distinguish a state, return unknown or a probability distribution rather than force a label.

Start with an interpretable rule-based baseline; compare HMM / Markov-switching and other probabilistic regime models. Regime outputs are probabilities plus state duration/transition evidence, not merely a colored label.

### 4.3 Volatility, downside and market-risk models — third learning target

This is separate from predicting direction. Candidate methods:

- ATR and realized-volatility baselines.
- EWMA, GARCH / EGARCH and, when intraday/realized measures support it, HAR-RV.
- Quantile models for conditional return/range distributions.
- Downside risk: VaR, Expected Shortfall, drawdown distribution, tail-event probability, MFE/MAE and volatility regime.
- Execution/liquidity risk: gap risk, limit-lock probability, queue/no-fill risk, spread/slippage proxies and stale/insufficient-liquidity states.

Evaluate volatility forecasts with appropriate loss functions (e.g. QLIKE where applicable), and tail-risk estimates with coverage/calibration tests. Do not treat price direction accuracy as a risk-model acceptance metric.

### 4.4 Candle-sequence and probabilistic future-path models — fourth learning target

**Kronos remains a first-class candidate and must not be dropped.** It is the domain-specific OHLCV sequence model already downloaded and benchmarked in the repository.

Model comparison set:

- **Kronos-mini** — first local reference model for multichannel candle-sequence forecasting; official PyTorch implementation is tools/kronos_engine_official.py.
- **Chronos-Bolt-Tiny** — lightweight probabilistic forecasting comparator and possible CPU deployment candidate.
- **TimesFM** — broader time-series foundation-model comparator; model-version license and deployment conditions must be checked separately.
- **PatchTST / iTransformer** — trainable specialist architectures if the data and benchmarks justify them.
- Naive/seasonal, drift, linear and volatility-based forecasts — mandatory baselines.

The current Kronos integration is not yet accepted as an Iranian-market forecast: Go currently calls the older tools/kronos_inference.py path and supplies closes/timestamps, while Kronos expects real multichannel OHLCV plus amount. The integration gate requires the official inference path, real OHLCV/volume/amount, correct trading-session timestamps (not fixed 86,400-second increments), explicit model/fallback reporting and reproducible CPU/GPU benchmarks. Synthetic OHLCV proxies are allowed only in labelled synthetic tests, never in real-data acceptance.

Evaluate path distributions, not just P50: quantile/CRPS or pinball loss, empirical P10/P90 coverage, interval width, calibration by regime/horizon, path coherence, and performance against simple baselines. Fine-tuning is allowed only after zero-shot and baseline evaluation on the same time-aware splits.

### 4.5 Final opportunity ranking / classification — last learning target

Only after 4.1–4.4 have validated outputs should a final LightGBM/CatBoost ranker or calibrated classifier combine:

- deterministic pattern/structure results and learned pattern quality;
- market and symbol regime probabilities;
- volatility, downside and liquidity-risk estimates;
- Kronos/Chronos/other forecast distributions and uncertainty;
- canonical FTS state and the five existing fundamental axes;
- market breadth, sector-relative strength, tape/order-flow and data freshness where historically available.

The ranker is a final decision-support layer. It cannot change a hard FTS reject into a pass, cannot hide missing data, and cannot label a pattern/forecast as a guaranteed trade.

### 4.6 Unsupervised learning and anomaly research

Potential uses:

- clustering symbols and setups by behavior;
- discovering recurring regime subtypes;
- anomaly detection in candles, volume, corporate actions and model residuals;
- similarity search for historically comparable technical structures.

Unsupervised outputs remain research hypotheses until independently validated.

## 5. Ensemble architecture

The engine should be able to combine specialized model outputs.

Example:

```
Trend Model          0.86
Breakout Model       0.74
Volume Model         0.91
Regime Model         0.68
Pattern Model        0.81
Fundamental ML       0.77
--------------------------------
ML Composite         0.82
```

The initial implementation may use explicit, versioned weights.

Later, ensemble weights may become regime-dependent or learned from out-of-sample performance.

Every ensemble definition must be versioned so that historical results remain reproducible.

## 6. Data and feature sources

The current BorsTerminal architecture already exposes potential ML feature sources.

Possible feature groups:

### Market / candle data

- OHLCV
- display price / LAST
- canonical adjustment basis where applicable
- returns over multiple horizons
- volatility
- range/ATR-style measures
- gaps
- candle structure
- relative volume

### Technical structure

- weekly trend state
- daily trend state
- swing structure
- BOS / CHoCH state
- pullback state
- Fibonacci context
- distance to structural levels
- moving-average relationships
- indicator-derived features

### Fundamental data

- revenue growth
- gross-margin metrics
- earnings/profit metrics
- estimated sales / market-cap measures
- quarterly/annual changes
- other features already canonicalized by the Fundamental engine

Fundamental feature definitions must come from the existing BorsTerminal source-of-truth rules and must not be re-invented inside ML.

The five canonical FTS fundamental axes are already available in BorsTerminal and must be consumed as five separately versioned, point-in-time feature groups (not collapsed to a single score):

- **F-01:** revenue/sales growth.
- **F-02:** sustained profitability and EPS trend.
- **F-03:** gross-profit margin.
- **F-04:** annualized sales relative to market value.
- **F-05:** industry outlook and pricing regime (free/market-based versus administered pricing), including applicability/unknown states.

The exact formulas, thresholds, vetoes and sector rules remain those of the canonical FTS sources and owner rulings. ML must consume their actual values/statuses and publication/availability timestamps; it must not independently redefine the five axes.

### Market microstructure / order flow

- order-book imbalance
- queue information
- legal/real-person flow where reliably available
- volume/value concentration
- execution/timing-related features when they are actually observable
- board/tape state

Only fields with a verified provenance and clear timestamp semantics should be used for training.

### FTS state

Examples:

- weekly branch
- daily branch
- FTS stage
- pass/reject reason
- setup type
- jet context
- Fibonacci zone context
- fundamental blocker states

FTS outputs must be treated as canonical features, not recomputed inconsistently by the ML layer.

## 7. Outcome/label design

A major part of the project is defining labels correctly.

Labels should be tied to explicit timestamps and trading horizons.

Possible examples:

```
Return after 3 sessions
Return after 5 sessions
Return after 10 sessions
Reached target before invalidation: yes/no
Positive return before stop: yes/no
MFE (Maximum Favorable Excursion)
MAE (Maximum Adverse Excursion)
Breakout confirmed within N sessions: yes/no
```

The exact target definitions must be documented and versioned.

There must be no ambiguous "successful trade" label.

## 8. Experience database / learning loop

Every production-qualified signal/setup should eventually be recordable as an observation.

Conceptual record:

```
signal_id
symbol
timestamp
FTS branch
FTS decision
technical state
fundamental state
market state
order-flow state
feature_vector_version
model_version
entry/context
target/invalidity definition
result_3d
result_5d
result_10d
MFE
MAE
```

This creates a feedback loop:

```
Historical Data
      ↓
Feature Generation
      ↓
Training Dataset
      ↓
Model Training
      ↓
Walk-forward Validation
      ↓
Approved Model
      ↓
Local Inference
      ↓
Production Outcomes
      ↓
Experience / Evaluation Store
      ↓
Next Training Cycle
```

The system must **not** automatically retrain and replace production models from raw live outcomes without validation and explicit model-promotion rules.

## 8.1 Market Signal Journal — required source for historical observations

The local ML data foundation must consume the canonical Market Signal Journal described in `docs/MASTER-EXECUTION-ROADMAP.md`; it must not independently reconstruct filter history with a parallel, subtly different implementation.

The journal should be able to query a symbol's state as-of a trading timestamp across Watchlist, Strategy FTS and Tape/Market. It should preserve:
- stable instrument identity;
- actual observation timestamp and trading date;
- observed end-of-day, observed intraday, or reconstructed status;
- canonical feature/input provenance and availability timestamps;
- FTS/technical/fundamental rule and engine versions;
- pass, reject, unknown, not-applicable, not-evaluated and error states;
- funnel stage and reason codes;
- data completeness and reconstruction confidence/status.

Do not store only successful candidates. Failed/rejected/unknown rows are part of the learning dataset and help measure selection bias.

### Capture semantics

- Daily snapshots should be recorded automatically by a reliable worker.
- Intraday transitions can be treated as observed only while a collector was actually running or where a trustworthy historical source supports them.
- If BorsTerminal was closed, startup catch-up may reconstruct a historical state only from data whose availability at that past decision time can be proven.
- Reconstructed records must remain explicitly distinguishable from live-observed records.
- Never invent intraday transitions during an interval without a collector/source.
- Preserve original observations when rules, historical records or features are revised; produce versioned recalculations instead of silently rewriting history.

### ML dataset boundary

Feature snapshots and outcome labels are separate datasets. A feature can only use information available at the decision timestamp. Future outcomes—such as returns after 3/5/10 sessions, MFE, MAE, or target-before-invalidation—must be stored as labels with a versioned definition and a clearly later evaluation window.

The dataset generator must audit feature availability timestamps, corporate-action status, report publication time and rule versions before accepting rows. Rows with missing/ambiguous provenance should be excluded from a claimed clean training set or explicitly represented as incomplete—not quietly filled with fabricated values.

The first learning-loop deliverable is a reproducible, time-aware dataset and simple baseline evaluation, not a large model.

---

## 9. Training vs inference

Training and inference should be separated.

### Training / ML Lab

Python ecosystem is a likely starting point:

- pandas
- NumPy
- scikit-learn
- LightGBM / XGBoost
- PyTorch when neural models are justified

Training can happen offline on a stronger machine.

### Production inference

Production models should be exportable to a stable local format where practical, for example:

- ONNX
- native LightGBM/XGBoost model formats
- other deterministic serialized model formats

Desktop inference can run locally through the existing backend architecture.

Android should prefer lightweight local inference where practical, using an appropriate mobile runtime.

No permanent dependency on an external AI/LLM API is part of this roadmap.

## 10. Model registry and versioning

Models must be treated as versioned software/data artifacts.

Conceptual structure:

```
models/
  ranking_v1/
  ranking_v2/
  breakout_v1/
  regime_v1/
  fib_setup_v1/
```

Each model version should record:

- training dataset version
- feature schema version
- label definition version
- algorithm and hyperparameters
- training date
- validation period
- out-of-sample metrics
- walk-forward results
- known limitations
- promotion status

Only validated models may become production models.

## 11. Validation is a hard requirement

Financial ML is especially vulnerable to false confidence.

The ML Engine must explicitly prevent:

- lookahead leakage
- future-candle leakage
- training on information unavailable at prediction time
- survivorship bias where applicable
- leakage through adjusted data or revisions
- accidental mixing of future labels into features
- random train/test splits when they violate temporal causality

The preferred validation strategy is time-aware:

```
Train → Validate → Test
        ↓
Walk-forward
        ↓
Out-of-sample confirmation
```

A model should not be promoted because a single backtest reports a high accuracy.

Relevant evaluation should include, where appropriate:

- precision / recall
- ROC-AUC / PR-AUC
- calibration
- hit rate
- expectancy
- drawdown
- MFE / MAE
- rank correlation
- stability across market regimes
- performance after realistic transaction costs/slippage assumptions

## 12. No-lookahead contract

Every feature must have a clear **availability timestamp**.

A feature is valid only when its source information was actually available to the system at that prediction time.

Examples that require special care:

- end-of-day indicators
- quarterly financial statements
- Codal publication timing
- corporate-action adjustments
- revised historical records
- order-book/tape fields
- market status fields

The ML dataset generator should be able to audit feature timestamps and reject invalid rows.

## 13. Relationship to Auto-Fibonacci and technical engine

Auto-Fibonacci is not required to be ML-driven in its first implementation.

The preferred sequence is:

1. establish canonical candle contract;
2. establish canonical swing/structure detection;
3. implement deterministic FTS Fibonacci anchor selection;
4. render validated FTS zones on the chart;
5. collect historical outcomes;
6. later create ML features from Fib context.

A future `fib_setup` model may evaluate questions such as:

- which Fib zone historically performs better under specific regimes;
- how distance from B affects outcome;
- whether CHoCH + Fib-zone interaction improves probability;
- whether volume/market regime changes Fib setup quality.

ML therefore extends the Fibonacci engine instead of replacing its deterministic source-of-truth logic.

## 14. Future ML Lab UI

A future dedicated **ML Lab** tab may expose:

- dataset/version selection
- feature inspection
- model comparison
- training runs
- walk-forward backtests
- feature importance
- calibration plots
- regime breakdown
- model performance over time
- model registry
- promotion/rejection status
- historical prediction audit
- explainability for a single symbol/setup

Example single-symbol view:

```
فولاد

FTS                PASS
ML Composite       82/100

Contributing Models
  Trend             0.86
  Breakout          0.74
  Volume             0.91
  Regime             0.68

Historical estimate
  Positive 10D      72%

Model version
  ranking_v2

Validation
  Walk-forward      PASS
```

This UI must distinguish **historical validation evidence** from a live prediction.

## 15. Desktop and Android strategy

### Desktop

Desktop is the primary environment for:

- feature generation
- training
- ML Lab
- model comparison
- backtesting
- model promotion

Inference should also be supported locally.

### Android

Android should focus on:

- consuming validated models;
- lightweight local inference when technically appropriate;
- displaying ML scores and explanations;
- offline operation where possible.

Training large models on Android is not a target.

## 16. Owner-approved technical-first implementation sequence

The order below is mandatory for this ML workstream. It does not reorder unrelated owner-approved product priorities in the Master Execution Roadmap; it defines what happens **after the ML/technical workstream is opened**.

### Phase 0 — Build and connect the Operational Technical DB to Go

- Preserve the Rahavard reference archive unchanged as a cold, immutable research source.
- Build the compact operational Technical DB from verified historical series. The approximately 5.2 GB size is an estimate until measured.
- Keep technical candles/adjustment data separate from the existing market.db, codal.db, user.db, research.db and oc_client.db.
- Add an explicit read-only Go database handle and typed query/service contracts; Go must not become a second writer.
- Include instrument identity, raw/adjusted price basis, OHLCV/amount, source and availability timestamps, corporate-action/factor history, trading calendar and schema/version metadata.
- Verify row counts, hashes, schema, duplicate/missing/zero semantics, price-basis behavior, corporate-action handling, sample symbol parity, query latency, memory, generation switching and read-only enforcement.

**Exit gate:** Go can serve reproducible real candles for representative symbols/timeframes from the new DB, and all integrity/parity/performance gates pass. No ML training begins before this gate.

### Phase 1 — Complete deterministic technical analysis and FTS/chart parity

Audit and complete existing code rather than duplicating it. Existing frontend-v2 pattern detectors/registry and current Go chart services are starting points, not proof of completeness.

#### Mandatory reuse of the existing indicator library — no greenfield rebuild

Before implementing or training any pattern/indicator capability, perform an asset-to-capability audit of the materials already committed to the repository. The audit must cover, at minimum:

- `docs/technical-indicators/implemented/`: features already implemented and documented; reuse their actual runtime implementations and tests.
- `docs/technical-indicators/reviewed/`: previously researched engines, chart/FTS parity, pivots, major swings, trend and candle fidelity; do not repeat completed investigations unless new evidence contradicts them.
- `docs/technical-indicators/inbox/`: source files, notes, catalog attachments and screenshots that the owner collected for evaluation.
- Legacy `docs/Indicator/`: reconcile against the curated `docs/technical-indicators/` tree by content hash; do not ignore it or create duplicate implementations.
- Existing runtime code: `frontend-v2/src/features/technical/`, the current pattern registry/detectors, `backend-go/internal/indicators/`, FTS indicator catalog/overlays, and the canonical FTS calculation services.

The current repository triage records **nine existing indicator overlays** already implemented (including Double Tap, Auto Trendline/CHoCH, SuperTrend Pullback, Breakout Retest, RSI/MA/Divergence, Fibo RSI8, SuperTrend Heikin-Ashi and channel variants). These are a starting inventory to verify against current code and tests—not permission to recreate them.

The recorded next candidates are:
1. Support/Resistance Retest Breakout (catalog item 21).
2. Automatic Wedge & Channel Detector (item 19).
3. Order-Block scoring / volume confirmation (items 17 and 23).

These are investigation priorities, not pre-approved implementation specifications. First determine whether an equivalent calculation already exists in code or a reviewed source; then fill only the proven gap.

The Telegram inbox records 64 catalog entries and 38 readable source files. Each must be classified and deduplicated by content hash. MQL4/MQL5 files must be inspected to determine whether they are indicators, Expert Advisors, scripts or libraries. Compiled EX4/EX5 files are not treated as readable source, must not be executed, and are not directly ported. The documented license audit identifies MPL-2.0 files, CC BY-NC-SA 4.0 files, and files with no stated license; check rights per asset before copying or distributing code. Where direct code reuse is not licensed or appropriate, use the material as a behavioral/formula reference only and implement from independently documented semantics where lawful.

For every asset, record: source/path/hash, type, license, capability, formula/parameters, required inputs, timeframe, price basis, closed/current-candle behavior, repaint/look-ahead risk, missing-data behavior, computational cost, existing equivalent implementation, parity evidence, tests, and decision (`reuse`, `port`, `adapt`, `research-only`, `defer`, or `reject`).

**Hard rule:** no new pattern or indicator implementation may start until this audit checks the existing inbox, reviewed/implemented assets and runtime code. Do not rebuild an existing capability merely because it is in a different language or folder. ML models learn the conditional quality/outcomes of deterministic pattern outputs; they do not replace the deterministic geometry engine or start from chart-image recognition by default.


Required coverage:

- candle geometry, confirmed pivots and non-repainting swing structure;
- HH/HL/LH/LL trend classification on daily/weekly/monthly timeframes;
- BOS / CHoCH, support/resistance, breakout/failure/retest and pullback;
- canonical Fibonacci anchors/zones, Jet and the FTS-specific setups;
- classical reversal and continuation pattern library with forming/confirmed/invalidated lifecycle;
- indicators and derived features (trend, momentum, volatility, volume, divergence);
- sector/index-relative strength, market breadth and multi-timeframe context;
- candle/session calendar and corporate-action-aware price-basis correctness.

The four printed FTS chart pages remain the canonical product map: **F = fundamental, T = technical, S = selection/tape, M = reverse-engineering/capital management**. Reconcile the chart against docs/جزوه FTS.pdf, docs/FTS.CHART_3.pdf, docs/FTS-RULE-ALGORITHM-MAP.md, docs/CHART-FOUR-PAGES-PARITY.md and owner rulings. Each node must map to a canonical rule, actual computation, input/provenance and visible chart evidence. The chart model/layout is presentation; it must not independently judge signals.

FTS remains deterministic. Python/Go/chart parity and Golden Vectors are required before any FTS result is treated as validated.

**Exit gate:** deterministic technical outputs, chart overlays, four-page FTS mapping and Go/API behavior pass source-to-chart parity; no repaint/look-ahead defects remain in confirmed outputs.

### Phase 2 — Market Signal Journal, Point-in-Time Feature Store and labels

- Use the canonical Market Signal Journal; do not create a competing history of FTS/technical states.
- Preserve all instruments and states: pass, reject, unknown, not-applicable, not-evaluated, error.
- Distinguish observed EOD, observed intraday and reconstructed states.
- Build versioned feature snapshots with source, rule/model version, observation time and availability time.
- Use the five canonical feature pillars: candle/price, technical structure, market/tape, breadth/regime, and the five fundamental FTS axes.
- Keep raw features, engineered features, forecast/model outputs and future outcome labels in separate datasets.
- Define 1/3/5/10/20-session labels as appropriate: forward return, target-before-invalidation, MFE, MAE, realized volatility, drawdown and liquidity/no-fill outcomes.
- Account for symbol listing/delisting and survivorship, corporate-action basis, trading calendar and incomplete historical tape/order-book coverage.

**Exit gate:** a fixed dataset can be regenerated deterministically; every feature is point-in-time valid; labels are versioned; leakage and survivorship audits pass.

### Phase 3 — Train technical-pattern quality models

- Build deterministic pattern-event datasets from the Phase 1 engines.
- Train interpretable baselines first (Logistic/ElasticNet), then LightGBM/CatBoost.
- Estimate pattern confirmation, failure, invalidation, target-before-stop and conditional MFE/MAE.
- Evaluate by pattern family, market regime, symbol liquidity and timeframe.
- Deep sequence classifiers are challengers only after tabular baselines.

**Exit gate:** meaningful out-of-sample improvement over baselines with calibrated probabilities and no retrospective pattern-timestamp leakage.

### Phase 4 — Train the five-state market-regime system

Candidate states: bullish directional, bearish directional, range/neutral, liquidity contraction, and shock/limit-locked. Validate that these are empirically distinguishable; keep market-wide and symbol-level regimes separate.

- Begin with a transparent rules-based baseline.
- Compare HMM / Markov-switching and validated probabilistic alternatives.
- Return state probabilities, confidence, duration and transition diagnostics; allow unknown/uncertain.
- Test stability across different historical regimes and data-coverage levels.

**Exit gate:** regime classifications are stable, calibrated and economically meaningful out of sample; no forced label on insufficient evidence.

### Phase 5 — Train volatility and risk models

- Build realized-volatility and ATR/EWMA baselines.
- Compare GARCH/EGARCH and HAR-RV where data frequency supports them.
- Add conditional quantile, downside-tail, VaR/Expected Shortfall and drawdown estimates.
- Model liquidity, limit-lock and execution/no-fill risk separately from price-direction risk.

**Exit gate:** risk estimates pass coverage/calibration and loss-function tests; risk is evaluated separately from return-direction accuracy.

### Phase 6 — Validate and fine-tune candle-sequence/path models

Comparison order:

1. Naive/drift/linear/volatility baselines.
2. Kronos-mini using the official PyTorch implementation and real six-channel OHLCV+amount.
3. Chronos-Bolt-Tiny as a lightweight probabilistic comparator.
4. TimesFM under a separately reviewed model-version license.
5. PatchTST / iTransformer if data volume and benchmark evidence justify them.

Run locally on the owner's machine and use Colab only for scoped, reproducible GPU jobs. First compare zero-shot models; fine-tune only those that demonstrate a meaningful baseline gap. Store model/tokenizer revisions, dataset hash, feature/label versions, environment lock, seed, parameters and metrics.

**Exit gate:** path distributions are calibrated by horizon and regime, beat appropriate non-ML baselines, and meet local inference/resource constraints. Synthetic OHLCV is never accepted as real-market evidence.

### Phase 7 — Specialized-model integration and paper research

- Combine pattern, regime, risk and sequence forecasts through a versioned, auditable interface.
- Measure calibration, correlation/redundancy, stability and performance contribution of each model.
- Use paper/replay research, cost/queue-aware execution assumptions, Drift monitoring and explicit model registry.
- No automatic production promotion or silent retraining.

**Exit gate:** repeated walk-forward/paper evidence across different market conditions and explicit owner-reviewed model acceptance.

### Phase 8 — Final Opportunity Discovery and ranking (last)

Only now build the final opportunity ranker/ensemble. Its inputs include validated technical patterns, five-state regime, risk/volatility, probabilistic candle paths, FTS state, the five fundamental axes, sector/breadth/tape evidence and freshness.

- Begin with transparent and explainable baselines, then LightGBM/CatBoost ranking.
- Rank only after mandatory deterministic gates and risk/data-quality exclusions.
- Show rank trace, supporting models, uncertainty and reasons.
- Never convert a hard FTS reject or unknown into an accepted FTS candidate.
- Contextual Bandits/strategy allocation remain later research, after a reliable outcome journal exists.

**Exit gate:** Opportunity Discovery demonstrably adds value beyond the specialist engines on untouched out-of-sample periods and paper results. This is the final consumer, not the starting point of the ML program.

### Research compute and product runtime

- Local PC: data engineering, audit, LightGBM/CatBoost, HMM/GARCH, CPU/GPU inference benchmarks and reproducibility.
- Google Colab: temporary GPU training/fine-tuning for bounded jobs; checkpoint frequently; record environment and data-scope hashes. Never depend on Colab for a permanent service.
- Runtime: Go + Tauri; only validated model artifacts and stable inference contracts may be integrated. Research Python and training dependencies remain outside the client runtime.
- The current Opportunity Lab architecture's approval gate remains authoritative; research success alone does not imply a model is Stable or distributable.

## 17. Non-goals

The following are explicitly out of scope for the initial ML roadmap:

- replacing FTS with a black-box model;
- depending on a remote LLM/API for every prediction;
- claiming guaranteed future prices;
- automatic self-modifying production models;
- promoting a model based on one backtest;
- hiding model uncertainty;
- using future information for training features;
- inventing unsupported market/fundamental data.

## 18. Definition of success

The long-term ML Engine is successful when BorsTerminal can:

1. reproduce a historical dataset from versioned source data;
2. build features from the same canonical engines used by the application;
3. train multiple candidate algorithms;
4. evaluate them with walk-forward/out-of-sample validation;
5. compare models and ensembles;
6. promote only validated model versions;
7. run inference locally;
8. show ML evidence without overriding deterministic FTS rules;
9. record real outcomes and use them in future validated training cycles.

## 19. Guiding principle

The objective is not to make BorsTerminal "AI-powered" for marketing purposes.

The objective is to build a **measurable, reproducible, local statistical-learning engine for the Iranian market** that improves decision support while preserving the determinism and auditability of the existing BorsTerminal engines.

This is a **long-term roadmap**. It should not block current priorities such as canonical market data, technical parity, FTS correctness, chart parity, Auto-Fibonacci, Android stability, and release integrity.
