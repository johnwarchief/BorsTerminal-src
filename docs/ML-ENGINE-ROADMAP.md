# BorsTerminal ML Engine — Long-Term Roadmap

**Status:** Planned / Long-term  
**Date:** 2026-10-07  
**Scope:** Desktop + Android, with a shared model/feature contract where practical.

## 1. Vision

BorsTerminal should eventually contain a **local Machine Learning Engine** as a first-class analytical engine.

This is **not** a plan to depend on an online AI model or an external inference API.

The target architecture is a local engine composed of multiple algorithms and specialized models that can learn from historical BorsTerminal data and provide statistical evidence alongside the existing deterministic engines.

The long-term goal is:

```
FTS / Technical / Fundamental / Market
                ↓
        Feature Engineering
                ↓
          ML Engine
     ┌──────────┼───────────┐
     │          │           │
   Ranking   Pattern      Regime
    Model     Models      Models
     │          │           │
     └──────────┼───────────┘
                ↓
         ML Composite Score
                ↓
      Master / Portfolio Layer
```

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

## 3. First target: ranking, not price prophecy

The first production-oriented ML capability should **not** be "predict tomorrow's price."

The preferred starting point is **ranking / setup-quality estimation**.

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

### 4.1 Ranking / classification

Candidate families:

- LightGBM
- XGBoost
- Random Forest
- Logistic Regression
- Other lightweight tabular learners justified by validation

Potential tasks:

- setup quality classification
- probability of positive return
- probability of breakout confirmation
- probability of reaching a predefined target before invalidation
- ranking of FTS-approved candidates

### 4.2 Pattern / structure models

Potential tasks:

- swing high / swing low classification
- impulse-wave detection
- pullback detection
- breakout detection
- BOS / CHoCH classification
- double-bottom / double-top classification
- accumulation / distribution pattern classification

The first versions should preferably reuse the canonical deterministic swing/structure representation instead of replacing it blindly.

### 4.3 Market-regime models

Potential regimes:

- directional uptrend
- directional downtrend
- range / neutral
- high-volatility regime
- low-volatility regime
- other statistically validated regimes

The regime can later control feature selection or ensemble weighting.

For example, trend-following features may receive less weight during a validated range regime.

### 4.4 Unsupervised learning

Potential uses:

- clustering symbols by behavior
- clustering historical setups
- discovering recurring market regimes
- anomaly detection
- similarity search for "historically similar setups"

Unsupervised outputs are research signals until they pass the same validation discipline as supervised models.

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

## 16. Phased implementation plan

### Phase 0 — Data foundations

Before serious ML work:

- canonical candle contract
- stable timestamps
- verified market/fundamental provenance
- corporate-action semantics
- deterministic technical structure outputs
- reproducible historical datasets
- no-lookahead dataset builder

**Exit criterion:** identical input data + same versioned feature pipeline produces identical features.

### Phase 1 — Dataset and experience store

Build:

- feature schema
- outcome/label schema
- historical dataset generator
- signal/setup result store
- dataset versioning

**Exit criterion:** a reproducible training dataset can be regenerated from a fixed snapshot.

### Phase 2 — First ranking/classification models

Start with lightweight tabular models.

Initial experiments:

- Logistic Regression baseline
- Random Forest baseline
- LightGBM/XGBoost candidate

**Exit criterion:** every model has time-aware validation and an explicit comparison against simple baselines.

### Phase 3 — ML Composite / Ensemble

Add specialized models:

- trend/setup quality
- breakout
- volume
- regime
- fundamental features

Combine them into a versioned ensemble.

**Exit criterion:** ensemble performance is demonstrably better and more stable than the baseline models across multiple out-of-sample periods.

### Phase 4 — ML Lab

Expose the research workflow in BorsTerminal.

**Exit criterion:** model training/evaluation results are reproducible and inspectable without editing source code.

### Phase 5 — Production ranking

Integrate ML scores into Master/Portfolio as decision-support information.

**Exit criterion:** ML never changes a deterministic FTS hard reject into a pass, and model version/provenance is visible.

### Phase 6 — Advanced pattern/regime learning

Explore:

- structural pattern models
- unsupervised clustering
- anomaly detection
- similarity search
- regime-aware ensembles

Only validated components progress to production.

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
