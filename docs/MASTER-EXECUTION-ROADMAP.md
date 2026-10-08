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

## F.1 First-install / first-launch contract

The first-run experience is a production feature and must be designed, measured, and tested deliberately.

The application must define exactly what happens after a fresh installation on:

- A normal/recommended machine/device
- A low-resource machine/device
- A device with slow storage
- A device with limited free disk space
- An offline device
- A partially interrupted first launch

The user must never be left with an apparently frozen application or an ambiguous blank screen.

### Required first-launch state machine

The application should expose explicit states such as:

**Installed → Checking environment → Preparing runtime/data → Loading essential data → Ready**

with failure/retry states where necessary.

The first launch must distinguish:

- Application startup
- Database/snapshot preparation
- Cache creation
- Data download/update
- Decompression/indexing/migration
- UI readiness

Do not block the whole UI behind long-running work when a useful shell/status screen can be shown safely.

### First-launch UX

Show:

- What the application is doing
- Progress where measurable
- Downloaded/remaining data where applicable
- Current stage
- Estimated size requirements where known
- Retry/resume action
- Clear error messages
- Safe recovery path

Never display fake progress.

If exact progress is impossible, show an honest indeterminate state rather than fabricated percentages.

### Low-resource profile

Define an explicit low-resource operating profile.

The application should:

- Detect constrained CPU/RAM/storage conditions where practical
- Defer non-critical work
- Avoid starting all heavy analyses simultaneously
- Load essential market/UI functionality first
- Build secondary indexes/caches lazily where safe
- Bound memory growth
- Avoid excessive startup processes
- Provide a usable degraded mode without changing canonical analytical results

The low-resource mode must not silently remove required FTS or market functionality.

### First-launch acceptance

Test cold first launch, repeated first launch, interrupted launch, insufficient disk, offline launch, and low-resource hardware.

Record:

**time to first UI → time to first usable data → time to ready → peak RAM/CPU → disk usage → network usage**

and compare against defined product budgets.

## F.2 Update compatibility and legacy-version fallback

Updates must work even when the installed version is too old to consume the current delta/patch format.

The updater must implement a compatibility decision before applying a package:

**Current version → update channel → patch compatibility check → Delta update OR Full-package fallback**

### Delta-update rules

- Never assume every old version supports delta patches.
- Determine a minimum supported base version for each delta package.
- Verify applicability against the exact installed version/build identity.
- Reject incompatible deltas before attempting mutation.
- Never leave the installation half-updated because an incompatible patch was selected.
- Do not rely on users manually installing several historical versions unless that is explicitly the documented recovery path.

### Full-package fallback

When the installed version is too old, corrupted, structurally incompatible, or otherwise outside the delta range:

**Download full installer/package → verify checksum/signature → preserve user data/configuration where compatible → migrate data → install/replace safely → verify new version → clean up old package**

The fallback path must be automatic or clearly offered to the user.

The user should not need to understand delta patches or version internals.

### Supported-version policy

Define and document:

- Current version
- Minimum supported update-from version
- Minimum supported data/schema version
- Whether direct update is supported from N versions back
- When full installer is mandatory
- End-of-support behavior for extremely old releases

An outdated installation must receive a clear message and a supported recovery path.

### Interrupted update / rollback

The updater must tolerate:

- Network interruption
- Power loss
- Application termination
- Insufficient disk
- Signature/checksum failure
- Corrupt package
- Failed migration
- Failed post-install verification

Use atomic replacement/staging where the updater technology supports it.

Never destroy the last known-good installation before the new version has passed verification.

Provide rollback/recovery when the packaging system supports it.

### User data preservation

Updates must not casually delete:

- User settings
- Custom filter parameters
- FTS configuration
- Local watch/portfolio state
- Cache/configuration that is explicitly intended to persist

Schema/data migrations must be versioned and reversible where practical.

### Update UX

The user should be told only what matters:

- New version available
- What kind of update is being performed
- Download/progress
- Restart requirement
- Success/failure
- Recovery action when needed

Do not expose confusing internal updater terminology unless useful.

### Update acceptance matrix

Test at least:

1. Current version → current+1 delta
2. Supported older version → current delta
3. Very old version without delta support → full installer
4. Corrupted/out-of-range installation → recovery/full installer
5. Interrupted download
6. Interrupted installation
7. Insufficient disk
8. Invalid checksum/signature
9. Failed migration
10. Successful post-update launch
11. Rollback/recovery path where supported

Every update path must end in a verified runnable installation.

## F.3 Desktop packaging architecture — migrate to real Tauri runtime

The long-term Desktop target is **real Tauri v2 runtime**, not a repository that merely contains Tauri tooling while the distributed product is PyInstaller/FastAPI + Inno.

The migration must be treated as an architectural project and must not be rushed.

### Current state

The current repository contains a Tauri v2 shell, updater plugin, NSIS/MSI configuration, and signing infrastructure, but the distributed Windows product is still the Python/PyInstaller backend packaged by Inno Setup.

This dual-path architecture is a source of complexity and documentation drift.

### Target state

Preferred target:

**Tauri native shell → React frontend → Python/FastAPI sidecar → local data/runtime**

with one canonical Desktop packaging and update path.

The Python backend remains available where necessary; the migration does not permit changing analytical semantics merely to fit the packaging technology.

### Migration gates

Before switching the production channel:

1. Prove Tauri can launch the complete application.
2. Prove the Python/FastAPI backend can run reliably as a managed sidecar.
3. Prove startup/shutdown and process cleanup.
4. Prove local API communication and security boundaries.
5. Prove database access and writable-data locations.
6. Prove all chart engines and browser-level integrations.
7. Prove offline operation.
8. Prove first-launch preparation.
9. Prove update, rollback, and recovery.
10. Compare startup time, RAM, CPU, disk, and installer size against the current production build.
11. Install and run the release artifact on a clean Windows environment.
12. Only after all gates pass, switch the public production installer/update channel.

### Canonical architecture rule

After migration is accepted, avoid maintaining two competing Desktop packaging/runtime paths unless there is a documented compatibility reason.

Old packaging code may remain temporarily during migration, but it must be clearly marked:

**legacy / migration-only / not production**

### Updater target

Prefer the official Tauri v2 updater path once the app is genuinely running under Tauri.

Use signed updater artifacts and version-bound trust.

The current Tauri updater supports signed Windows NSIS/MSI updater artifacts. Current Tauri documentation also supports requiring the signed artifact version to match the announced version; this must be evaluated and enabled where compatible with the release system.

The custom Python updater may remain only as a migration bridge until parity with the official updater is demonstrated.

### Delta strategy

Do not assume that a custom overlay patch is automatically superior.

Benchmark:

- Tauri updater package
- Full installer
- Current overlay delta
- Any future binary/differential delta system

Choose the smallest trustworthy update mechanism that preserves rollback/recovery and does not create file-version drift.

### Migration acceptance

The new Tauri distribution is accepted only when:

- The user-visible product is functionally equivalent or better.
- Performance is equal or better.
- Resource use is equal or better.
- Installer/update reliability is equal or better.
- Signing and integrity checks are equal or better.
- Data/configuration survive updates.
- Very old installations have a documented full-installer recovery path.
- No production route depends on the obsolete packaging path.

## F.4 Installer hardening and lifecycle audit

The installer itself is a product component and must be reviewed independently from the updater.

Audit and validate:

- Fresh install
- Upgrade
- Repair
- Uninstall
- Reinstall
- Per-user installation
- All-users installation
- UAC behavior
- Non-ASCII installation paths
- Spaces in paths
- Existing installation discovery
- Existing-process handling
- Locked files
- Insufficient disk
- Antivirus/Defender interaction
- Interrupted installation
- Interrupted update
- Rollback/recovery
- User-data preservation
- Database/schema migration
- Orphan cleanup
- Uninstall cleanliness
- Start Menu/Desktop shortcuts
- Registry/AppId/DisplayVersion consistency
- Installer signing
- Payload signing
- Hash/signature verification

### Installer data boundary

Define explicitly:

**Application files**
**User data**
**Database**
**Configuration**
**Cache**
**Logs**

The installer/updater must know which category may be replaced, migrated, preserved, or deleted.

Never use broad recursive deletion as a substitute for a versioned data lifecycle.

### Current Inno-specific audit items

The present Inno installer and updater contain several deliberate protections that must be preserved or revalidated during migration:

- Per-user default install with optional elevation
- Existing-install discovery
- Repair/reinstall maintenance choices
- Separate runtime database handling
- Cleanup of stale `_internal` payload during full installer upgrades
- Preservation of user-owned `user.db` and FTS threshold configuration
- Version/registry synchronization
- Installer password handling
- Minisign verification before update installation

These mechanisms should become explicit migration test cases rather than assumptions.

### Installer acceptance

No installer path is accepted from source inspection alone.

Use clean-machine and upgrade-matrix testing and record:

**version → installation mode → operation → result → preserved data → registry state → artifact hash/signature**

## F.5 Desktop window and rendering-stack evaluation

The application already has a native Tauri window concept; **the window container and the web renderer are separate concerns**.

The first research question is therefore not “can the app have an independent window?” — it already can — but:

**Which rendering stack gives BorsTerminal the best combination of correctness, performance, memory use, compatibility, chart capability, startup time, and maintainability?**

### Candidate classes

Evaluate:

1. **Tauri + WebView2 (current Windows target)** — lowest migration cost and strong Windows integration.
2. **Tauri + another platform webview** where officially supported by the target platform — relevant for cross-platform, not a Windows replacement for WebView2.
3. **CEF / bundled Chromium** — evaluate only if a concrete WebView2 limitation is demonstrated; expect larger footprint and additional runtime/update responsibility.
4. **Native UI stack (WinUI 3 / WPF / Qt / Avalonia / similar)** — evaluate only as a true alternative architecture because this is not a drop-in renderer swap and would require substantial frontend/chart/UI migration.

### Mandatory research questions

Measure, do not assume:

- Cold startup
- Warm startup
- RAM idle
- RAM with live market feed
- CPU during market updates
- GPU/frame behavior
- Chart rendering latency
- Large-candle-history performance
- Number of overlays/annotations supported
- Accessibility
- RTL/Farsi behavior
- Clipboard/file dialogs/notifications
- Multi-window behavior
- Process isolation
- Offline behavior
- Windows version coverage
- Installer size
- Update size
- Update reliability
- Security model
- Development/maintenance cost

### Current WebView2 position

For the current React/Tauri architecture, **WebView2 should remain the default candidate unless measurements demonstrate a material blocker**.

Tauri officially uses WebView2 on Windows. WebView2 is Chromium-based and updates through the Evergreen runtime; Microsoft recommends Evergreen for most applications because it reduces storage overhead and receives ongoing performance/security updates.

