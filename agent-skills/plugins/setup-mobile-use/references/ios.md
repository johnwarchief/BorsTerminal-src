# iOS Simulator Setup

## Supported Runtime

Mobile Use uses full Xcode command-line tools to discover an available
iPhone Simulator, then builds with `xcodebuild` and controls it through
`simctl`. It runs only on macOS and does not target a physical iPhone.

## Install

1. Install the full Xcode application from Apple. Command Line Tools alone are
   insufficient.
2. Open Xcode once, accept its license, and allow first-launch components to
   finish installing.
3. In **Xcode > Settings > Components**, install an iOS Simulator runtime. See
   [Downloading and installing additional Xcode components](https://developer.apple.com/documentation/xcode/downloading-and-installing-additional-xcode-components).
4. In **Window > Devices and Simulators > Simulators**, create an iPhone when
   no available one exists. See [Adding additional simulators](https://developer.apple.com/documentation/safari-developer-tools/adding-additional-simulators).
5. Provide Node.js 20+ to run the Skill-local tools. When no standalone Node is
   installed, use the validated Qoder Electron-as-Node fallback from
   [Node runtime discovery](node-runtime-discovery.md). This fallback does not
   provide `npm` or `npx`.
6. For interactive iOS capabilities, provide a working `npx`. Mobile Use uses
   pinned `serve-sim@0.1.46`; preparing it needs registry access once, then
   reuses the npm cache. The adapter resolves `npx` from
   `CANVAS_SERVE_SIM_NPX`, the inherited `PATH`, or the user's login shell.

If multiple Xcode installations exist, inspect the current selection first:

```bash
xcode-select -p
```

Changing it is a system mutation. Ask before running commands such as:

```bash
sudo xcode-select -s /Applications/Xcode.app/Contents/Developer
sudo xcodebuild -runFirstLaunch
```

## Verify Without Booting

```bash
node "/absolute/loaded-setup-mobile-use-skill/scripts/check-mobile-environment.mjs" --platform ios --strict
```

The checker distinguishes a full Xcode installation from the active developer
directory, locates `simctl`, and reports installed iOS runtimes separately from
created iPhone Simulators. It verifies Node.js and `npx`; `npm` is a diagnostic
warning because the adapter invokes `npx` directly. These checks do not boot a
Simulator or download `serve-sim`.

## Prepare the Interaction Runtime

After the user approves npm registry access and a write to the npm cache, run:

```bash
node "/absolute/loaded-setup-mobile-use-skill/scripts/check-mobile-environment.mjs" \
  --platform ios \
  --strict \
  --prepare-ios-interaction-runtime
```

Preparation invokes `npx --yes serve-sim@0.1.46 --version`. It succeeds only
when the exact pinned version is returned. It does not globally install the
package, start a `serve-sim` daemon, boot a Simulator, or copy a Helper app.

The JSON report includes `nodePath`, `nodeSource`, `npmPath`, `npxPath`,
`npxSource`, `iosRuntimes`, and `recommendedIdeEnvironment`. The legacy
`interactionRuntimePrepared` field and `interactionRuntimeVerifiedThisRun`
both describe verification performed by this invocation; `false` does not
prove that no cache exists. `recommendedIdeEnvironment` is advisory and is not
proof that Qoder inherited those values. The actual adapter uses the same
explicit/PATH/login-shell `npx` order as the checker.

The plugin intentionally contains no prebuilt Helper app and does not generate
a macOS helper executable. The Canvas Node host owns its pinned `serve-sim`
process and stops it with the Canvas. Mobile Use ships only the Swift source
templates and project generator for the iOS SwiftUI preview host and reload
dylib; the disposable project and all build products are created in the user's
writable Qoder cache by that Mac's Xcode. The interaction path is qualified
for Apple silicon (`arm64`); an Intel Mac is not considered ready.

Common fixes:

- **Developer directory points to CommandLineTools:** install full Xcode and,
  with permission, select its `Contents/Developer` directory.
- **No iOS runtime:** install one in Xcode Settings > Components.
- **No available iPhone:** create one in Devices and Simulators.
- **Standalone Node.js unavailable:** use a validated Qoder Electron-as-Node
  command for the Skill-local checker and CLI. This does not satisfy `npx`.
- **npx unavailable:** install a complete Node.js/npm distribution or provide
  a working absolute `CANVAS_SERVE_SIM_NPX` path. The Canvas can still use its
  simctl view-only fallback, but it cannot claim H.264, input, orientation, or
  accessibility-tree capabilities.
- **First interaction runtime preparation fails:** verify npm registry/network
  access for `serve-sim@0.1.46`, then rerun the approved preparation command;
  do not use `latest`, install globally, or copy a Helper app manually.
- **Project build later fails:** verify the `.xcodeproj`, runnable scheme, and
  deployment target. The viewer disables code signing; do not create signing
  identities as a setup workaround.
- **Swift package preview target is ambiguous:** export the desired regular
  target from a non-dynamic library product and set `CANVAS_IOS_PACKAGE_TARGET`.
  The first preview build also resolves the pinned preview-discovery package;
  later reloads reuse DerivedData.
