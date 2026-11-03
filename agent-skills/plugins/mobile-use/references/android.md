# Android Emulator

The Android Canvas resolves the project root through its Gradle Wrapper, builds
the selected module and variant, installs the newest APK, and launches the
resolved application id and activity.

Defaults:

- module: inferred from the selected file, otherwise `app`
- variant: `debug`
- AVD: first configured AVD when `CANVAS_ANDROID_AVD` is unset
- transport: Android Emulator gRPC for frames and input
- semantic tree: UIAutomator

Useful overrides are `CANVAS_ANDROID_SDK_ROOT`, `CANVAS_ANDROID_JAVA_HOME`,
`CANVAS_ANDROID_AVD`, `CANVAS_ANDROID_MODULE`, `CANVAS_ANDROID_VARIANT`,
`CANVAS_ANDROID_APPLICATION_ID`, and `CANVAS_ANDROID_ACTIVITY`.

Do not claim physical-device or scrcpy support from this plugin version. Keep
Gradle outputs and APKs in the project build directories rather than copying
them into the plugin.

## Diagnosis

- Separate Gradle/JDK/project failures from Emulator discovery and boot
  failures. A buildable APK does not prove that the selected AVD is online.
- The current viewer publishes Android Emulator targets. Absence from live
  Canvas inventory is not proof that no AVD exists on the machine; use the setup
  Skill for environment discovery.
- For normalized UIAutomator selectors, bounded scroll and re-observe, app
  readiness, package-scoped logs, and the current profiling boundary, read
  [Android runtime QA](android/runtime-qa.md).
- Frame, touch, keyboard, application, logs, and native-test operations remain
  capability-gated. Do not substitute direct ADB commands when the selected
  session does not advertise the operation.
