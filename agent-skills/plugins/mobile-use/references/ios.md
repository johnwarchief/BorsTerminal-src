# iOS Simulator

Use `<App>.xcodeproj/project.pbxproj` as the Canvas project entry. Individual
`Info.plist` and `main.swift` files are intentionally left to their normal file
handling so one Xcode project contributes only one Mobile Use entry.
Use `Package.swift` for SwiftUI package preview mode. The package target must be
importable through a non-dynamic library product; `CANVAS_IOS_PACKAGE_TARGET`
resolves an otherwise ambiguous target choice.

The Canvas discovers a runnable scheme, selects an available iPhone Simulator,
builds with `CODE_SIGNING_ALLOWED=NO`, installs the app, and launches its bundle
identifier. On the first interactive session the Node host prepares and starts
the pinned `serve-sim@0.1.46` backend directly for H.264, input, orientation,
and AX tree capabilities; it does not generate a native Helper project. If that
runtime cannot be prepared for the selected Simulator, that session must
degrade to view-only and surface the reason.

Package preview mode generates a two-target Xcode project from three source
templates owned and shipped by Mobile Use plus one generated configuration
file. Generation and compilation happen in the user's writable Qoder cache
with that Mac's Xcode; no preview app or dylib is prebuilt in the plugin. The app target stays
running; source edits rebuild a dylib target, copy it to the app container, and
load it with `dlopen`. Treat an unchanged PID plus a `reloaded` status as the
hot-reload proof. Xcode application projects still rebuild, install, and
relaunch their real app target.

Do not invent accessibility container nodes or treat the AX tree as a DOM.
Prefer accessibility identifiers, then semantic role and label. Treat element
paths as snapshot-scoped fallbacks.

The pinned interaction runtime is currently qualified only on arm64 macOS. Do
not claim Intel Mac support until an x86_64 runtime path is verified.

## Diagnosis

- Separate Xcode project/scheme discovery, Simulator target availability,
  application build/install/launch, and XCTest selection. Success at one stage
  does not prove the next.
- The compiled runtime gates H.264, input, orientation, and AX capabilities. If
  the selected session does not advertise them, report it as view-only rather
  than treating a no-op or rejected input as success.
- A discoverable application scheme does not guarantee that the requested
  XCTest target is included. `run-native-test` must preserve runner-selection
  failure separately from assertion failure.
- After launch, use a bounded readiness wait before asserting against the AX
  tree. Element paths and refs expire with the snapshot; prefer stable native
  accessibility identifiers.