Do not switch away from WebView2 merely because it is called a “WebView”.

### Fixed versus Evergreen

Evaluate:

- Evergreen WebView2 — preferred default for a normal consumer installation.
- Fixed Version WebView2 — only where reproducibility/offline/compatibility requirements justify the much larger footprint and added runtime servicing responsibility.

Current Microsoft documentation indicates Fixed Version runtimes add a very large package footprint compared with Evergreen, so this choice must be benchmarked against the user's low-resource objective.

### Acceptance

Do not replace WebView2 unless an alternative demonstrates, on real BorsTerminal workloads:

**equal or better correctness + materially better performance/resource usage + acceptable installer/update footprint + acceptable maintenance/security burden**

Otherwise the target remains:

**Tauri + WebView2 + optimized React/chart architecture**

## F.6 Future Technology Stack / Replatform Study — maximize freedom, quality, and long-term capability

This is a **research item, not a current migration order**.

The long-term architecture must remain open to replacing individual technologies — or the entire stack — when evidence shows that doing so would give BorsTerminal materially better performance, resource efficiency, developer velocity, product capability, portability, maintainability, or freedom to evolve.

The question is therefore **not** “Should BorsTerminal use Rust?” and **not** “Should BorsTerminal use React?”

The real question is:

**What technology stack gives BorsTerminal the strongest long-term foundation for a professional financial terminal, advanced charting, real-time market data, Strategy FTS, automation, Android/Desktop clients, local ML, and future capabilities?**

### No technology is sacred

Treat all current choices as revisable:

- Python / FastAPI
- React / TypeScript
- Tauri
- WebView2
- SQLite
- Vite
- current chart libraries
- current state-management libraries
- current packaging/update technology

A working component must not be replaced merely because another language is fashionable. Conversely, no existing component should be protected from replacement when profiling and research demonstrate a better option.

### Candidate technology families

At minimum investigate and compare:

1. **Current Web stack** — React/TypeScript + Tauri + Python/FastAPI + SQLite
2. **Tauri + alternative frontend** — evaluate React against alternatives such as Svelte, Vue, Solid, or other mature options when they provide a measurable advantage for large, highly interactive financial UIs.
3. **Tauri + Rust services/backend** — Rust for local services, hot paths, concurrency, data processing, or selected engines.
4. **Hybrid multi-language architecture** — use the best language per subsystem, with explicit boundaries.
5. **Go desktop stack** — e.g. Wails or comparable architecture when Go materially improves simplicity, runtime/resource use, or developer productivity. Wails uses the OS webview rather than bundling Chromium. 
6. **.NET desktop stack** — Avalonia/WinUI/WPF or related architecture when native desktop capability, tooling, maintainability, or cross-platform needs justify migration.
7. **Flutter/Dart** — evaluate for a unified desktop/mobile UI architecture with native desktop compilation.
8. **Qt/C++/QML** — evaluate for maximum native control, graphics capability, desktop maturity, and long-term performance.
9. **Kotlin Multiplatform / Compose or another modern native/cross-platform stack** — evaluate only where its product and ecosystem advantages are demonstrated.
10. **Other emerging stacks** — may be evaluated when a concrete technical advantage is demonstrated.

These are research candidates, not preselected winners.

### Frontend research is independent from backend research

Do not assume changing the backend requires changing the frontend.

Evaluate separately:

**UI framework → rendering model → state model → chart integration → native bridge → backend/service layer → packaging**

A future BorsTerminal could legitimately use, for example:

**React + Rust**
**Svelte + Python**
**Flutter + Rust**
**Avalonia + C#**
**Qt/QML + C++**
**React + Go**
**React + Python**

or another combination.

### Research dimensions

Use real BorsTerminal workloads, not generic benchmarks.

#### Product capability

- Rich financial tables
- Real-time market updates
- Advanced charting
- Multiple chart engines
- FTS chart annotations
- Complex filters
- Full-universe screening
- Order-book/tape presentation
- Multi-window workflows
- Keyboard/mouse power-user workflows
- Touch/mobile workflows
- RTL/Farsi UI
- Offline mode
- Local ML/inference
- Future trading automation

#### Performance

- Cold startup
- Warm startup
- Time to first usable UI
- Time to first market data
- Time to first chart
- CPU idle
- CPU during live market
- CPU during FTS Funnel/full-universe analysis
- RAM idle
- Peak RAM
- GPU usage/frame stability
- Chart rendering latency
- Large-history chart performance
- Full-universe filtering speed
- Market tick throughput
- Backend latency
- IPC/bridge latency
- Disk I/O
- Battery/power on mobile

#### Engineering freedom

- Ability to access native OS APIs
- Ability to add custom native capabilities
- Ability to implement high-performance engines
- Interoperability with C/C++/Rust/Python/Go/.NET libraries
- Availability of mature packages
- Ease of embedding specialized algorithms
- Ease of adding new chart engines
- Ease of supporting new platforms
- Ease of creating plugins/modules

#### Development quality

- Type safety
- Debugging
- Testing
- Profiling
- Observability
- Static analysis
- Refactoring safety
- IDE/tooling quality
- Build/release complexity
- CI/CD
- Documentation quality
- Community/ecosystem maturity
- Developer hiring/onboarding

#### Deployment and operations

- Installer size
- Runtime dependencies
- WebView/browser dependencies
- Native dependency management
- Update mechanism
- Delta/full update strategy
- Code signing
- Crash recovery
- Rollback
- Offline installation
- Windows support
- Android support
- Linux support if desired
- macOS support if desired

#### Long-term risk

- Project maturity
- Vendor/platform lock-in
- License implications
- Security maintenance
- Breaking-change frequency
- Dependency churn
- Bus-factor concerns
- Long-term support
- Availability of specialist developers

### Architecture patterns to compare

Do not compare only programming languages. Compare complete architectures:

**A. Web UI + local HTTP service**

**B. Web UI + in-process native commands/bridge**

**C. Web UI + native sidecar/service**

**D. Fully native UI + native backend**

**E. Unified cross-platform native UI + shared core**

**F. Hybrid polyglot core with language-specific frontends**

Measure the operational cost and benefit of each.

### Special question: is React still the best frontend for BorsTerminal?

Do not assume the answer.

Research whether React remains the best choice for:

- Very large live tables
- High-frequency numeric updates
- Dense financial dashboards
- Complex chart overlays
- Advanced keyboard workflows
- Fine-grained rendering control
- Memory efficiency
- Mobile responsiveness
- Maintainability at BorsTerminal's eventual scale

Compare against serious alternatives using the actual application, not demo benchmarks.

### Special question: should Python remain in the critical path?

Profile the real application first.

Possible reasons to move parts away from Python:

- CPU-bound hot paths
- high-frequency concurrency
- memory footprint
- startup/package size
- native integration
- long-running reliability

Possible reasons to keep Python:

- data tooling
- scientific/numerical ecosystem
- ML ecosystem
- rapid development
- existing proven business logic
- mature internal tooling

Do not rewrite simply because another language is theoretically faster.

### Special question: should Tauri remain the desktop shell?

Compare Tauri against viable alternatives based on:

- Native window capabilities
- renderer performance
- startup
- memory
- multi-window behavior
- security
- update system
- native API access
- backend integration
- installer complexity
- long-term maintenance

Tauri currently remains the preferred migration target for the Desktop architecture, but this study may overturn that choice if another architecture demonstrates a decisive real-world advantage.

### Migration strategy

If a better architecture is identified:

**prototype → benchmark → prove one subsystem → migrate incrementally → validate → continue**

Do not perform a giant rewrite without a proven migration path.

Allow mixed architectures temporarily when that reduces risk.

Examples:

- Move market tick processing to Rust while keeping Python analytics.
- Move one chart engine or rendering-heavy subsystem to a different frontend stack.
- Keep React during backend migration.
- Keep Python for ML/data tooling while native code owns runtime hot paths.

### Final decision rule

Select the architecture that maximizes:

**correctness + performance + resource efficiency + product capability + engineering freedom + development velocity + maintainability + security + release simplicity**

while minimizing:

**migration risk + operational complexity + ecosystem risk + lock-in + long-term maintenance cost**

### Acceptance

This study is complete only when multiple viable stacks have been compared using representative BorsTerminal workloads and the report contains:

**candidate stack → workload → measurements → capability differences → migration cost → risks → recommendation → confidence**

The result may be:

- keep the current stack
- partially replatform
- replace one layer
- replace several layers
- or perform a staged full replatform

but it must be an evidence-based architecture decision.

Never turn a language preference into an architectural requirement without evidence.

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

# 10. P0/P1 — Maximum performance + minimum resource consumption

Performance is a first-class product requirement, not a cosmetic optimization.

The target is **maximum practical responsiveness and throughput while using the minimum practical CPU, RAM, GPU, disk I/O, network bandwidth, battery/power, and background work required to preserve full functionality**.

This phase must optimize the real application under realistic market conditions, not only synthetic benchmarks.

## 10.1 Non-negotiable principles

- Never improve performance by silently removing analytical capability.
- Never reduce the universe, candle history, indicators, FTS evidence, chart tools, or live data merely to make benchmarks look better.
- Never disable animations or UX behavior solely to hide performance problems; optimize the implementation first.
- Never replace correct real-time data with fabricated, stale, or lower-quality data for performance.
- Do not introduce hidden hard caps such as 60/120 symbols when the product requirement is the full universe.
- Prefer architectural fixes over micro-optimizations.
- Measure before and after every material optimization.
- Optimize Desktop and Android separately where their runtime constraints differ, while preserving one canonical analytical meaning.

## 10.2 Baseline and measurement contract

Before a performance change, record a reproducible baseline.

Measure at minimum:

- App startup time
- Time to first usable market data
- Time to first chart render
- Time to interactive Strategy FTS
- Market update latency
- Backend API latency
- Database query latency
- Full-universe filter/screen time
- FTS funnel processing time
- Chart render/frame performance
- Memory usage at idle
- Memory usage during active market updates
- CPU usage at idle
- CPU usage during market-open/live updates
- GPU usage where applicable
- Network requests per minute
- Network bytes per minute
- Disk I/O
- Android battery/power impact where measurable

Every optimization must report:

**before → change → after → workload → environment → trade-offs**

No “performance improved” claim without measurements.

## 10.3 Full-universe scale

Where the product concept requires the full universe:

- Keep the full dataset available.
- Use virtualization for large tables/lists.
- Use indexed search and filtering.
- Bound only the amount of UI actually rendered, not the underlying analytical universe.
- Batch expensive calculations where safe.
- Avoid repeated full-universe recomputation when only a small subset of data changed.
- Make user-selected limits explicit rather than silently imposed by code.
- Audit every existing cap, slice, LIMIT, page size, query cap, cache cap, and early-return path.

For the FTS Funnel especially:

