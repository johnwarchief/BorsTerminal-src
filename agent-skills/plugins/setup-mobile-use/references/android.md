# Android Emulator Setup

## Supported Runtime

Mobile Use builds the selected Gradle module, boots or attaches to an
Android Virtual Device, installs the APK, and streams through Emulator gRPC.
It requires an AVD; a physical Android device is not a substitute.

## Install

1. Install [Android Studio](https://developer.android.com/studio/install) and
   complete its first-run setup wizard.
2. In **Tools > SDK Manager**, install:
   - one Android SDK Platform compatible with the project;
   - Android SDK Build-Tools;
   - Android SDK Platform-Tools;
   - Android Emulator;
   - an architecture-compatible system image;
   - Android SDK Command-Line Tools when command-line maintenance is needed.
3. In **Tools > Device Manager**, create one phone AVD from the installed
   system image. See [Create and manage virtual devices](https://developer.android.com/studio/run/managing-avds).
4. Provide JDK 17 or newer. Android Gradle Plugin 8.x requires JDK 17; check the
   project's Gradle/AGP compatibility before choosing a newer JDK. See
   [Java versions in Android builds](https://developer.android.com/build/jdks).

Do not download SDK components or accept licenses without the user's consent.

## Configure Mobile Use

The packaged viewer resolves values in this order:

- SDK: `CANVAS_ANDROID_SDK_ROOT`, `DEVICE_ANDROID_SDK_ROOT`,
  `ANDROID_SDK_ROOT`, `ANDROID_HOME`, then the Android Studio default:
  `~/Library/Android/sdk` on macOS, `~/Android/Sdk` on Linux, or
  `%LOCALAPPDATA%\Android\Sdk` on Windows.
- JDK: `CANVAS_ANDROID_JAVA_HOME`, `DEVICE_ANDROID_JAVA_HOME`, `JAVA_HOME`,
  then the standard Android Studio bundled JBR on macOS, Windows, or Linux;
  macOS also tries `/usr/libexec/java_home` for JDK 21 or 17.
- AVD: `CANVAS_ANDROID_AVD`, `DEVICE_ANDROID_AVD`, then the first name returned
  by `emulator -list-avds`.

For a standard macOS Android Studio installation, the corresponding values are
`CANVAS_ANDROID_SDK_ROOT=~/Library/Android/sdk`,
`CANVAS_ANDROID_JAVA_HOME=/Applications/Android Studio.app/Contents/jbr/Contents/Home`,
and `CANVAS_ANDROID_AVD=<exact-avd-name>`. Apply overrides to the intended IDE
process or its managed launch environment; do not assume a terminal export is
inherited by Qoder.

Set `CANVAS_ANDROID_SDK_ROOT` explicitly for a custom SDK location. Configure
the variables for the IDE process; do not modify a shell profile unless the
user requests it. Windows resolves `adb.exe` and `emulator.exe` automatically
and invokes a project `gradlew.bat` through the Windows command processor.

## Verify Without Booting

```bash
node "/absolute/loaded-setup-mobile-use-skill/scripts/check-mobile-environment.mjs" --platform android --strict
```

The checker requires `adb`, `emulator`, `emulator_controller.proto`, at least
one Build-Tools `aapt`, JDK 17+, and at least one AVD. It only runs
`emulator -list-avds`; it does not boot a device.

Common fixes:

- **No AVD:** install a system image and create a phone in Device Manager.
- **JDK is too old:** point `CANVAS_ANDROID_JAVA_HOME` at a compatible JDK.
- **SDK root is missing:** set `CANVAS_ANDROID_SDK_ROOT` to the SDK Manager path.
- **No `aapt`:** install Android SDK Build-Tools.
- **No controller proto:** update or reinstall Android Emulator from
  [SDK Manager](https://developer.android.com/studio/intro/update).
