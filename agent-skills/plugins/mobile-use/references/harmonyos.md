# HarmonyOS

The HarmonyOS Canvas reads the application descriptors and publishes the
targets supported by the current host. On macOS and Windows it publishes
DevEco Previewer plus connected HDC targets and builds only after a session is
selected. Previewer builds its page artifact; an HDC project session can build
the selected HAP, install it, and launch its descriptor-derived bundle and
Ability. Linux publishes explicitly connected HDC targets in attach-only mode:
Mobile Use does not build, install, or launch the HarmonyOS project there.

Defaults:

- module: selected from `build-profile.json5` `modules[].srcPath`
- product / target / build mode: descriptor values, with explicit overrides
- variant: `default`
- route: selected ArkTS page, first `main_pages.json` entry, or `pages/Index`
- semantic tree: DevEco Previewer Inspector

Useful overrides are `DEVECO_STUDIO_HOME`, `CANVAS_HARMONY_MODULE`,
`CANVAS_HARMONY_PRODUCT`, `CANVAS_HARMONY_TARGET`,
`CANVAS_HARMONY_BUILD_MODE`, `CANVAS_HARMONY_VARIANT`, `CANVAS_HARMONY_ROUTE`,
`CANVAS_HARMONY_DEVICE_CONFIG`, and the documented display/language options.

Both transports use the same Mobile Use CLI and session contract:

| Capability | Previewer | HDC target |
| --- | --- | --- |
| Frames | JPEG stream across current protocol versions; raw RGBA compatible | UITest PNG polling, up to 2 fps |
| Semantic tree | DevEco Inspector | UITest `dumpLayout` |
| Pointer input | Previewer command pipe | UITest `uiInput` |
| Keyboard input | unavailable | advertised only when probed |
| App build/install/launch | not applicable | Hvigor HAP + HDC/BM/AA on macOS/Windows; attach-only on Linux |
| Recording/logs | unavailable | not advertised yet |

HDC runtime kind is not guessed from product strings. Set
`CANVAS_HARMONY_RUNTIME_KIND=emulator|physical|remote` when classification is
known; otherwise it is `remote`.

## Diagnosis and qualification

- Keep Previewer and HDC results separate. Previewer supplies interactive
  evidence and intentionally does not advertise `device.test.run`; native
  ArkXTest evidence requires a qualified HDC project session.
- On Linux, require an already installed/running app on the exact connected HDC
  target. Do not claim that Mobile Use performed project build, install, launch,
  or native test selection for an attach-only session.
- Implementation, advertised capability, and release qualification are
  different states. Claim an HDC operation only when the selected target
  advertises it, and claim platform support only after installed E2E against a
  live HDC target.
- Diagnose Previewer frame formats from the payload, not the protocol version.
  JPEG begins with `FF D8`; raw RGBA must match the exact width × height × 4
  byte count. Log only a bounded magic prefix and expected size when these
  disagree.
- A valid HAP build does not prove HDC install, launch, UITest semantics, input,
  or ArkXTest. Preserve each stage and its capability receipt separately.

## Read the matching subsystem

Load only the reference needed for the current task:

- Project discovery, JSON5 descriptors, modules, bundle or Ability identity:
  [Project model](harmonyos/project-model.md)
- Previewer or installable-package builds, product/target selection, and
  artifact qualification: [Hvigor builds](harmonyos/hvigor.md)
- Device discovery, install/launch, lifecycle, or future HiLog support:
  [HDC runtime](harmonyos/hdc.md)
- Layout snapshots, input injection, or device screenshots:
  [arkXtest and UITest](harmonyos/arkxtest.md)
- Official provenance, external-project findings, and rejected patterns:
  [Source and design notes](harmonyos/source-notes.md)

The subsystem references are for implementation and review. Normal agent
automation must continue to use the plugin CLI and its advertised capabilities
rather than invoking HDC, UITest, or Hvigor directly.