- Preserve the full candidate universe.
- Use virtualization.
- Eliminate hidden 60/120-symbol caps unless a canonical business rule explicitly requires one.
- Ensure the full-universe result count is consistent across backend, frontend, and export/inspection paths.

## 10.4 Real-time market efficiency

The live market path must be optimized for both responsiveness and resource discipline.

Investigate and measure:

- Polling frequency
- Request duplication
- Request coalescing
- Cache effectiveness
- Incremental versus full refresh
- Payload size
- Compression effectiveness
- Parsing/serialization cost
- Backend fan-out
- Frontend state-update frequency
- Re-render frequency
- Table row virtualization
- Chart update frequency
- Indicator recomputation frequency
- Derived-data memoization
- Worker/background computation opportunities
- Database connection/query reuse

A new market tick should update only the parts that actually changed.

Avoid patterns such as:

**one tick → full database scan → full API recomputation → full frontend tree rerender → full chart redraw**

when an incremental path is valid.

## 10.5 Database and backend efficiency

Profile the entire data path:

**source → ingestion → storage → query → calculation → API → serialization → frontend → rendering**

Investigate:

- Missing/unused indexes
- Expensive joins
- Repeated queries
- N+1 access patterns
- Full-table scans
- Oversized payloads
- Duplicate calculations
- Unbounded in-memory caches
- Serialization/deserialization overhead
- Unnecessary database copies
- Stale/duplicate runtime processes
- Inefficient snapshot loading
- Startup work that can be deferred safely

Any database optimization must preserve exact market/FTS semantics.

## 10.6 Frontend rendering efficiency

The frontend must remain responsive under a live market feed and full-universe workloads.

Measure and optimize:

- React/component rerender frequency
- Large component trees
- Expensive selectors/computations
- Table virtualization
- Chart redraw frequency
- DOM node count
- Layout/reflow cost
- Animation cost
- Number formatting cost under rapid updates
- State fan-out
- Event listener count
- Memory retention/leaks

The numeric transition system defined earlier must remain smooth while avoiding excessive timers, RAF loops, rerenders, or duplicate animation jobs.

## 10.7 Chart performance

Chart correctness and chart performance are both mandatory.

Measure with:

- Large historical datasets
- Multiple overlays
- FTS annotations
- Fibonacci zones
- BOS/CHoCH markers
- MA/indicator layers
- Zoom/pan
- Live updates
- Multiple symbols
- Daily and weekly timeframes

Optimize without changing:

- Candle semantics
- Time/price coordinates
- Indicator formulas
- FTS decisions
- Overlay meaning
- User-visible analytical capability

Prefer incremental drawing/update paths where the chart engine permits them.

## 10.8 Resource ceilings and graceful degradation

Define practical resource budgets for normal machines, including the user's stated low-resource target.

At minimum track:

- CPU
- RAM
- GPU
- Network
- Disk
- Power/battery on Android

The app should degrade gracefully when resources become constrained:

- reduce redundant refresh work
- defer non-critical background work
- pause computations for hidden/off-screen views when safe
- lower update frequency for non-critical secondary visuals
- release unused resources
- avoid runaway queues

Graceful degradation must never silently change canonical FTS or market results.

## 10.9 Cache strategy

Create an explicit cache hierarchy and invalidation policy.

For each cache document:

- What is cached?
- TTL/freshness?
- Invalidation trigger?
- Maximum size?
- Memory/disk location?
- Is stale data allowed?
- Who is authoritative when cache and live data disagree?

Caches must not create semantic drift between Desktop and Android.

## 10.10 Concurrency and scheduling

Audit background work for:

- Duplicate timers
- Overlapping polls
- Race conditions
- Long-running tasks blocking UI
- Unbounded task queues
- Excess worker creation
- Repeated computation caused by dependency churn

Use bounded concurrency.

There must be one clear owner for each recurring market/data job wherever practical.

## 10.11 Android-specific resource efficiency

Android has a stricter resource budget than Desktop.

Validate:

- Startup memory
- Snapshot loading memory
- Database open/read cost
- Chart memory
- List virtualization
- Background work
- Network usage
- CPU during live updates
- Battery impact
- Behavior on lower-end supported devices

Do not solve Android performance by reducing the analytical universe or silently omitting required data.

## 10.12 Performance regression suite

Maintain repeatable workloads:

1. Cold startup
2. Warm startup
3. Market open
4. High-update market period
5. Full 873+ symbol universe
6. FTS Funnel processing
7. Strategy FTS chart with all accepted overlays
8. Fast symbol switching
9. Long-history chart
10. Android offline snapshot load
11. Android live/refresh mode
12. Rapid numeric updates

Track historical results so a later change cannot silently regress performance.

## 10.13 Acceptance gate

A performance optimization is accepted only when:

- Correctness is unchanged.
- Full required functionality remains available.
- Before/after measurements are recorded.
- Resource usage does not regress materially without an explicit reason.
- No hidden capability-reducing cap was introduced.
- Realistic market workloads remain responsive.
- No memory leak, runaway task, or duplicated polling is introduced.
- Desktop and Android behavior remain semantically aligned.

The final target is:

**faster response + lower resource consumption + full analytical capability + stable live behavior**

—not merely a higher benchmark number.

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

---

# 15. Execution state ledger — updated by the running agent

This section is the live state of the roadmap above. Every claim carries a commit, a test, or a
measurement. Nothing is recorded as PASS without evidence; unproven items stay `UNVERIFIED`.

## 15.1 Phase 0 — Android (`arena/fts-mobile-uiux-20261007`, base_main_commit `e23e240`)

| ID | Item | State | Evidence |
| --- | --- | --- | --- |
| A0-1 | Branch consumes canonical `main` | `ACCEPTED` | merge `a02d0b2`; `dev/version_anchor_guard.py` → 6 anchors = 1.0.78 |
| A0-2 | Fundamental shows the full universe | `ACCEPTED-PROVISIONAL` | `b47595a`. Root cause of "59 companies": offline resolver honours `?limit` while `api/screener.py` ignores it, and `useFtsScreen` asked for 60. Baked snapshot holds 873 rows (679 non-excluded), counted from `mobile_snapshot.db.gz`. Pixel proof of 873 rendered rows: `UNVERIFIED` → A3 |
| A0-3 | Chart renders offline | `ACCEPTED-PROVISIONAL` | `2dbc1ab` + `ccd2226`: three raw `fetch()` calls replaced by `http()` (`resolveLocal` is wired only there). Candle contract pulled onto desktop: no `last := close` fabrication, no clamping, `widen()` geometry, zero-volume adjustment signal. On-device pixels: `UNVERIFIED` → A3 |
| A0-4 | Live board overlay completeness | `ACCEPTED` | `tmin`/`tmax`/`d_even` overlaid, `is_live` recomputed like `api/market.py:552`; `mobile-live-overlay.spec.ts` (7 tests, fixture from the desktop `_mw` shape, includes a negative control) |
| A0-5 | Queue / depth view (owner ruling: view only) | `ACCEPTED` | five live `blDs` lines mirror `test_tsetmc.py::book_lines`; resolver test covers live / baked / `no_data` |
| A0-6 | Funnel stage links resolve | `ACCEPTED` | `e80df0b`. `funnelStagePath` emitted `/master/stage/…` with no such route — dead on Desktop too. Live at 360×800: `#/master?stage=technical&preset=trend`, zero `route-not-found` |
| A0-7 | Portrait layout and inspector sheet | `ACCEPTED-PROVISIONAL` | `adc9ae2`: missing `data-shell` attributes added, dead selectors retargeted. Measured 360×800: nav `{y:742,h:58}`, inspector `{w:338, y:39…742}`. Owner visual verdict pending |
| A0-8 | Strategy-tree flow animation restored | `ACCEPTED-PROVISIONAL` | owner ruling "bring it back"; live: `animation-name: fts-path-flow`, `play-state: running`, `data-tree-flow-running=1` |
| A0-9 | Snapshot freshness diagnostics on device | `ACCEPTED` | `933a72a` — package version/`built_at`, screener rows, per-symbol bake counts, candle depth/range, last live board patch |
| A0-10 | Mobile test/type gates locally | `ACCEPTED` | vitest 1486 passed / 0 failed (145 files), `tsc -b` 0 errors, `eslint src` 0, `dev/persian_glyph_guard.py` 4/4 |

## 15.2 Open phase-0 items

