# HarmonyOS HDC Runtime

Read this reference when using, implementing, or reviewing the broker-backed
HDC target. The viewer keeps HDC and DevEco Previewer as separate targets. The
current adapter qualifies application lifecycle and UITest operations per
target; logs remain unimplemented. For source provenance, see
[Source and design notes](source-notes.md).

## Toolchain and target discovery

Resolve `hdc` from explicit plugin configuration first, then official DevEco
SDK layouts, then `PATH`:

- `<DevEco Studio>/sdk/default/HarmonyOS/toolchains`
- `<DevEco Studio>/Contents/sdk/default/HarmonyOS/toolchains` on macOS
- `<Command Line Tools>/sdk/default/HarmonyOS/toolchains`

Discovery argv:

```text
["list", "targets"]
```

Discard empty output and `[Empty]`. Every target-scoped operation must prepend
the exact selected target:

```text
["-t", targetId, ...operation]
```

Bind one broker session to one discovered target ID. Never silently choose the
first device when multiple targets are present. Product probes such as
`param get const.product.name` or `const.build.characteristics` may enrich
metadata, but their strings are not a stable emulator/physical classifier.

Use HDC error codes for automation. The official guide warns that
human-readable error messages can change and must not drive program logic.

## Lifecycle argv seams

The following suffixes come after `["-t", targetId, ...]`; they are adapter
implementation seams, not Skill commands:

| Operation | Adapter argv suffix |
| --- | --- |
| Install or replace HAP | `["install", "-r", hapPath]` |
| Inspect installed bundle | `["shell", "bm", "dump", "-n", bundleName]` |
| Launch Ability | `["shell", "aa", "start", "-b", bundleName, "-a", abilityName]` |
| Force-stop bundle | `["shell", "aa", "force-stop", bundleName]` |
| List application PIDs | `["jpid"]` |
| Track PIDs and bundle names | `["track-jpid", "-p"]` |
| Stream device logs | `["hilog", ...qualifiedHilogArgs]` (planned) |

Read the bundle and entry identity from project or official unpacking-tool
metadata. Use `bm dump -n` as an installed-bundle inspection surface, not an
excuse to default every app to `entry` and `EntryAbility`. Treat a launch as
successful only after process completion and a qualified result. Translate
official error codes to typed adapter errors; do not couple logic to English
success text.

The official log surface is `hdc hilog`. Query supported filters with
`hdc hilog -h`; do not assume the third-party `shell hilog -P` form exists on
every device. Own live logs as a cancellable session process, stop them with
the broker session, and bound all buffered output.

## Safety and capability gates

- Execute argv arrays; never concatenate a command string.
- Do not expose arbitrary `shell`, file transfer, port forwarding, or process
  termination to the Agent.
- Validate local package paths against the selected project and use unique
  remote paths for transferred artifacts.
- Keep Previewer and HDC as separate target surfaces.
- Advertise each HDC/UITest operation only after real target qualification against the
  installed HDC and HarmonyOS versions.
- An HDC adapter belongs in `packages/device-adapter-harmony`; the viewer and
  plugin CLI remain the distribution and capability boundary.
