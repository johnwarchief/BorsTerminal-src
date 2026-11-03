# Tools and boundaries

Read this reference when deciding which executable or host capability should
perform mobile runtime work. Mobile Use has one Agent-facing command
surface; platform tools remain behind the Canvas host unless the user asks for
a separate platform-native workflow.

## Choose the owning tool

| Need | Use | Boundary |
| --- | --- | --- |
| Discover or automate a live Canvas device | Skill-local `mobile-use.mjs` launcher | Inventory covers `live_canvas_surfaces`, not every toolchain or device on the machine |
| Diagnose missing SDKs, runtimes, or machine-wide targets | `$setup-mobile-use` and its environment probe | Diagnose only; do not provision or mutate the machine without a separate request |
| Build, install, launch, capture, or test through a published target | Mobile Use CLI and the target's advertised capability | The Canvas host owns Gradle/ADB, Xcode/simctl, or Hvigor/HDC execution |
| Verify a returned local artifact's bytes | Skill-local `verify-artifact-receipt.mjs` | Integrity only; it does not inspect pixels, video, behavior, or native-test outcome |
| Inspect screenshot pixels | An image-capable local file tool on the artifact's host | Opening a URI in a text reader or receiving a digest is not visual inspection |

Do not route around a missing Canvas capability by calling ADB, simctl, HDC,
UITest, or a native runner directly. A platform-native command may be
appropriate for source development or a separately requested diagnostic, but
its result is outside the Mobile Use CLI evidence contract.

## Host-owned platform tools

The plugin may cause the host to use these tools after a live target and
capability have been selected:

- Android: the project Gradle Wrapper, Android SDK/Emulator tools, ADB-side app
  lifecycle, UIAutomator semantics, and instrumentation.
- HarmonyOS: DevEco Previewer or HDC, Hvigor, BM/AA, UITest, and ArkXTest/Hypium
  where the selected HDC project session has qualified them.
- iOS: `xcodebuild`, `xcrun simctl`, XCTest, generated Swift Package Preview
  host/reload projects, and pinned
  `serve-sim@0.1.46` prepared through `npx` on supported arm64 macOS hosts.

These are implementation dependencies, not additional Agent-facing commands.
Use the matching platform reference for their qualification rules. Do not infer
that a tool is installed, enabled, or working from source references alone.

## Interaction runtime boundary

`serve-sim` is an internal iOS Adapter dependency, not an Agent-facing command
surface. The viewer starts one attached, pinned process for its selected
Simulator, adapts its H.264/HID/AX endpoints to the Canvas protocol, and stops
only that owned process when the Canvas closes. Do not start another mirror,
parallel MCP server, or manual `serve-sim` daemon for Mobile Use work.

XcodeBuildMCP remains external. If the user separately requests an external
iOS browser mirror or an Xcode-specific debugging workflow, treat it as a
distinct integration with its own lifecycle and proof. Do not report that
result as Mobile Use package, installed-host, or cross-platform evidence.

## Verify a local artifact receipt

Save the exact CLI JSON envelope outside the repository or in a user-chosen
evidence directory, then invoke the verifier by its loaded Skill path:

```bash
node "/absolute/loaded-skill/scripts/verify-artifact-receipt.mjs" \
  "/absolute/path/to/mobile-use-receipt.json"
```

The verifier finds SHA-256 artifact descriptors in direct command or
`run-plan` results, deduplicates repeated descriptors, resolves local `file:`
URIs, and recomputes file size and digest. It returns one JSON result and uses
these exit classes:

- `0`: every discovered artifact is a local file and matches the receipt;
- `2`: invalid arguments, unreadable JSON, or no artifact;
- `3`: a file is missing or the URI is not a local `file:` URI;
- `4`: the actual size or SHA-256 digest differs from the receipt.

Use only the exact receipt returned by the active workflow. The helper does not
copy, upload, open, decode, or retain the artifact. A verified result supports
the claim **local bytes match the receipt**, not **visually inspected** or
**behavior passed**. It may verify failure screenshots from an unsuccessful
`run-plan`; `commandOk: false` remains separate from the artifact integrity
result.