| ID | Item | State | Note |
| --- | --- | --- | --- |
| A1 | Snapshot re-bake | `ACCEPTED` | Rebuilt from the current bank: `app_version 1.0.78`, `built_at 2026-10-08T02:34`, `baked_ok 4627`, `baked_fail 0` (1 skip, see D-7). `price_history` 433,922 rows / 6,031 symbols ending **2026-10-07** with `last`/`value`/`src`; universe grew 873 → **922** rows. Published to `mobile-latest`: `mobile_snapshot.db.gz` 62,030,206 B + meta. Cost recorded honestly: the bundled APK asset goes 23 MB → 59 MB gz (raw 126 MB, VACUUM changes nothing) — shrinking it would mean dropping data, which the roadmap forbids; the alternative (ship the APK without a bundle and let the app pull `release`) is a separate owner decision. Codal contract documented: raw codal tables are deliberately not baked, only their cooked output (`screener`, `fundamental/*`, `quarters/*`) |
| A2 | `npm test` in `mobile.yml` | `ACCEPTED` | CI ran it green: job `build-apk` 4m14s on `f91b031` (`npx tsc -b` + `npx vitest run` before `vite build`). The tape-parity corpus is a PC-side artifact (`_audit/*.json` is untracked), so the suite now reports SKIPPED with the exact build command rather than dying in CI — verified both ways: 1484 passed / 3 skipped without it, parity assertions run with it. CI now runs `npx tsc -b` + `npx vitest run` after `npm ci` and before `vite build`, so a red guard can no longer produce an APK. Release tag renamed to `mobile-parity-<sha>` and the notes now carry `base_main_commit`, artifact size and sha256 (D-3 closed) |
| A3 | Final Android verification | `ACCEPTED` | 10/10 measured live at 360×800 and 812×375 on the rebuilt bundle (`_audit/acceptance/*.png`, `acceptance_run*.log`): header **«۶۵۸ شرکت از ۹۲۲»** with virtualization (22-23 rows in DOM) and scroll to `scrollTop 29708`; chart **10 canvases, 5-6 with ink** (empty before the transport fix); all four funnel stages resolve (`/master?stage=…`, `route-not-found=0`, stage card + 15 rows); tree flow `animation-name: fts-path-flow`, `play-state: running`; tape 26 rows, `horizontalOverflow 0`; inspector sheet `{x:22,y:39,w:338,bottom:742}` with the bottom bar `{y:742,h:58}` still visible; landscape nav = 52px side rail `{x:760,w:52,h:375}`; diagnostics reads `v1.0.78`, `433922 کندل · 6031 نماد · 2024-08-24 ← 2026-10-07`, overlay `3924 ردیف`. Offline measured as a phone experiences it — only `*.tsetmc.com`/`github.com` blocked: chart drawn, 26 tape rows. (Blocking the origin also kills the app's own lazy chunks, which live inside the APK — see D-9.) | Harness limit: Playwright's Chromium returns `204`/empty for the 10–23 MB snapshot fetch (0.2 MB works) while `curl` returns 200 — evidence path must avoid that (direct CDP session or documented lightweight bundle) |
| A4 | Final Android release record | `ACCEPTED` | **`mobile-parity-f91b031`** · source `f91b0312df7e915cb40497055837321631a63d9f` · `base_main_commit e23e240bd158130e56c9dc4ad09c4b0688a12fc6` · APK 71,333,163 B · sha256 `2f2de28b9c2ae584e47b252681df056f1cab948b813348f87d8862ce9f718910` · CI green · notes link this ledger. Cost stated honestly: bundling the re-baked snapshot took the APK 33 MB → 71 MB. Bundled stays the default because GitHub reachability from inside Iran is not guaranteed and first run must work offline; shipping without the bundle and pulling `mobile-latest` is an owner decision, not a silent change. Superseded: `mobile-uiux-data-progress-ccd2226` | `mobile-uiux-data-progress-ccd2226`, APK 33,002,123 B, sha256 `88c495ecf204649d887a7ffc75d3fa9ee1b569a2d6271840c8dc6ef99c178eab`; to be re-cut after A1–A3 |

## 15.3 Discovered outside the roadmap (classified)

| ID | Finding | Class | Priority | State |
| --- | --- | --- | --- | --- |
| D-1 | Tape flags on the phone are the baked values; they are not recomputed after the live patch. Frontend-vs-python equality was measured on 1312 perturbed real rows and matched (`tape-fuzz-parity`) | FEATURE GAP | phase 0/1 | `DISCOVERED` |
| D-2 | `instruments` accumulates: 5861 rows in the bank, 2306 with an older `d_even`; the same live endpoint returned 3865 rows today — the bake prunes nothing | DATA HYGIENE | with A1 | `DISCOVERED` |
| D-3 | `mobile.yml` tagged `mobile-uiux-data-progress-<sha>` instead of `mobile-parity-<sha>`, and its notes carried no base commit or checksum | RELEASE DISCIPLINE | with A4 | `RESOLVED` (A2 commit) |
| D-4 | `guards` CI job fails on `main` already: `dev/market_hot_state_v1077.py` reads its schema from `market.db(.lzma)`, which is not tracked, so CI builds an empty bank and asserts "table instruments gone from schema" | CI DEBT | independent | `BLOCKED` (needs a committed schema fixture or an explicit skip) |
| D-5 | Backend gate not run locally this session: a foreign `uvicorn` on 127.0.0.1:8002 shares `market.db` and was not killed | PROCESS | low | `UNVERIFIED` |
| D-6 | Live Codal rate-limit/quota check needs an Iranian egress; `cdn.tsetmc.com` returns 403 from this machine | EXTERNAL | phase 1 | `UNVERIFIED` |
| D-9 | Browser-harness `setOffline(true)` is not phone offline — it blocks the app's own chunks and local snapshot, so a route never mounts; block only external hosts | TEST METHOD | with A3 | `RESOLVED` (probe updated) |

## 15.4 Conflict register

| ID | Conflict | Ruling | State |
| --- | --- | --- | --- |
| C-1 | "Is the style door a gate or evidence?" — `fts-candidate-engine` tests vs `techMark` hierarchy | Owner (2026-10-08): weekly then daily is the judge; setups (jet/fib/point-hunt) are evidence and points only; fibo is context, never a trigger | `RESOLVED` — three tests migrated, the null≠false guard they protected is still asserted |

## 15.6 Data findings from the re-bake

| ID | Finding | Class | State |
| --- | --- | --- | --- |
| D-7 | One screener symbol is stored as `معيار ` — trailing space and Arabic `ي` — in `price_history` and `instruments`; `/api/fundamental/معيار` returns 404 so the bake skipped exactly one of 922 symbols | DATA HYGIENE (canonical layer) | `DISCOVERED` — fix belongs in the shared symbol reader, not in a clamp |
| D-8 | Universe drift: the same canonical `/api/screener` now returns 922 rows where the shipped snapshot had 873 — the old number quoted in reports is stale | DATA | `DISCOVERED` |


## 15.7 Phase 1 — سرخطی: what the audit actually shows

| ID | Item | State | Evidence |
| --- | --- | --- | --- |
| S-1 | Reference repositories | `ACCEPTED` | Already in the repo: `docs/execution/SARKHATI-ARCHITECTURE.md` §۶ names `RezaMahdaviiDev/mofid`, `m-fazel/Sarkhati`, `Sir-Sorg/Stock-Headline-Script-Mofid`, `Mkhorasani99/sarkhat`; §۷ records the license verdict (two with no license, two GPL-3.0 ⇒ no code copied; their 50/100 ms claims are not accepted as facts) |
| S-2 | Engine vs research | `ACCEPTED` | `execution_contract/service/timing/latency/mock` and the `dev/execution_*` guards match doc stages C/D/H/I/J/G; `git grep` across `api/` and `frontend/` is empty ⇒ no router, no UI |
| S-3 | Router + thin UI (dry-run/mock, labelled experimental) | `IMPLEMENTING` | The doc lists stage K as the remaining broker-independent work |
| S-4 | Real-broker stages E/F/G-real/I-live/L | `BLOCKED-OWNER` | D8 (which Mofid platform: EasyTrader/MTS vs Online-Plus/Titan — two protocols, two adapters) and D1 (is a real-account PoC allowed) per §۹-ث. No endpoint, no credential, no order has ever been called |

## 15.10 FTS Funnel → Decision Workspace (owner mission 2026-10-08, audit stage)

The owner's new mission makes the funnel the top priority: **Sarkhati S-3 is paused**
(`api/execution.py` stays uncommitted WIP in this worktree), no Auto-Fibonacci or other
FTS chart feature starts before this milestone is `ACCEPTED`.

| ID | Item | State | Evidence |
| --- | --- | --- | --- |
| F-1 | Canonical filter registry read out of the sources | `ACCEPTED` | 7 TXT filters documented with verbatim thresholds in `docs/fts-notes/FUNNEL-WORKSPACE-AUDIT-1405-07-16.md` §۱; `f_smart`/`f_legal` exist in `tape_flags.py:351-352` but are outside `FILE_FILTERS` (`ftsFunnel.ts:44`) — the funnel registry does not cover the sources |
| F-2 | Judge-location audit | `ACCEPTED` | Four parallel judge stacks listed with file:line (audit §۴). `tapeFilterVerdict` (`tapeAlgorithms.ts:409-414`) prefers the frontend formula over the backend flag, so the frontend is the *primary* tape judge today; `ftsPipelineEvaluator.ts:241-249` judges a 1% clock gap while the TXT and `tape_flags.py:62` say 2% — the mirrors have already diverged |
| F-3 | Fundamental gate audit | `ACCEPTED` | No AND-gate: `api/fundamental.py:1226-1229` yields `WATCH` at `score>=3` even when a blocker failed — measured 307 of 922 symbols with `primary_score<3` today. Missing data: I1/I2/I4 → REJECT (263 / 542 / 84 rows), I5 with an empty sector → PASS (504 neutral rows, 129 of them with no `sector_name`); `PENDING` does not exist in the backend |
| F-4 | Preset provenance | `ACCEPTED` | swing/trend match chart-3 and the notebook; **hourglass has no tape filter in any source** (it is MA52 + weekly RSI5 ≤ 30, already implemented at `api/chart.py:2767-2790`) while `PRESET_ENTRY` currently borrows `f_roobi,f_clock` → `UNVERIFIED`, owner ruling Q-1 |
| F-5 | Hidden caps inventory | `ACCEPTED` | `TECH_QUERY_CAP=60` (`useFtsTechBoard.ts:77`), `watchlist_max=50` gating backend tech enrichment (`screener.py:444-458`, `fts_engine.py:2005-2006`), plus 60/20 limits in adjacent hooks (audit §۶) |
| F-6 | Acceptance-gate mapping (22 items) | `ACCEPTED` | audit §۹ — 3 items partially satisfied, the rest open |
| F-7 | Stage R — canonical filter registry | `ACCEPTED` | `funnel_registry.py`: 7 filters (the five plus `f_smart`/`f_legal`), each with source_file + pinned sha256 + formula_version + backend_impl + 21 params whose values come from `tape_flags` constants, `configurable=True` only where the notebook hands the dial to the user. Guard `dev/funnel_registry_v1.py` (registered in `run_all_tests.py`) checks coverage, hashes, importability, "the number appears in the cited text", and carries a negative control that moves `ruleset_version` (555648ebff52) when a threshold is nudged. `fts_terminal.spec` hiddenimports updated |
| F-9 | Cost of removing the technical-scan cap | `MEASURED` | `_fts_analyze_symbol` on 40 symbols: median **248 ms**, p90 411 ms, max 600 ms → **252 s single-threaded for 922 symbols**. That is why `api/screener.py:456-458` enriches only the 50 watchlist rows. Stage C therefore cannot be a one-line cap removal: it needs one batched candle load + parallel/incremental verdict computation keyed by a scan `as_of`, with the per-symbol 900 s TTL cache kept for the interactive path |
| F-8 | Stages C → E → U → T | `PENDING` | audit §۱۰ — C = batched full-universe technical scan and cap removal, E = `funnel_engine` + `/api/funnel` (sequential intersection, per-stage counts, I1∧I2∧I3 gate with PASS/REJECT/PENDING/UNAVAILABLE, decision trace), U = workspace UI with the frontend judges retired, T = tests + live + 20-symbol TSETMC validation |
| F-10 | Owner rulings Q-1…Q-5 | `BLOCKED-OWNER` | hourglass tape set, `tno>100` in the funnel, `dist>=0` floor, whether 50/10/5-7 (ruling ۶) are visible stage targets or compute caps, and I5-with-no-sector state. None of them blocks stage C or E |

| F-11 | Why the cap exists (measured, not assumed) | `MEASURED` | `_fts_analysis_series` (`api/chart.py:2900-2943`) reads the **CDN chart per symbol** and only falls back to the local bank, so the 248 ms is mostly network. The local bank today: 6031 symbols, but only 1263 with ≥60 sessions, 737 with ≥252, max depth 512, none ≥756 — a local-only scan would silently change verdicts for the shallow rest |
| F-12 | Stage C design (chosen) | `PENDING-BUILD` | Batched **incremental** full-universe technical scan in a new root module: reuse `_fts_analysis_series` + `_fts_analyze_candles` unchanged (one code path, so no board-vs-funnel parity risk), bounded worker pool, skip symbols whose `(symbol, last_close, basis)` already has a stored verdict, write `funnel_tech_scan(symbol, trend_w, trend_d, matrix_decision, hourglass_*, jet_*, basis, as_of, engine_version, ruleset_version)`. `/api/screener` joins that table instead of the per-row call and the `watchlist` flag goes back to being a label, not a compute gate. Cold cost and steady-state cost are both reported before the caps are declared lifted |

| F-13 | Stage C first cut built and measured | `PARTIAL` | `funnel_tech_scan.py` (not wired into `/api/screener` yet): one `funnel_tech_scan` table, `tech_fields_from_fts()` as the **only** copy of the extraction (the screener will call it, so no second judge is created), signature-based incremental reuse, CLI. Re-measured after removing a double history fetch: **serial 0.57 s/symbol → 922 symbols ≈ 8.8 min cold**, a repeat call 0.02 s (cache), `universe()` over 433,922 rows 0.4 s. **Four threads made it 10× worse** (68 s for 12 symbols), so the default is one worker. Remaining: scope the scan to the screener's ~922 symbols (not the 6031 spellings in `price_history`; 3710 traded in `market_watch`, 1263 with ≥60 sessions), wire the screener to the table, then lift `watchlist_max`/`TECH_QUERY_CAP` |

## 15.11 Funnel UX restructure (owner mission 2026-10-08, presentation only)

| ID | Item | State | Evidence |
| --- | --- | --- | --- |
| U-1 | «نقشۀ راه قیف» page deleted | `ACCEPTED` | `FtsFunnelOverview.tsx` deleted; `/master` now opens the stage table itself (`fts-funnel-workspace`), `?stage=` keeps addressing the four stages and defaults to the first |
| U-2 | Three modes in one workspace | `ACCEPTED` | `FUNNEL_MODES` = نوسان‌گیر / روندگیر / Custom in one segmented row; hourglass left out of the selector because no source gives it a tape filter (Q-1) but `?preset=hourglass` still works, so no capability was deleted |
| U-3 | Table is the centre | `ACCEPTED` | The stage hero (title + purpose + 4 stat cards + rule chips) is gone; the duplicate in-table preset picker is gone; counts live on one line above the table |
| U-4 | Reason visible without a second page | `ACCEPTED` | New `دلیل` column renders the engine's own reason string per row (it was only a `title` tooltip before, invisible on touch) |
| U-5 | Stage survives a row click | `ACCEPTED` | `pick()` navigates to `/master/<symbol>?stage=<active>`; the workspace also falls back to the Task-#78 snapshot. Found by the retargeted snapshot test, which had passed only because the deleted overview page never consumed the snapshot |
| U-6 | Custom: pick filters | `PARTIAL` | Selection works through the existing board chips (`funnel-tape-chip-*`) shown in the tape stage; **reordering the chain is not built yet** and the engine still intersects the picked set as a set, so order is display-only until stage E |
| U-7 | Browser validation | `ACCEPTED` | `tools/jev_ui_check.mts` at 1366/1920/360 → `_audit/funnel_workspace_check.json`: three modes present, no overview page, `دلیل` present, `pageOverflowX: 0` at every width. One React "setState during render" warning appeared only in the 1366 run and its cause is not yet isolated - recorded, not dismissed |
| U-8 | Logic untouched | `ACCEPTED` | No change under `lib/ftsFunnel.ts`, `tape_flags.py`, `fts_engine.py` or `api/*` in this commit; tsc clean and 1444 passed / 3 skipped |

## 15.12 Final Funnel milestone (owner mission 2026-10-08, §1-46) - IN PROGRESS

| ID | Item | State | Evidence |
| --- | --- | --- | --- |
| X-1 | Re-audit before coding | `ACCEPTED` | §15.10 F-1..F-13 plus this round's re-read of the current tree (the UX commit changed the files the earlier audit described, so the audit was redone against `d0314b6`, not against the report) |
| X-2 | Canonical backend judge | `ACCEPTED` | `funnel_engine.py` + `api/funnel.py` (`GET/POST /api/funnel`, `GET /api/funnel/registry`). Guard `dev/funnel_engine_v1.py` = the mission's 22 required cases, each with expectations written outside the engine. Registered in `run_all_tests.py`, in `fts_terminal.spec` hiddenimports, and in `api/__init__.py` |
| X-3 | Sequential intersection is real | `ACCEPTED` | Live smoke on this bank: `custom [f_susp, f_noqteh]` = 5865 → 121 → 4, and `[f_noqteh, f_susp]` records different per-stage counts. Guard case 3 fails if OR logic leaks (it would match 2) |
| X-4 | Weekly-first technical gate | `ACCEPTED` | down/neutral reject, up only then daily, branch map per the four-page chart, `UNKNOWN` = PENDING not reject; guard case 12 proves jet+CHoCH+5 points never break a weekly veto |
| X-5 | Fundamental hard/standard/exception | `ACCEPTED` | standard blocks on I1∧I2∧I3, hard requires all five, missing data is PENDING, exception keeps `canonical=REJECT` beside `effective=PASS WITH EXCEPTION` with the indicator and reason code in the trace; a wrong exception does nothing |
| X-6 | Handover ranking without invented weights | `ACCEPTED` | final → no-exception → existing fundamental score → existing technical points → backend rank → symbol, with `display_rank`; 1200 in = 1200 out and the engine source contains no slice |
| X-7 | **Frontend still runs its own judge** | `OPEN - BLOCKING` | `lib/ftsFunnel.ts` (`buildFunnel`, `techMark`, `fundMark`) and `tapeAlgorithms.tapeFilterVerdict` are still the browser-side verdict path used by the table. Until the table renders `/api/funnel`, the mission's "one judge" rule is NOT met and the funnel cannot be called complete |
| X-8 | Custom builder (add/remove/reorder/save presets) | `OPEN` | Registry is served and the chain is honoured by the engine; the UI control does not exist yet |
| X-9 | Hidden caps | `OPEN` | `TECH_QUERY_CAP=60`, `watchlist_max=50` gating tech enrichment, and `scan_all[:cap]` all still stand. `funnel_tech_scan.py` is built and measured but not wired |
| X-10 | React "setState during render" | `OPEN` | Seen only in the 1366 live run; cause not isolated yet |
| X-11 | 3 skipped tests | `OPEN` | Classified as required by §42, not yet resolved |
| X-12 | TSE/TSETMC validation, browser validation, inspector | `OPEN` | §24, §33, §40 |

### Order of the remaining work (each its own commit)

1. `useFtsFunnel` → fetch `/api/funnel` (POST with chain/fund_mode/params/exceptions) and
   return the server payload unchanged; delete `buildFunnel`/`techMark`/`fundMark` verdicts
   and make `tapeFilterVerdict` read the backend flag (the live-board mirror stays only as a
   parity-guarded display path, or dies).
2. Custom builder in the workspace header: registry-driven add/remove/reorder + saved
   presets (ordered ids, parameter set, registry+formula version, fundamental mode,
   technical settings, timestamp).
3. Handover table + inspector with the trace (§23, §24), progressive disclosure.
4. Wire `funnel_tech_scan` into `/api/screener`, lift the caps, re-measure.
5. Isolate the React warning, classify the skipped tests, browser validation at
   1366/1920/360, TSETMC validation on >= 20 real symbols.

**FINAL STATUS of the milestone: NOT COMPLETE.** Backend decision layer is accepted;
the frontend still judges, so the funnel is not yet "one canonical engine + a renderer".

## 15.14 Funnel integration is green on `funnel-api-wip` (2026-10-08, later in the same day)

Owner instruction: continue on the branch and fix the harness, do not drop the canonical
backend. Done - the branch is green and the UI no longer judges.

| commit | what |
| --- | --- |
| `5a34395` | the funnel spec now renders a hand-written `/api/funnel` payload; 15 cases replace the 42 that called `buildFunnel`; `StageRow` takes its stage key so the tape card's دلیل column stopped rendering «—» for every row; `moved()` applies the destination index after removal; `useFtsFunnel` read `portfolio.data` as an array (it is `{status, decisions,...}`) and crashed three master specs as unhandled exceptions |
| `93af3bc` | `SymbolInspector` reads `stageProgressFor(funnel, symbol)` from the same answer instead of re-running `symbolStageProgress` on one symbol; statuses are merged per stage because the tape row only carries `status.tape` |

Evidence, all run after the last change: `tsc` 0 errors, **1417 passed / 3 skipped (139
files)**, no unhandled errors; `funnel_engine` guard 26/26, `funnel_registry` guard 7 filters /
21 params, `persian_glyph_guard` 4/4.

### §37 verified - the runtime no longer imports any browser-side judge

`grep` over `frontend/src` (excluding `__tests__`) for `buildFunnel`, `symbolStageProgress`,
`funnelUniverse`, `techQueryQueue`, `useFtsTechBoard`: the only remaining hit is a **type**
import (`TechVerdict`) inside `lib/ftsFunnel.ts`. Everything else is prose in comments.

### What is still dead-but-present (attempted this session, reverted)

`buildFunnel`, `evaluateCandidate`, `symbolStageProgress`, `funnelUniverse`, `techQueryQueue`,
`tapePickedSymbols`, `officialRankMap`, `orderOfficial`, `techFromScreen`, `techFromVerdict`,
`technicalDailyBranch`, `technicalEvidencePoints` and `api/useFtsTechBoard.ts` (which owns
`TECH_QUERY_CAP = 60`) are unreferenced by the app but still in the tree, and
`__tests__/fts-candidate-engine.spec.tsx` still exercises them.

A first deletion pass mangled `ftsFunnel.ts` (line-slice removed the tail of the `Candidate`
type and duplicated `Funnel`/`FunnelStage`), so the file was restored from HEAD and the branch
was left green. **The deletion is not a text-slicing job**: it needs the type block, the two
`import type` lines and the candidate-engine spec handled together, then `tsc` as the gate.

### Still open before ACCEPTED

1. DONE (15.15): the dead judges, `useFtsTechBoard` and `fts-candidate-engine.spec.tsx` are
   deleted; decision coverage lives in the 38 python bands only.
2. Custom builder UI in the workspace header (state is ready: chain, moveFilter, savedChains).
3. Handover columns + inspector fed by `timeline`.
4. PARTLY DONE (15.15): `funnel_tech_scan` is wired into `/api/funnel` (verdicts come from
   the scan table, not the top-50). Still open: `/api/screener` enrichment + weekly veto
   remain capped at `watchlist_max`, and `scan_all[:cap]`.
5. React "setState during render" root cause; classify the 3 skipped tests.
6. Browser validation 1366/1920/360 with `_audit/funnel_final_*.json`; TSETMC on >= 20 symbols;
   full-universe benchmark.

Release: still not built. Funnel: IMPLEMENTING (one step closer - the UI now renders the
canonical answer).

## 15.15 Completeness rule enforced end to end (2026-10-08 / 1405-07-16, later the same day)

Owner rule: «هیچ نمادی نباید با وضعیت «سنجیده نشده» از Funnel خارج شود» plus the
mandatory guard `input universe count == output evaluated-symbol count`.

Backend (commit `1ffd11a`, `d10f618`):
- `status_matrix()` + `coverage` in `funnel_engine.py`: one explicit status per symbol per
  stage, with `reason_code` + `human_reason`. Five statuses: pass / reject / pending /
  unavailable / **not_required**.
- Universe is keyed by normalized symbol; duplicate board rows are reported
  (`duplicate_rows`) instead of silently double-counting.
- Live identity on this bank: `board 5865, screened 922, joined 5863, duplicate_rows 2`;
  every stage sums to 5863.
- `technical_stage()` now takes `tech_scan` + `tech_sigs` and separates three honest cases:
  verdict available -> judge; history exists but the scan has not run -> `PENDING` /
  `TECH_SCAN_PENDING`; no price history at all -> `UNAVAILABLE` / `TECH_NO_HISTORY`.
- Stop reasons are status-aware (`stop_text`): a pending upstream stage no longer claims the
  symbol was "rejected".

API:
- `GET /api/funnel/trace?symbol=` serves the per-symbol timeline on demand; the list
  response drops `timeline` - payload **18.9 MB -> 9.1 MB** with identical decisions.
- `_tech_context()` reads verdicts from `funnel_tech_scan` (60s cache) instead of the
  screener's enriched top-50; leftovers are queued into a background thread, so no HTTP
  request ever waits for a scan.

Measured cost of the scan (this bank, 4 real tape survivors): 99.5 s for 4 symbols
=> ~25 s per cold symbol (history fetch), 0.02 s when the stored signature matches.
A cold full 922-symbol pass is therefore **hours**, not the 8.8 minutes the earlier
0.57 s/symbol figure suggested - which is exactly why it is background + PENDING.

Frontend (P0 second judge removed):
- `ftsFunnel.ts` 920 -> ~260 lines: `buildFunnel`, `evaluateCandidate`, `techMark`, `fundMark`,
  `tapeMarkOf`, `tapeRows`, `symbolStageProgress`, `funnelUniverse`, `techQueryQueue`,
  `orderOfficial`, `officialRankMap`, the `techFrom*`/`technical*` helpers and `FUNNEL_TARGETS`
  are gone. What remains is types, labels and display metadata only.
- `api/useFtsTechBoard.ts` deleted - its `TECH_QUERY_CAP = 60` was a decision queue (case B of
  the cap table). `__tests__/fts-candidate-engine.spec.tsx` deleted with it (classification:
  OBSOLETE - it tested the browser judge that no longer exists; decision coverage is the
  38 python bands).
- `funnelFromApi()` builds one row per universe symbol per stage from `status_matrix`,
  enriched by that stage's own rich row; counts come from backend `coverage`.
- Every stage table now renders the whole universe (virtualized body + virtualized pending
  group), the header shows the five statuses and «حکم: N = کلِ universe», and the tab badge
  shows the pass count. `not_required` = «لازم نبود» in labels, dots, badges, dossier, details.
- Background scan progress is visible: «تکنیکال در انتظارِ اسکن: N».

Gates: `tsc -b` 0 errors; `vitest run` 1400 passed / 3 skipped / 138 files;
`funnel_engine_v1` OK (38 bands); `funnel_registry_v1` OK (7 filters, 21 params);
`persian_glyph_guard` 4/4.

Open: `api/screener.py` still computes `tech_*` only for `watchlist_max=50` rows and applies
the weekly veto only to them - the funnel no longer depends on it, the screener table does.
Also open: Custom builder UI, handover inspector from `/api/funnel/trace`, the React warning,
classifying the 3 skipped tests, browser + TSETMC validation, full-universe benchmark.
Today's live funnel ends at 0 PASS with explicit reasons (the tape survivors are ETFs:
no codal coverage, and the weekly judge rejects or cannot classify them).


