# HarmonyOS DevEco Previewer and HDC Setup

## Supported Runtime

On macOS and Windows, Mobile Use uses DevEco Studio's bundled Hvigor,
Node.js, OpenHarmony SDK, HMS Previewer runtime, Previewer, HDC, and
target-provided ArkUI UITest. The Canvas keeps Previewer and every HDC
connection as separate selectable targets. On Linux, where DevEco Previewer is
not published as a host runtime, Mobile Use falls back to an explicitly
connected HDC target in attach-only mode: it does not build, install, or launch
the project automatically.

## Install

1. Download and install the full DevEco Studio package from the official
   [DevEco Studio resources](https://developer.huawei.com/consumer/cn/deveco-studio/resources/).
2. Complete first-run SDK setup in DevEco Studio. Ensure the default
   OpenHarmony SDK and Previewer components are present.
3. Open the HarmonyOS project in DevEco Studio and render a phone preview once.
   This can generate `.idea/previewer/phone/phoneSettingConfig_rd.json` when the
   installed DevEco package does not provide a fallback phone configuration.
4. Start or connect the intended HarmonyOS target in DevEco Studio, then confirm
   `hdc list targets` returns its exact ID. Target discovery never selects the
   first device implicitly.

The DevEco overview documents its Previewer and Hvigor capabilities:
[DevEco Studio](https://developer.huawei.com/consumer/cn/deveco-studio).
Do not run PreviewBuild or alter a user's project merely to create setup
evidence without consent.

## Configure Mobile Use

The qualified macOS default is
`DEVECO_STUDIO_HOME=/Applications/DevEco-Studio.app/Contents`.

The Windows fallback is `%ProgramFiles%\Huawei\DevEco Studio`. Set
`DEVECO_STUDIO_HOME` when DevEco is installed elsewhere. Windows uses
`hvigorw.bat` through `ComSpec`, `Previewer.exe`, and named pipes rather than
Unix-domain socket paths.

For Previewer mode, the viewer expects:

- `tools/hvigor/bin/hvigorw` (`hvigorw.bat` on Windows);
- `tools/node`;
- `sdk/default/openharmony/previewer/common/bin/Previewer`;
- `sdk/default/HarmonyOS/toolchains/hdc` (the qualified legacy
  `sdk/default/openharmony/toolchains/hdc` path is also discovered);
- `sdk/default/hms/previewer`;
- an OpenHarmony SDK under `sdk/default/openharmony`;
- a phone configuration from the project or a known DevEco plugin path.

Override the phone configuration only when necessary with
`CANVAS_HARMONY_DEVICE_CONFIG=<absolute-path-to-phone-config.json>`.
For a non-standard toolchain layout, use
`CANVAS_HARMONY_HDC_BIN=<absolute-path-to-hdc>` and, when known,
`CANVAS_HARMONY_RUNTIME_KIND=emulator|physical|remote`. Apply these values to
the intended IDE process rather than assuming a shell profile is inherited.

The viewer also accepts `DEVICE_HARMONY_DEVICE_CONFIG`. Do not commit the
absolute local path.

On Linux, put `hdc` on `PATH`, set `HDC_SDK_PATH`, or set
`CANVAS_HARMONY_HDC_BIN` explicitly. The environment checker reports READY
only when `hdc version` succeeds and `hdc list targets` returns at least one
target; missing DevEco/Previewer files are warnings in this fallback mode.

## Verify Without Starting Previewer

```bash
node "/absolute/loaded-setup-mobile-use-skill/scripts/check-mobile-environment.mjs" \
  --platform harmony \
  --project /absolute/path/to/project \
  --strict
```

Common fixes:

- **Hvigor or Node is missing:** repair the full DevEco installation instead
  of installing unrelated global copies.
- **Previewer binary/runtime is missing:** install the matching SDK and
  Previewer components from DevEco Studio.
- **Phone configuration is missing:** preview the project once in DevEco or set
  `CANVAS_HARMONY_DEVICE_CONFIG` to a valid local configuration.
- **PreviewBuild later fails:** treat it as project/toolchain evidence. Inspect
  the selected module, variant, route, and DevEco logs before editing source.
- **HDC exists but no target appears:** start/connect it in DevEco, run the
  checker again, and inspect `hdc list targets`. Do not substitute a guessed ID.
- **Linux reports attach-only:** build/install/launch the HAP outside Mobile
  Use, then connect the exact target with HDC before opening the Canvas.
- **Target lacks UI operations:** verify `uitest --version` and `uitest uiInput
  help` on that exact target. The adapter advertises only probed capabilities.
