---
name: mobile-use
description: "Use when an Agent must operate or verify an Android, HarmonyOS, or iOS app through a live Qoder Canvas device surface. Excludes machine-wide setup and source-only editing."
---

# Mobile Use

Operate the host-owned Canvas device surface through this Skill's CLI. The
plugin contributes no MCP server, editor-opening tool, or second runtime.

## Route only the needed detail

- Invocation, command contracts, plans, and iOS build synchronization:
  [CLI](references/cli.md).
- Discovery/capability/runtime mismatch: [Debugging](references/debugging.md).
- Screenshot/recording claim: [Visual evidence](references/visual-evidence.md).
- Native test/E2E/repair claim:
  [Installed-app verification](references/installed-app-verification.md).
- Platform detail: [Android](references/android.md),
  [HarmonyOS](references/harmonyos.md), or [iOS](references/ios.md).
- Ownership or receipt integrity: [Tools](references/tools.md).
- Missing toolchain or machine-wide target: use `$setup-mobile-use`.
- Missing `node` executable: resolve a validated runtime with
  [Node runtime discovery](../setup-mobile-use/references/node-runtime-discovery.md)
  before invoking the Skill-local launcher.

## Establish a live surface

When no surface exists, open its canonical Canvas entry:

- Android: application-module `src/main/AndroidManifest.xml`
- HarmonyOS: application-root `build-profile.json5`
- iOS application: `<App>.xcodeproj/project.pbxproj`
- SwiftUI Package Preview: importable package `Package.swift`

Reading the entry is insufficient. Use a host Canvas-open action or report that
boundary; do not replace it with a platform shell or a machine-wide inference.

## Use the Agent contract

1. Invoke the sibling launcher with a validated Node.js 20+ runtime and its
   absolute loaded-Skill path. Qoder Electron-as-Node is acceptable when
   validated as described above. Do not use an exported variable,
   `QODER_PLUGIN_ROOT`, guessed cache, or workspace cwd.
2. Start with `inventory` (`live_canvas_surfaces`). Use `doctor` when discovery
   is empty or inconsistent; use `describe <command>` only when needed.
3. Bind one unique surface/target/session. Follow structured `recovery`; never
   select the first ambiguous match or repeat an unchanged retry.
4. Prefer selector-first `tap`/`long-press` for one action and `run-plan` for a
   workflow. Reserve revision-bound actions for explicit refs or coordinates.
5. Require advertised capabilities. Never bypass them with raw ADB, simctl,
   HDC, UITest, or native-runner commands.
6. Stop only sessions started by this workflow unless requested otherwise.

For iOS edits, establish a terminal `project-build-status` cycle, edit, then
`wait-project-build` after that cycle. On success, discard prior refs,
coordinates, and `uiRevision` and observe again. If the capability is absent,
report the boundary; do not consume events or sleep blindly. See [CLI](references/cli.md).

Native nodes are not DOM. Prefer stable native identifiers, then unique labels.
Refs, coordinates, paths, and `uiRevision` are snapshot-scoped.

## Match evidence to the claim

- **Build:** selected project/target compiled.
- **Interactive:** live surface completed the semantic workflow.
- **Native test:** exact selector returned `data.output.outcome == "passed"`.
- **Captured:** receipt has artifact provenance; this is not visual inspection.
- **Visually inspected:** a media-capable consumer opened the artifact.
- **Repair:** the same frozen contract failed before and passed after.

Starting a target needs authorization unless run/test/E2E was requested.
Uninstall needs explicit confirmation. Keep credentials private, preserve
artifact URI/digest metadata, and name unverified layers.