## 15.16 Funnel validation: warning fixed, browser walked, benchmark and TSETMC measured (2026-10-08)

React warning (`122143d`) — reproduced, root-caused, not suppressed:
`Warning: Cannot update a component (%s) while rendering a different component (%s)`
with the substituted names printed after the string; stack
`dispatchSetState <- Topbar.tsx:47 <- query-cache Set.forEach`. Cause:
`useFeedSnapshot` calls `setSnap` synchronously from the TanStack Query **cache
subscription**, and mounting the funnel's observer notifies that subscription
during `FtsFunnelStages`' render phase. Fix: defer the listener body one
microtask. Now **0 errors / 0 warnings at all three viewports** (was 6 at 1366).

Live browser walk `_audit/funnel_final_check.mts` -> `_audit/funnel_final_dev2.json`
+ `funnel_final_{1366,1920,360}.png`, against the real backend on this worktree:

| viewport | pageOverflowX | table px / box px | reason cells | ruled vs universe | technical not_required |
| --- | --- | --- | --- | --- | --- |
| 1366x768 | 0 | 1196 / 1198 | 18 of 18 filled | حکم ۵۸۶۳ = کلِ universe | ۵۷۶۱ لازم نبود |
| 1920x1080 | 0 | 1670 / 1672 | 18 of 18 | same | same |
| 360x800 | 0 | 278 / 280 | 18 of 18 | same | same |

