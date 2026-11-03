# HarmonyOS Source and Design Notes

Read this file when refreshing official syntax, evaluating another HarmonyOS
automation project, or deciding whether a feature belongs in the Canvas
adapter. Ordinary Previewer use does not need it.

## Evidence order

When sources disagree, use this order:

1. current Huawei HarmonyOS documentation;
2. current OpenHarmony documentation or owning component source;
3. installed-tool `version`, `help`, and real-device behavior;
4. this repository's accepted protocol and qualified runtime behavior;
5. third-party implementations.

Official sources were last reviewed on 2026-08-21. Third-party syntax is never
enough to advertise a capability.

## Official sources

| Subsystem | Primary source |
| --- | --- |
| HDC, target selection, install, transfer, HiLog | Huawei [HDC guide](https://developer.huawei.com/consumer/en/doc/harmonyos-guides/hdc) |
| Project products, modules, targets, `srcPath` | Huawei [build-profile.json5](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/ide-hvigor-build-profile) |
| Build mode and official HAP/APP argv | Huawei [Hvigor build modes](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/ide-hvigor-compilation-options-customizing-guide) |
| Task names and `PreviewBuild` | Huawei [Hvigor task reference](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/ide-hvigor-task-process) |
| Package verification | Huawei [HAP unpacking tool](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/unpacking-tool-0000001821000457) |
| Package modes and validation errors | Huawei [packing tool](https://developer.huawei.com/consumer/cn/doc/doccenter-capabilities/packing-tool) |
| UITest input, layout and screenshot shell grammar | OpenHarmony [arkXtest](https://gitee.com/openharmony/testfwk_arkxtest/blob/master/README_zh.md) |
| Ability and bundle tools | OpenHarmony [AA](https://gitee.com/openharmony/docs/blob/master/en/application-dev/tools/aa-tool.md) and [BM](https://gitee.com/openharmony/docs/blob/master/en/application-dev/tools/bm-tool.md) |

## External project audit

### agent-device

Useful documents and seams:

- `README.md`: capability discovery and the inspect-act-verify loop.
- `docs/adr/0010-error-system.md`: typed errors, hints, cause preservation,
  redaction, and machine-readable retry semantics.
- `docs/adr/0011-interaction-guarantee-contract.md`: a path-by-guarantee
  matrix so fast paths cannot silently skip safety rules.
- `docs/adr/0014-session-ref-frame-lifetime.md`: refs are authorization scoped
  to one published frame and expire at the first possible mutation.
- `docs/adr/0019-request-bound-platform-runtime.md`: bind platform resources to
  request/session lifetime and keep operation failure primary over cleanup
  diagnostics.
- `docs/agents/device-verification.md`: real-runtime proof expectations.
- `packages/platform-harmonyos/src/inventory.ts`, deployment/log runtimes, and
  `src/platforms/harmonyos/{input-actions,snapshot,screenshot}.ts`: practical
  HDC/UITest adapters with unique temporary paths and bounded captures.

Retain the capability, error, ref-lifetime, cleanup, and evidence ideas. Canvas
already owns their equivalents; do not port agent-device's CLI/MCP/session
implementation or add a second runtime.

### harmony-tools

`README.md`, `docs/DEVELOPER.md`, `src/harmony_tools/tools.py`, and
`build_helper.py` show a useful step-receipt shape for build, transfer, install,
cleanup, and launch. Retain per-step timing and structured outcomes.

Do not inherit its arbitrary shell tool, `openharmony/toolchains` assumption,
third-party Hvigor argument ordering, fixed output guesses, or newest-artifact
selection. Official HarmonyOS syntax and the deterministic artifact oracle in
[Hvigor builds](hvigor.md) take precedence.

### mcp-harmonyos

`README.md`, `plan.md`, `src/tools/projects.ts`, and `src/utils/hdc.ts` identify
useful project projections: modules, permissions, dependencies, signing
completeness, Abilities/pages, installed apps, and bounded logs. Its argv-array
`execFile` wrapper is the right process boundary pattern.

Do not inherit its simplified regex JSON5 parser, guessed top-level `outputs`
directory, default `EntryAbility`, output-string parsing, or split design where
the Agent falls back to raw Bash. The mobile-use CLI remains the only
Agent adapter.

`CONFIGURATION.md` and `QUICKSTART.md` are client-installation material and do
not change the Canvas adapter contract, so they are not copied into the Skill.

### HarmonyOS-mcp-server

`README.md`, `hdc/Component.py`, `window_manager.py`, and `app_manager.py` are a
small feature inventory for layout attributes, input, current-app inspection,
and screenshots. They demonstrate why a prototype still needs sessions,
capabilities, stable refs, cleanup, and evidence.

Do not inherit concatenated command strings, shared `tmp.json`, unscoped target
selection, first-module Ability selection, unawaited operations, success-string
classification, or working-directory artifacts.

### Appium HarmonyOS Driver

`README.md` is the broadest inventory of HarmonyOS selector, gesture,
application, device-state, file, log, recording, and WebView-context behavior.
`lib/commands/app-managerment.js` is useful when evaluating entry-Ability
selection; `viewport.js` shows layout-to-WebDriver projection; and
`context/context.js` identifies future WebView/port-forwarding requirements.

Use this project to assess traditional test and WebView compatibility, not as
the Canvas control contract. Do not expose Appium element IDs as Canvas refs,
fall back to the first HDC device, return screenshots/recordings as base64, or
adopt its generic shell endpoint. Orientation, multitouch, recording, and
WebView remain absent until independently qualified.

## Architecture notes retained from the workspace survey

The survey correctly prioritizes session, capability, snapshot/ref, evidence,
and build-run verification over a flat list of HDC commands. Its older proposal
for several MCP servers is superseded: the accepted Canvas design has one
`mobile-use` plugin, one host-owned runtime, and one plugin-local CLI as
the only Agent adapter.

Future candidates worth re-evaluating are:

- project permission/dependency/signing/Ability projections;
- WebView context discovery and authorized port forwarding;
- bounded DFX diagnostics such as process, memory, CPU, and crash evidence;
- replay/export only after Canvas operation and ref semantics remain intact.

Each candidate needs an official schema or command source, an explicit
capability, bounded/redacted output, real-runtime proof, and ownership by the
existing broker session.

## Public project links

- [agent-device](https://github.com/callstack/agent-device)
- [harmony-tools](https://github.com/99byte/harmony-tools)
- [mcp-harmonyos](https://github.com/FadingLight9291117/mcp-harmonyos)
- [HarmonyOS-mcp-server](https://github.com/XixianLiang/HarmonyOS-mcp-server)
- [Appium HarmonyOS Driver](https://github.com/zhihu/appium-harmonyos-driver)
