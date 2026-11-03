# Mobile Use CLI

Read this reference when selecting an Agent workflow. Query the CLI itself for
the exact current command contract instead of memorizing flags from prose.

## Invoke the loaded launcher

Derive `scripts/mobile-use.mjs` from the directory containing the loaded
`SKILL.md`, then pass that absolute path directly to `node`:

```bash
node "/absolute/loaded-skill/scripts/mobile-use.mjs" inventory --json
```

Do not export a launcher variable, use `QODER_PLUGIN_ROOT`, guess a plugin cache,
search for another copy, or depend on the workspace cwd. A missing sibling
launcher means the installed plugin is incomplete. PowerShell uses the same
direct `node "C:\absolute\...\mobile-use.mjs"` form.

## Discover only the needed contract

Use targeted introspection when an argument shape is not already known:

```bash
node "/absolute/loaded-skill/scripts/mobile-use.mjs" commands --json
node "/absolute/loaded-skill/scripts/mobile-use.mjs" describe run-plan --json
```

`describe` returns required parameters, value and number constraints, required
capabilities, destructive confirmation, and the nested plan contract. Command
and option names are canonical kebab-case; underscore aliases remain accepted.
Unknown, duplicate, conflicting, or out-of-range parameters fail before broker
discovery.

Every success writes one versioned JSON envelope to stdout. Every failure writes
one to stderr. Inspect `error.code`, `retryable`, `recovery.kind`, and `details`;
do not route from message text alone. Recovery kinds are bounded instructions:

- `refresh_inventory`: refresh live surface/target/session identity.
- `reobserve`: take a fresh snapshot and replace old refs/revision.
- `refine_selector`: add a stable native semantic constraint.
- `wait_for_readiness`: change or satisfy the discriminating readiness state.
- `run_doctor`: inspect credential-free broker reachability.
- `fix_arguments`: correct the command from `describe`; do not retry unchanged.
- `fix_project`: repair the reported source/build failure before waiting again.
- `do_not_retry`: report the unsupported or terminal boundary.

Exit classes are `0` success, `2` invalid command/arguments, `3` stale or
missing surface/session/target, `4` revision/selector/assert/wait failure, `5`
unsupported capability, `6` broker failure, and `1` other failure.

## Choose the smallest workflow

1. Start with `inventory`. It describes only `live_canvas_surfaces`.
2. If discovery is empty or inconsistent, use `doctor`; do not infer that a
   machine-wide SDK or device is absent.
3. For one semantic action, use selector-first `tap` or `long-press`.
4. For a bounded multi-step workflow, use one `run-plan` invocation.
5. Use lifecycle plus `observe`/`act` only for explicit refs, coordinates,
   text, keys, or swipe.
6. Use operational commands only when the selected target/session advertises
   the capability returned by `describe` and discovery.

Selectors accept non-empty `ref`, `identifier`, `label`, `role`, and `type`
fields and must resolve uniquely. Prefer a stable native identifier, then a
uniquely resolved semantic label. Native accessibility nodes are not DOM nodes.

## Synchronize an iOS source edit

Do not consume the session event stream or use an arbitrary sleep to infer that
an iOS rebuild finished. The project session owns one monotonic build cycle:

```bash
node "/absolute/loaded-skill/scripts/mobile-use.mjs" project-build-status \
  --surface-id "SURFACE" --session-id "SESSION" --json

# After editing the source, use data.output.cycle from the status receipt.
node "/absolute/loaded-skill/scripts/mobile-use.mjs" wait-project-build \
  --surface-id "SURFACE" --session-id "SESSION" --after-cycle 12 \
  --timeout-ms 300000 --json
```

Before editing, the status must be terminal (`succeeded` or `failed`). If it is
`pending`, wait with `after-cycle: 0`; if cycle `N` is `running`, wait with
`after-cycle: N-1`. Use the terminal receipt's cycle as the edit baseline. This
prevents a cold initial build from being mistaken for the rebuild caused by the
edit.

`wait-project-build` succeeds only for a newer terminal cycle. A failed cycle
returns `recovery.kind: "fix_project"`; a timeout returns
`wait_for_readiness`. A successful Xcode application rebuild relaunches the app,
so take a fresh observation before any later selector/ref/coordinate action.
Swift Package Preview reloads keep the host process, but its UI snapshot is
still stale after the reload. These commands are capability-gated; a runtime
that does not advertise them cannot be treated as synchronized.

## Run one versioned plan

Ask `describe run-plan --json` for the current step catalog and constraints.
A plan requires either an exact `surfaceId`/`sessionId` pair or a platform
selector. `policy: "existing"` is the default; `reuse-or-start` may start one
uniquely matched target. A plan-started session is stopped unless
`keepSession: true` is explicit.

```bash
node "/absolute/loaded-skill/scripts/mobile-use.mjs" run-plan \
  --plan-json '{
    "schemaVersion":1,
    "session":{"platform":"ios","policy":"reuse-or-start"},
    "evidence":{"screenshots":"on-failure"},
    "steps":[
      {"kind":"tap","selector":{"identifier":"login.submit"}},
      {"kind":"wait","condition":{"kind":"present","selector":{"identifier":"home.ready"}},"timeoutMs":5000},
      {"kind":"assert","selector":{"identifier":"home.ready"}}
    ]
  }' --json
```

Step failures preserve `details.stepIndex` and `details.stepKind`. Failure
screenshots are best-effort and never mask the primary error. Native recording
is transactional: a plan that starts it stops it on success or failure before
session cleanup. Read [Visual evidence](visual-evidence.md) before making a
claim about captured media.

## Low-level and operational boundaries

`observe` returns the current `uiRevision` and refs. `act` binds its action to
that revision. Re-observe after any UI change; never silently replay a stale
action.

`assert` proves semantic UI state only. `run-native-test` proves a platform
runner result only when the session advertises `device.test.run` and
`data.output.outcome == "passed"`. Operation status `succeeded` alone is not a
native pass. Read [Installed-app verification](installed-app-verification.md)
for native E2E or repair claims.

Application uninstall requires explicit confirmation. Screenshot, recording,
and native-test receipts preserve bounded artifact metadata rather than media
bytes. Use [Tools and boundaries](tools.md#verify-a-local-artifact-receipt) when
local byte-integrity verification is material.

## Swift Package preview cache

The macOS-only `swift-cache-status`, `swift-cache-prune`, and
`swift-cache-clean` commands do not require a live surface. Prune is a dry run
unless `--apply` is explicit. Exact clean requires `--confirm` and refuses
active leases/build locks. Ask `describe <command> --json` for its current
bounds; never delete the broad Qoder or Canvas cache root.