Steps executed at every viewport: enter (default = tape) -> swing -> trend ->
custom -> add two registry filters -> reorder -> remove -> save -> reset ->
load -> row click -> technical -> fundamental -> handover -> back.
Ordered intersection proved by the UI's own numbers: `[f_clock, f_susp]` printed
`f_clock ۵۸۶۳ ← ۵۰`, `[f_susp, f_clock]` after reorder printed
`f_susp ۵۰ ← ۱۹` / `f_clock ۵۸۶۳ ← ۵۰`.
Row click kept the stage (`?stage=technical` - bug found and fixed: `pick()` used
the component's internal active instead of the routed one) and Back returned to it.
Registry gave 7 filters including `f_smart` / `f_legal` (the old five-chip list is gone).

Two more defects the walk exposed and fixed:
- switching preset/chain blanked the dominant table to `universe: ۰` for the whole
  POST; now `placeholderData: keepPreviousData` + an explicit «در حالِ تازه‌سازی» chip.
- the inspector collapsed `not_required` into `unknown` («سنجیده نشده»); it is now its
  own state with «لازم نبود» and the blocking stage in the title.

Skipped tests classified (§28) - all three were **FIXED**, not accepted as skipped:
they needed fixtures that did not exist on this machine. Built from the live bank:
`_audit/live_rows.json` (5865 rows from /api/market) and
`tools/tape_parity_fuzz.py --rows 140` => 1312 mutated cases.
`tape-fuzz-parity` 2/2 pass; `tape-badge-chip-parity` 8/8 pass including the
three-way live check (backend flag == frontend formula == row badge) for all five
filters: f_clock [50,50,50], f_susp [102,102,102], f_jet [8,8,8], f_roobi [19,19,19],
f_noqteh [17,17,17]. `_audit/*` stays gitignored by design (PC gate, not CI).

Full-universe benchmark (§35) `tools/funnel_universe_benchmark.py` ->
`_audit/funnel_universe_benchmark.json`: universe 5863 (board 5865, 2 duplicate rows
deduped, screened 922), `evaluate()` 1.87-2.34 s per case, peak 40-48 MB, six cases
(swing / trend / two custom chains / empty chain / hard fundamental), cache cold
2113 ms -> warm 902 ms (the remaining cost is serialising the answer), concurrency:
`evaluate()` is single-threaded and the technical verdicts are built in a background
thread, never awaited by a request. `no_truncation_proof: true` - every case has
`matrix rows == universe` and every stage's five statuses sum to the universe.

TSETMC/TSE validation (§32-33) `tools/tse_live_filter_parity.py` ->
`_audit/tse_filter_parity_final.json`, live at 21:38 against the app snapshot of
21:18 (7207 comparison rows, 2273 traded):

| filter | site | app | match | only_site | only_app |
| --- | --- | --- | --- | --- | --- |
| clock | 49 | 50 | 49 | 0 | 1 |
| susp | 102 | 102 | 102 | 0 | 0 |
| jet | 8 | 8 | 8 | 0 | 0 |
| roobi | 18 | 19 | 18 | 0 | 1 |
| noqteh | 17 | 17 | 17 | 0 | 0 |
| smart | 143 | 147 | 143 | 0 | 4 |
| legal | 34 | 34 | 34 | 0 | 0 |

Every one of the 6 `only_app` rows classified in `_audit/funnel_tse_diff_classify.py`:
**all DATA_DIFFERENCE, zero RULE_DIFFERENCE, zero BUG** - one symbol is absent from
the site's live `GetMarketWatch` payload, the other five differ on `zd1/bp/sp/sn/h_len`
(their clientType and history inputs are not identical between the two snapshots).
An earlier draft of that probe compared only five fields and mislabelled them
RULE_DIFFERENCE; the instrument was wrong, not the app - the check now compares all
ten variables the formulas read.

Open before ACCEPTED: /api/screener's own `tech_*` enrichment and weekly veto are
still limited to `watchlist_max=50` rows (the funnel no longer depends on them);
the technical scan covers 16 of 6032 symbols with history and is ~25 s per cold
symbol, so the universe-wide verdicts are still filling in the background;
handover columns + the trace-fed inspector (§21-22); the same completeness counters
on Android (§9); owner questions Q-1..Q-5.


## 15.5 Next item selected

* superseded by §15.17 (2026-10-09): U-6 and the Custom builder are done, the funnel consumes
the canonical engine, and the next cut is the AssemblyEvent unit in
`docs/ASSEMBLY-EVENT-PLAN-1405-07-17.md`. The text below is kept as written then.*

**FTS Funnel stage U-6 then C** — first the Custom chain editor (order controls over the
already-picked filters, display-only until the engine consumes the order), then replace the
per-symbol technical enrichment of the top-50
(`api/screener.py:456-458`, `fts_engine.scan_all` `[:cap]`) with one batched full-universe
scan (single candle load, parallel verdicts, scan-level `as_of`), then measure the cold
rebuild. Stage E builds the intersection engine on top of it.
Phase 1 **S-3** (execution router) is `PAUSED` by the owner's mission until the funnel milestone
is `ACCEPTED` (`api/execution.py` sits uncommitted in this worktree); S-4 stays
`BLOCKED-OWNER` (D8/D1). Phase 2 (trading bot) is not started: the bot must consume the
canonical FTS signal rather than judge again.


## 15.17 WS-7 — دو جامعه، واژگانِ غربالگری، walkِ واقعیِ واچ‌لیست (۱۴۰۵-۰۷-۱۷)

 پنج کار درِ این دور نشست (branch `funnel-api-wip`، پنج کامیت):

| کار | حکم | شاهد |
| --- | --- | --- |
| جامعۀ تابلو ≠ جامعۀ غربالگری | **پیاده و زنده** | `X=5863 / Y=3655 / Z=2208`؛ `X=Y+Z`؛ `docs/SCREENING-UNIVERSE-LIVE-STATE-1405-07-17.md`؛ `_audit/ws7_universe_check.mts` |
| live ≠ «امروز معامله داشت» | **اثبات‌شده از داده** | ۳۹۹۲ ردیفِ نشستِ جاری که ۱۷۰۵شان بی‌معامله‌اند؛ شاهدِ مستقلِ `price_history` ۲۲۹۲ |
| «NOT IN SCREENING UNIVERSE» | **وضعیتِ ششمِ رسمی** | `not_in_universe` درِ matrix/trace/رابط؛ نه reject، نه «سنجیده نشده» |
| گاردها | **۴۲ بند سبز + کنترلِ منفی** | `dev/funnel_engine_v1.py` ۳۸-۴۱؛ جهشِ عمدی → ۷ FAIL → بازگشت از copy |
| rename: Funnel → غربالگری | **فقط متنِ دیدنی** | ۲۲ رشته درِ ۱۴ فایل؛ walkِ DOM درِ پنج مسیر: صفر «قیف»؛ `_audit/ws7b_rename_check.mts` |
| walkِ واقعیِ واچ‌لیست | **۱۰/۱۰ سبز** | optimistic (فقط POST+GET)، ماندگاری با reload، سطر درِ Portfolio → پرتفوی فعلی، ستارۀ بنیادی، حذف؛ `_audit/ws7c_watchlist_walk.mts` |
| `/api/watchlist/matrix?symbols=` | **از مرگ برگشت** | `no such table: instruments` → حالا verdict می‌دهد؛ تفکیکِ `USER_WATCHLIST_MAX` / `MATRIX_PROBE_MAX`؛ گارد ۱۳ بند |
| `api.funnel` درِ hiddenimports | **نقصِ ریلیزِ واقعی برطرف** | EXE رویِ اولین `/api/funnel` می‌مرد؛ `onedir_contract_v11` الان PASS |

open, in this order:

1. **Sidebar «در یک نگاه»** (رأیِ ۱: حذفِ Quick Scan به‌عنوان قابلیتِ مستقل؛ رفتارش
   کلیکِ نماد ⇒ داوریِ هدفمندِ کامل ⇒ سایدبار). امروز هیچ «Quick Scan»ی درِ این
   کارتر ساخته نشده بود، پس چیزی برای حذف نیست؛ کاری که مانده ساختِ همان سطرِ
   «در یک نگاه» است (تک‌نگار: `stageProgressFor` سطرِ خارج از جامعه را هم می‌دهد).
2. **AssemblyEvent** — مدلِ canonical از sourceهایِ راستی‌آزمایی‌شده
   (`Codal/GetPreparedDataByInsCode`، `MarketData/GetInstrumentState`،
   `GetInstrumentShareChange`)؛ `DPS = UNAVAILABLE`؛ `decision_date = null` بی‌دادهٔ
   ساختاریافته؛ تاریخِ انتشار با labelِ خودش. کامنتِ گمراه‌کنندۀ
   `codal_fetcher.py:3588-3590` هم درِ همین بند.
3. **Android parity** — واژگانِ «غربالگری»، واچ‌لیست، و شمارشِ تکمیلِ جامعۀ
   غربالگری درِ `BorsTerminal-android` (کارترِ جدا).
4. **زنجیرۀ acceptance روند** (Trend milestone): G1 candle parity، corpusِ
   دستیِ ۳۰-۵۰ نماد، Rahavard/TradersArena فقط به‌عنوان مرجع، و
   `docs/validation/FTS-TREND-VALIDATION.md`. G3/G5/G6/G7 سبزند
   (`dev/fts_trend_pit_v1.py`، ۱۳ بند)؛ **parityِ بیرونی هنوز UNVERIFIED**.

still red in this worktree *and* in the untouched one (not caused by this work,
each with identical counts): `tape_filters_v1034` 214/2، `test_fts_technical_tristate`
32/37، `test_fts_roundj` ۱ سرخ، `chart_api_check_v95` (فایلِ بایگانیِ gitignored).

pilot jev: سه درخواستِ داوری درِ دوراهیِ «نبودِ ردیفِ وضعیت» هر سه `read timeout`
دادند ⇒ آن تصمیم **UNVERIFIED-BY-PILOT** ثبت شد و قضاوتش با مالک است.
Release ساخته نشد (milestone هنوز ACCEPTED نیست).


## 15.18 ارزشِ بازار درِ سایدبار، و یک مبنایِ واحد برای I4 (۱۴۰۵-۰۷-۱۷)

Addendum به spec از مالک: «ارزش بازار باید در Sidebar → در یک نگاه باشد» و I4 باید
**همان** canonical market cap را مصرف کند.

چه چیزی به‌عنوان canonical پیدا شد (هیچ‌چیز اختراع نشد):

| پرسش | پاسخ با شاهد |
| --- | --- |
| آیا TSETMC برای *هر نماد* `marketValue` ساختاریافته می‌فرستد؟ | **نه** — سنجش‌های زندۀ پروژه: `docs/fts-notes/FUND_LIVE_AUDIT.md:306-313`؛ فیلدِ ساختاریافته فقط در سطحِ *بازار* وجود دارد (`GetMarketOverview.marketValue/marketValueBase` → `market_totals`) |
| پس منبعِ جاریِ هر نماد چیست؟ | ستونِ رسمیِ `market_watch.market_cap` + برچسبِ منشأِ `market_cap_src`؛ درِ این بانک: ۴۶۷۳ `tse_board_calc` + ۳۹۷ `tse_board_calc_backfill` + **صفر** `tse_raw` |
| تعریفِ واحدِ کد کدام است؟ | `fts_engine.mcap_bulk_expr` (ستونِ رسمی ← آخرین `daily_prices` معتبر) با دروازۀ یک‌تعریفِ «بانِ مرده» (`mcap_dead_band_sql`) — همان که از نسبتِ ۱۴۱۳٫۷۵× جعلی جلوگیری می‌کند |

انجام‌شده:

- تابلو حالا خودِ عدد را می‌فرستد: `/api/market` ردیف‌ها را با `mcap`/`mcap_src`
  برمی‌گرداند (۵۰۷۰ از ۵۸۶۵ ردیف دارایِ عدد؛ بقیه **بی‌داده**، نه صفر) و سایدبار
  «در یک نگاه» یک سطرِ `ارزشِ بازار … · I4 …` با titleِ منشأ/تازگی دارد.
- **یک فرمول، دو سطح:** سایدبار دیگر عبارتِ دومِ خودش را ندارد — `api/market._board_sql`
  دقیقاً `mcap_bulk_expr(conn, alias="i", board="m")` را می‌نشاند. سنجشِ زنده:
  روی ۵۰۷۰ ردیف، عددِ سایدبار با مخرجِ I4 درِ `confidence_engine.mcap_map`
  **صفر اختلاف** است.
- I4 از مبنایِ دومی جدا شد: `conf_fund` پیش‌تر `p_closing × total_shares` را خودش
  می‌ساخت. حالا همان canonical را می‌خواند. اثرِ واقعی (و این تغییرِ حکم است، نه
  فقط نام): از ۳۹۹۱ ردیفِ زنده، **۴۷۵ ردیف هیچ مبنایِ معتبری ندارند** و I4شان
  از این پس `None` (بی‌داده) است نه یک عددِ ساخته‌شده؛ درِ نمونۀ ۴۰۰تایی ۱۱۴ ردیف
  «بانِ مرده» دارند و به تاریخچۀ معتبر می‌روند.
- هزینۀ اندازه‌گیری‌شده: ساختِ سردِ تابلو ۱٫۱۵s ← **۱٫۵۴s**؛ مسیرِ کش‌دوست ۰٫۰۶s.
- یک رگرسیونِ واقعی که خودم ساخته بودم و گارد گرفت: `dev/board_hist_cache_v1056.py`
  و `tools/tape_formula_parity.py` متنِ `_BOARD_SQL` را با regex از فایلِ منبع
  برمی‌دارند و **مستقیم اجرا** می‌کنند؛ توکن‌های `@MCAP@` آن متن را بی‌اجرا کرده بود
  (`unrecognized token`). متنِ پایه حالا `CAST(NULL AS REAL)` قابل‌اجرا دارد و
  `_board_sql` فقط وقتی ستون هست آن را با عبارتِ canonical عوض می‌کند. گارد ۲۴/۰ سبز.
- گارد `dev/watchlist_matrix_v973.py`: ۵۱ چک، ۰ خطا (چهار بندِ تازه: نقشه یکی،
  برابری با ستونِ رسمی روی ردیف‌هایِ پذیرفته‌شدۀ دروازہ، نبودِ productِ محلی درِ
  conf_fund، و استفادهٔ سایدبار از همان `mcap_bulk_expr`).

هنوز باز ( ACCEPTED نیست ):

1. **سطرِ سایدبار درِ مرورگر زنده هنوز عدد نمی‌دهد — و این ادّعایِ PASS نیست.**
   `_audit/ws7d_sidebar_mcap_check.mts` اجرا شد: سطرِ `ارزشِ بازار … I4 …` رندر
   می‌شود ولی متنش `بی‌داده` است، در حالی که **همان پاسخ** وقتی درِ همان صفحه با
   `fetch('/api/market')` خوانده می‌شود برایِ ۵۰۷۰ ردیف `mcap` دارد (نمونۀ تست
   «آباد»: ۱٫۴۳ همت). یعنی عدد تا مرورگر می‌رسد و درِ رابط گم می‌شود.
   `MarketFeedSchema → MarketRowSchema` هر دو `mcap` را دارند (`marketRow.ts:39-40`)
   و خوراک هم همین schema را مصرف می‌کند (`marketFeed.ts:105`)، پس دو فرضیه مانده
   و یکی درمیانی را باید دید: (الف) `rawRow` برایِ آن مسیر `null` است
   (تشبیهِ نماد درِ سایدبار) و «بی‌داده» از نبودِ *ردیف* است نه نبودِ کلید؛
   (ب) سازندۀ ردیفِ نرمال‌شده، کلیدهای تازه را نمی‌گذراند.
   گامِ بعد: چاپِ `Object.keys(rawRow)` درِ همان صفحه، بعد از آن اصلاح درِ
   همان لایه. تا این دو حالت روشن نشود، بندِ «UI evidence» برایِ ارزشِ بازار
   **UNVERIFIED** می‌ماند.
2. **ترتیبِ کاملِ «در یک نگاه»** همان لیستِ مالک (نماد ← قیمت ← تغییر ← حجم/ارزش
   معاملات ← ارزش بازار ← قدرت خرید/فروش ← وضعیت تابلو ← تکنیکال ← بنیادی ←
   غربالگری FTS ← رویدادها) هنوز بازچینی نشده؛ سطرِ ارزشِ بازار فعلاً بعدِ
   قیمت/درصد نشسته است.
3. تازگیِ I4: عدد از ردیفِ اسکرینر می‌آید، پس با هر تیکِ قیمت تازه نمی‌شود.
   رفتاری که مالک خواست («I4 با تغییرِ مخرج، بی‌recomputeِ کلِ بنیادی تازه شود»)
   یعنی ratio از `sales(as_of ثابت) ÷ mcap(جاری)` درِ لحظۀ خواندن ساخته شود —
   این **هنوز ساخته نشده** و UNVERIFIED است؛ کلیدش این است که حکمِ موتور دومی
   ساخته نشود، فقط عددِ نمایشی با asofِ خودش برود.


## 15.19 سه رأیِ تازه (ارزشِ بازار) + milestone جدیدِ «وضعیت بازار» (۱۴۰۵-۰۷-۱۷)

رأی‌هایی که بعد از §15.18 آمد و **هنوز اجرا نشده‌اند** (به‌همین دلیل milestone
ACCEPTED نیست):

1. **حکمِ I4ِ موتور دست‌نخورد؛ عددِ سایدبار live باشد.** سازۀ نمایشی:
   `sales(as_ofِ ثابت) ÷ market capِ جاری` با `as_of` و sourceِ خودش؛ اگر با
   حکمِ cachedِ موتور می‌خواند همان عدد، اگر نمی‌خواند **اختلاف صریح نشان
   داده شود** (نه quiet overwrite). جایِ ساختن: `SymbolInspector` (نمایشی) —
   موتورِ بنیادی و `fts_engine.sales_to_marketcap` بی‌تغییر می‌مانند.
2. **بازچینی کاملِ «در یک نگاه» درِ همین milestone**، به ترتیبِ specification:
   نماد ← قیمت ← تغییر ← حجم/ارزشِ معاملات ← **ارزشِ بازار** ← قدرتِ خرید/فروش
   ← وضعیتِ تابلو ← تکنیکال ← بنیادی ← غربالگری FTS ← رویدادها. هیچ
   capability حذف نشود؛ پنجرۀ ۵ مظنه و جزئیاتِ معاملات به Page 2
   («جزئیاتِ بازار») می‌روند و سوییچ هر دو page محلی و فوری است.
3. **auditِ منشأ انجام شد** و نتیجه در `docs/TSETMC-MARKET-CAP-SOURCE-AUDIT-1405-07-17.md`:
   TSETMC هیچ `marketValue` هر-نمادی از هیچ مسیرِ راستی‌آزمایی‌شده نمی‌فرستد
   (detail pathها SPA-shell برمی‌گردانند؛ `GetInstrumentInfo` = 404)؛
   `marketValue` فقط سطحِ بازار است. `market_watch.market_cap` canonical
   می‌ماند **برایِ I4** ولی با ارزشِ بازارِ TSETMC هم‌خوان نیست:
   Σ ردیف‌هایِ live ما ۴۶۱٫۵ میلیون‌میلیون ریال در برابرِ ۲۷۰٫۲
   بازار ۱+۲ ⇒ **۷۰٫۸٪+** (فقط سهام+حق‌تقدم: ۵۱٫۶٪+). طبقه:
   DEFINITION DIFFERENCE. اگر مبنایِ شناور برای I4 خواسته شود، تعویضِ
   تعریفِ شاخص است و رأیِ مالک را می‌خواهد (با این ارقام، نه با تنظیمِ آستانه).

گامِ بعدِ فنی (پیش از ۱ و ۲): سطرِ ارزشِ بازار درِ مرورگر هنوز «بی‌داده»
می‌گوید با این‌که `mcap` درِ پاسخِ `/api/market` هست — اول `Object.keys(rawRow)`
درِ همان صفحه چاپ شود تا معلوم گردد ردیف resolve نمی‌شود یا کلید درِ لایه‌ای
می‌سوزد (بندِ ۱ و ۲ به همین عدد وابسته‌اند).

milestone جدیدِ الحاقی (از همین‌جا درِ صف، بعد از بسته‌شدنِ این سه رأی):
«بازطراحی کامل وضعیت بازار» — دو page (نمایشِ لحظه‌ای / تحلیل)، chartهای
چهارصفحۀ FTS که درِ وضعیت بازار نبودند، motion به‌عنوان information
visualization (≤۲۵۰ms، latest-target-wins، reduced-motion)، و parity
اندازه‌گیری‌شدنِ TradersArena با matrix و طبقه‌بندیِ هر mismatch؛ در ساعاتِ
واقعیِ بازار. منشأ و قاعدۀ جدید اختراع نمی‌شود.


## 15.20 نشانگرِ زیرِ موس، و «در یک نگاه»ِ دوصفحه‌ای (۱۴۰۵-۰۷-۱۷)

دو رأیِ مالک درِ همین دور اجرا شد: «مربعِ کوچک یا ستاره فقط اگر موس رویِ همان
ردیف رفت نشان داده بشه» و «بازچینیِ کاملِ «در یک نظرة» همین milestone».

**نشانگرها.** `SymbolSelectBox` و `WatchlistStar` از `opacity-0` شروع می‌شوند و با
`group-hover`ِ خودِ ردیف، یا `focus-visible`ِ کیبورد، ظاهر می‌شوند. دو حالت
عمداً همیشه‌دیده‌اند: ستارۀ نمادی که عضوِ واچ‌لیست است (پنهانش یعنی اطلاعاتِ
دیدنی حذف شده) و دستگاهِ لمسی (`@media(hover:none)` — اندروید موس ندارد).
`motion-reduce:transition-none` بی‌حرکتیِ خواستۀ کاربر را محترم می‌شمارد.
سنجش از بیرونِ DOM با `getComputedStyle(...).opacity` است، نه با خواندنِ کلاس:
`_audit/ws7e_hover_reveal.mts` → ۱۷/۱۷ (idle ۰، hover ردیف ۱، دور شدنِ موس ۰،
hoverِ ردیفِ دیگر ردیفِ اول را پنهان می‌دارد، کیبورد ۱، لمسی ۱).
`_audit/ws7f_hover_persistence.mts` ثابت می‌کند reveal با هر pollِ تابلو و با
همان گرهٔ DOM (۶ ثانیه بی‌حرکتیِ موس) می‌ماند؛ پس hoverِ خالصِ CSS رویِ
تابلویِ زنده شکننده نیست.

**دو صفحۀ بازرسی نماد.** `SymbolInspector` حالا دو صفحۀ *محلی* دارد:
«در یک نگاه» و «جزئیات بازار». ترتیبِ صفحۀ اول دقیقاً رأیِ مالک است —
قیمت ← تغییر ← حجم/تعداد/ارزشِ معاملات ← ارزشِ بازار/I4 ← قدرت خرید/فروش ←
وضعیت تابلو ← تکنیکال ← بنیادی ← غربالگری FTS ← رویدادها ← جمع‌بندی — و همین
ترتیب درِ `symbol-inspector.spec.tsx` با یک تستِ ترتیب قفل شده است.
«قدرت خرید/فروش» سلولِ دومِ خودش را نمی‌سازد: `BuySellCell` (سرانه‌ها + نوارِ
سهم + نسبت) از درونِ `TapeTable` بی‌کم‌وکاست به
`features/market/components/BuySellCell.tsx` منتقل شد و تابلو و سایدبار هر دو
از همان یک implementation می‌خوانند؛ `toBillionRial` و `billionRialText` هم به
`shared/lib/fmt` رفتند تا واحدِ «ارزشِ معاملات» دو جا دو جور نوشته نشود.
چراغِ «سرانۀ خریدار» حذف نشد بلکه درِ همان سلول حل شد (نسبت و دو سرانه آن‌جاست).
«رویدادها» عنوانِ خودِ اطلاعیه را از `/api/calendar/<symbol>` می‌خواند؛ برچسبِ
جدایی اختراع نشد.
صفحۀ دوم (پنج مظنه، جریان حجم، چراغِ سبد، ممیزی بنیادی، دسترسی‌ها) تا باز نشده
mount نمی‌شود تا پرسشِ عمقِ بازار بی‌مصرف نرود، و بعد از باز شدن سرِ جایش
می‌ماند تا حالتِ بازشو گم نشود.

**سنجشِ زنده** (`_audit/ws8_inspector_pages.mts`، Chromium، بک‌اندِ همین worktree
رویِ ۸۰۰۱ و vite رویِ ۵۱۷۵): ۱۱/۱۱ PASS. ترتیبِ دیدنی همان رأی؛ جابه‌جاییِ
صفحّه هیچ درخواستِ غیرِ pollingی نمی‌سازد؛ پنج مظنه بسته به‌پیش‌فرض درِ DOM نیست
و با باز شدن، `/api/order-book/<sym>` را می‌پرسد و ۱۰ سطر (۵+۵) می‌نشیند؛
برگشت و آمدنِ دوباره بی‌درخواست است و پنل باز می‌ماند. ارتفاعِ «در یک نگاه»
۴۷۰px و «جزئیات بازار» ۴۷۷px درِ پنلِ ۲۴۰ پیکسلی. روبشِ سرریز هیچ عددِ بریده‌ای
درِ صفحۀ اول نگذاشت (نسخۀ اولِ خانۀ «قدرت خرید/فروش» ۱۰۸ پیکسل درِ ۷۴ پیکسل
می‌شکست — با عددِ همان سنجش اصلاح شد).

**آنچه راستی‌آزمایی نشد:** درِ حالتِ توسعه اپ داخل `<StrictMode>` است و هر mount
اول را دو بار اجرا می‌کند؛ timeline همین را نشان می‌دهد (دو درخواستِ یکسان درِ
یک میلی‌ثانیه). شمارۀ «یک درخواست» درِ بیلدِ بسته باید دوباره گرفته شود.
رفتارِ دو صفحّه رویِ اندروید (عرضِ کوچک‌تر، نبودِ hover) درِ همین دور با
مرورگرِ لمسیِ Chrome سنجیده نشد — فقط `hover:none` شبیه‌سازی شد.
گیتِ pilot برایِ این رأی‌ها درخواست نشد چون مالک خودِ ترتیب را رأی داده بود.
