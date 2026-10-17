# Change: complete local-first Android FTS

## Scope

Continue from the Codal SQLite sidecar and isolated growth calculator. First make
the stored monthly and financial series obey the same issuer, period, evidence,
and ordering rules as `fts_engine.py`. Then add the remaining FTS indicators and
connect local evaluations to the Android screener and strategy routes in small,
parity-tested steps. Add incremental, throttled Codal synchronization with
explicit freshness and per-symbol `UNKNOWN` / `NOT_EVALUATED` states. Preserve
the existing snapshot as a labeled offline fallback until the local routes can
replace it safely. No central service is required.

The final Android release must be built from the reviewed branch, signed with the
existing release keystore, pass the workflow's APK checks, and include its
WebView-on-emulator result. A missing emulator run, missing live data, or
incomplete FTS input remains `NOT_VERIFIED`; it is not converted into a pass.

## Invariants touched

- Keep the existing `sql.js` + Cache API database; schema changes are additive,
  transactional, integrity-checked, and retain raw Codal HTML and provenance.
- Preserve the desktop `fts_engine.py` calculations and report-selection rules;
  use parity fixtures before connecting each result to a public Android route.
- Do not treat missing, stale, consolidated-only, or identity-ambiguous data as a
  live result. Preserve the corresponding unknown or not-applicable state.
- Keep TSETMC and Codal requests direct from the Android client through the
  existing Capacitor HTTP adapter. Do not add a VPS, mandatory API, or a parallel
  database technology.
- Do not remove the shipped mobile snapshot. Its source and build time must remain
  visible wherever it is used as fallback.
- Do not modify the dirty desktop checkout or publish until tests and the signed
  Android release workflow are verified.

## Lockstep updates (spec / ESLint / guards)

- No new Python backend module, PyInstaller import, npm dependency, or Tauri
  packaging change is planned. New TypeScript stays in the existing local API
  layer and must satisfy its ESLint boundaries.
- Android `versionName` and derived `versionCode` continue to come from
  `frontend/package.json`; update `package-lock.json` in the same version bump.
- Update the Android release notes and any snapshot/manifest schema only if the
  implementation actually changes that contract. Keep the desktop release
  anchors untouched.

## Guard that proves the change is safe

- Targeted Vitest for migrations, Codal parsing/storage, FTS axis parity, local
  resolver routes, freshness states, and funnel status mapping.
- Desktop parity checks using this repository's `fts_engine.py` and `api/funnel.py`
  as reference implementations for identical input rows.
- `npx tsc -b --pretty false`, targeted and full frontend lint, relevant mobile
  integrity guards, and the complete Vitest suite.
- `mobile-apk` workflow build, `apksigner`/metadata checks, release-signature
  gate, Android WebView emulator evidence, and anonymous download/hash verification
  after publication.

## Rollback

Keep changes additive. A local route can be disabled and the existing snapshot
route retained while the sidecar schema and raw reports remain readable. Do not
delete or overwrite existing snapshots. If release verification fails, do not
publish the tag; correct or revert only the isolated Android commits, then rerun
the full release workflow.
