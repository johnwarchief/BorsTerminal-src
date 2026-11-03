# Installed-app verification

Read this reference when the requested outcome is repair correctness,
fail-to-pass evidence, a native mobile test, benchmark execution, or a mobile
E2E claim. Ordinary Canvas preview and Phone Use work can stay on the shorter
workflow in `SKILL.md`.

## Freeze the execution contract

Before treating a result as native runtime evidence, identify and keep stable:

- repository revision or candidate patch identity;
- platform toolchain and SDK/API version;
- project-owned build tasks and app plus test artifact paths;
- package or bundle identifiers;
- exact device target, runtime kind, OS/API version, and architecture;
- one exact native test selector;
- runner command, timeouts, and expected outcome.

Discover these values from repository configuration and the selected live
target. Do not invent a generic runner command or silently switch devices,
schemes, variants, products, test methods, or timeouts between attempts.

The selector and behavioral evidence remain platform-native:

| Platform | Exact target | Required behavioral evidence |
| --- | --- | --- |
| Android | instrumentation `class#method` | instrumentation assertion and runner output |
| iOS | XCTest `Target/Class/testMethod` | XCTest assertion and Simulator/device log |
| HarmonyOS | repository-qualified ArkXTest or Hypium suite/test | runner assertion and device log |

Use the matching platform reference for project and target discovery. A
project-backed session advertises `device.test.run` only when its host owns a
qualified native runner. Invoke it through `run-native-test`; HarmonyOS
Previewer sessions intentionally do not advertise this capability. Absence of
the capability or the repository's test target is an unverified boundary, not
permission to substitute Phone Use `assert`.

The CLI binds the selector to the selected session and returns a semantic
`data.output.outcome`. Android builds and installs the app and androidTest APK
before instrumentation; iOS runs `xcodebuild test` with one `-only-testing`
selector and exact Simulator destination; HarmonyOS builds and installs the
`ohosTest` HAP before `aa test`. Platform-specific overrides must come from the
repository contract, never guessing.

## Keep the runtime path observable

Record the stages separately:

```text
build -> artifact validation -> target validation -> clean install/state
      -> launch -> exact target test -> assertion/result -> evidence cleanup
```

Bind every platform command to the selected target. Revalidate target identity
before execution, use fresh app and test artifacts, and clear stale package or
application state when the project contract permits it. Do not stop, erase, or
reset a remote or user-owned device merely because a verifier owns the test
attempt.

Preserve the raw stage and primary cause instead of collapsing all non-zero
exits into a test failure:

- `passed`: the exact target test executed and passed;
- `assertion_failed`: it executed and reached the behavior assertion;
- `build_failed` or `artifact_missing`;
- `install_failed` or `launch_failed`;
- `crashed_before_assertion` or `runner_mismatch`;
- `target_offline`, `timeout`, or external toolchain failure.

For a candidate patch, a patch-caused build regression is a candidate failure;
an unavailable SDK or offline target is infrastructure failure. Preserve enough
evidence to make that distinction rather than inferring it from an exit code.
A skipped test, empty selection, or runner that never reaches the selected
method is never a pass.

## Verify a repair with two states

Use this stricter contract only when repair-grade or benchmark evidence is
required:

1. Hold the test-only patch and production fix separately. A test must not call
   a fix-only hook or identifier.
2. In the defective state, require build, install, launch, exact-test execution,
   and an assertion failure attributable to the reported behavior.
3. In the repaired state, use the same target, test, and execution plan and
   require the test to execute and pass.
4. Run applicable regression tests separately; one target test does not prove
   global correctness.

The outer evaluator or Harness owns isolated worktrees, repository and device
locks, patch application, and cleanup. Never reset a dirty user worktree to
construct the two states. Give every attempt a new artifact directory; retries
rerun the exact candidate patch rather than granting a new repair sample.

## Preserve auditable evidence

Keep a versioned attempt record containing stage receipts, exact target and
toolchain provenance, app/test artifact digests, selected test identity, runner
output, bounded device logs, timestamps, timeouts, and final classification.
Keep screenshots or recordings when they materially explain the behavior, but
do not use them as substitutes for native runner evidence.

Preserve broker-owned artifact URI, digest, media type, size, source, and
revision. Device and runner logs can contain paths, identifiers, typed text, or
credentials; screen or redact them before exposing evidence outside the local
verification boundary.

`run-native-test` exiting `0` means the operation completed and its evidence
was persisted. It does not mean the assertion passed. Require
`data.output.outcome == "passed"`; keep `assertion_failed`, `runner_mismatch`,
and infrastructure outcomes as distinct results.

Report the strongest completed layer precisely: build verified, interactive
runtime verified, native target test verified, or two-state repair verified.

## Design basis

The two-state contract follows
[AppEval](https://arxiv.org/abs/2608.18588). Its v1 quantitative evidence is
Android-only; do not treat its synthetic iOS or HarmonyOS placeholders as
cross-platform validation.
