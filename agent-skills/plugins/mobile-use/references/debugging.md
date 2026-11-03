# Mobile Use debugging

Read this reference when project source, the installed plugin, a live Canvas
surface, semantic interaction, and native-test evidence disagree. For a missing
SDK or machine-wide target scan, use `$setup-mobile-use`. For repair-grade
or exact native-test evidence, also read
[Installed-app verification](installed-app-verification.md).

## Locate the failing layer

Do not jump from a visible symptom to a platform command. Identify the first
layer whose evidence is missing:

| Layer | Minimum evidence | Important boundary |
| --- | --- | --- |
| Project | One canonical entry resolves the intended project | Opening a file does not boot a target |
| Live Canvas discovery | `list-targets` publishes the exact surface and target | Discovery covers live Canvas surfaces, not every device installed on the machine |
| Session | One exact `surfaceId` and `targetId` resolve to one `sessionId` | Never select the first result when discovery is ambiguous |
| Capability | The selected target/session advertises the requested operation | Missing capability is an unsupported boundary, not permission to fall back |
| Project build | `project-build-status` establishes a cycle and `wait-project-build` returns a newer terminal cycle | A timer or event-stream consumer is not build synchronization |
| Semantic UI | `observe`, revision-bound `act`, `wait`, or `assert` succeeds against the current snapshot | Native accessibility nodes are not DOM nodes |
| Native behavior | `run-native-test` returns `data.output.outcome == "passed"` | A completed operation or Phone Use assertion is not a native-test pass |
| Installed host | The installed Skill/CLI and provisioned viewers match the intended plugin build | Source and package tests cannot prove the enabled-host path |

Use [CLI](cli.md) for command schemas. Read the matching
[Android](android.md), [HarmonyOS](harmonyos.md), or [iOS](ios.md) reference only
after the failing platform is known.

## Triage loop

1. Refresh `inventory`; use `doctor` when it is empty or inconsistent.
2. Pin exact surface, target, and session identifiers from the same live Canvas.
3. Follow `error.recovery.kind` and advertised capabilities. Use `describe` when
   the command input is uncertain; do not retry an unchanged failure.
4. Re-observe after UI change and keep refs, coordinates, text, keys, and swipe
   bound to that observation.
5. Separate launch, bounded readiness, assertion/native outcome, evidence, and
   cleanup instead of collapsing them into one pass/fail result.

## Symptom routing

| Symptom or error | Interpretation and next action |
| --- | --- |
| A project entry is known but no matching Canvas surface exists | Reading the file is not the same as opening its Format Viewer. Use a supported host Canvas-open action when available; otherwise report the host-open boundary and provide the canonical entry. Do not substitute a platform shell command. |
| Source changed but the session omits `device.project.live-build.status` or `.wait` | Runtime synchronization is unavailable. Preserve the source change, stop before runtime claims, and do not consume Surface events, sleep blindly, or edit Previewer caches/generated output. |
| `phone.project-build.failed` | Repair the bounded source/build error, read the current cycle again, and wait only after another discriminating source change. Do not reuse pre-relaunch UI refs. |
| `device.project.live-build.wait-timeout` | Keep the last cycle/status as evidence, inspect the live surface/build state, and change the readiness condition before retrying. A timeout is not a build failure or success. |
| Loaded Skill launcher is missing | The installed plugin is incomplete. Stop and report it; do not guess another cache path. |
| `list-targets` omits a platform | No live Canvas surface published it. This does not prove that its SDK or device is absent; use the setup Skill for a machine-wide probe. |
| Target or session selection is ambiguous | Supply exact IDs or refine selection until it is unique. Never silently choose the first target. |
| `phone.*broker*` or `doctor` reports a degraded/unavailable surface | Keep credentials private, preserve the reported broker error code, and restore or reopen the owning Canvas instead of starting another runtime. |
| `device.surface.*`, `device.target.*`, or `device.session.*` | Follow `refresh_inventory` and bind identifiers from the same surface. Do not copy broker records or credentials into commands. |
| `device.capability.unsupported` | Report the selected runtime and missing capability. Check the platform reference; do not route around the adapter with arbitrary shell commands. |
| `phone.selector.not-found` | Re-observe and verify the app is foreground and ready, then refine the selector. |
| `phone.selector.ambiguous` | Add a native identifier, role, type, or another semantic constraint. Do not choose a match by array position. |
| `phone.ui-revision.stale` or stale ref | Re-run `observe` and use only its revision and refs. |
| Launch succeeded but `wait` timed out | Preserve launch as a completed stage and UI readiness as a separate failure; capture bounded logs or a screenshot when advertised. |
| Operation receipt succeeded but native test did not pass | Inspect `data.output.outcome`; keep assertion, build, install, runner, target, crash, and timeout outcomes distinct. |
| Source/build/package checks pass but Canvas still fails | Verify the installed artifact and provisioned viewer closure, then reproduce in the real enabled Canvas host. Do not repair the symptom with generated output. |
| Frames are blank, stale, or decoded with an implausible size | Distinguish screenshot from stream capabilities and inspect the platform transport. For Previewer JPEG/RGBA diagnosis, use the HarmonyOS reference. |

Retry only after changing the discriminating condition: a newly published
surface, supported rebuild/refresh, fresh observation, unique selector, exact
live identifier, restored capability, completed app readiness condition, or
corrected installed artifact. Repeating an unchanged command is not additional
evidence.

Report only the strongest evidence layer defined in `SKILL.md` and name every
unverified platform. Infrastructure outcomes such as
missing toolchains, offline targets, build/install/launch failures, crashes,
and timeouts must not be reported as behavioral pass or failure.
