#!/usr/bin/env node

import { spawnSync } from "node:child_process";
import { accessSync, constants, existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { homedir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const args = parseArgs(process.argv.slice(2));
const selected = args.platform === "all"
  ? ["android", "harmony", "ios"]
  : [args.platform];
const report = {
  schemaVersion: 1,
  generatedAt: new Date().toISOString(),
  host: { platform: process.platform, arch: process.arch },
  platforms: {},
};

for (const platform of selected) {
  report.platforms[platform] = platform === "android"
    ? inspectAndroid()
    : platform === "harmony"
      ? inspectHarmony(args.project)
      : inspectIos(args.prepareIosInteractionRuntime);
}

if (args.json) {
  process.stdout.write(`${JSON.stringify(report, null, 2)}\n`);
} else {
  printHuman(report);
}

if (args.strict && Object.values(report.platforms).some((entry) => !entry.ready)) {
  process.exitCode = 1;
}

function inspectAndroid() {
  const checks = [];
  const sdkResolution = firstEnvironment([
    "CANVAS_ANDROID_SDK_ROOT",
    "DEVICE_ANDROID_SDK_ROOT",
    "ANDROID_SDK_ROOT",
    "ANDROID_HOME",
  ]) ?? {
    source: "viewer default",
    value: process.platform === "win32"
      ? path.join(process.env.LOCALAPPDATA?.trim() || path.join(homedir(), "AppData", "Local"), "Android", "Sdk")
      : process.platform === "darwin"
        ? path.join(homedir(), "Library", "Android", "sdk")
        : path.join(homedir(), "Android", "Sdk"),
  };
  const sdkRoot = path.resolve(sdkResolution.value);
  const executableSuffix = process.platform === "win32" ? ".exe" : "";
  const adb = path.join(sdkRoot, "platform-tools", `adb${executableSuffix}`);
  const emulator = path.join(sdkRoot, "emulator", `emulator${executableSuffix}`);
  const controllerProto = path.join(sdkRoot, "emulator", "lib", "emulator_controller.proto");

  checks.push(fileCheck("android.sdk", "Android SDK root", sdkRoot, "directory"));
  checks.push(fileCheck("android.adb", "Android Platform-Tools adb", adb, "executable"));
  checks.push(fileCheck("android.emulator", "Android Emulator", emulator, "executable"));
  checks.push(fileCheck("android.grpc-proto", "Emulator controller proto", controllerProto, "file"));

  const aapt = newestBuildTool(sdkRoot, `aapt${executableSuffix}`);
  checks.push(aapt
    ? pass("android.aapt", "Android Build-Tools aapt", aapt)
    : fail("android.aapt", "Android Build-Tools aapt", path.join(sdkRoot, "build-tools", "<version>", `aapt${executableSuffix}`)));

  const avdOverride = firstEnvironment(["CANVAS_ANDROID_AVD", "DEVICE_ANDROID_AVD"]);
  let avds = [];
  if (isExecutable(emulator)) {
    const result = run(emulator, ["-list-avds"], 30_000);
    if (result.ok) {
      avds = result.stdout.split(/\r?\n/u).map((value) => value.trim()).filter(Boolean);
      if (avdOverride) {
        checks.push(avds.includes(avdOverride.value)
          ? pass("android.avd", "Android Virtual Device", `${avdOverride.value} (${avdOverride.source})`)
          : fail("android.avd", "Android Virtual Device", `${avdOverride.value} from ${avdOverride.source} was not returned by emulator -list-avds`));
      } else {
        checks.push(avds.length > 0
          ? pass("android.avd", "Android Virtual Device", `${avds.length} found: ${avds.join(", ")}`)
          : fail("android.avd", "Android Virtual Device", "No AVD returned by emulator -list-avds"));
      }
    } else {
      checks.push(fail("android.avd", "Android Virtual Device", result.error));
    }
  } else {
    checks.push(fail("android.avd", "Android Virtual Device", "Cannot list AVDs until Android Emulator is installed"));
  }

  const javaResolution = resolveJavaHome();
  let javaMajor;
  if (javaResolution) {
    const java = path.join(javaResolution.value, "bin", process.platform === "win32" ? "java.exe" : "java");
    const version = run(java, ["-version"], 10_000);
    javaMajor = version.ok ? parseJavaMajor(`${version.stdout}\n${version.stderr}`) : undefined;
    checks.push(javaMajor !== undefined && javaMajor >= 17
      ? pass("android.jdk", "JDK 17 or newer", `${javaResolution.value} (Java ${javaMajor})`)
      : fail("android.jdk", "JDK 17 or newer", version.ok
        ? `${javaResolution.value} reports Java ${javaMajor ?? "unknown"}`
        : version.error));
  } else {
    checks.push(fail("android.jdk", "JDK 17 or newer", "No CANVAS_ANDROID_JAVA_HOME, DEVICE_ANDROID_JAVA_HOME, or JAVA_HOME was resolved"));
  }

  return platformResult("Android Emulator", checks, {
    sdkRoot,
    sdkSource: sdkResolution.source,
    javaHome: javaResolution?.value,
    javaSource: javaResolution?.source,
    javaMajor,
    avds,
    selectedAvd: avdOverride?.value ?? avds[0],
    avdSource: avdOverride?.source ?? (avds.length > 0 ? "first available AVD" : undefined),
  });
}

function inspectHarmony(projectPath) {
  const checks = [];
  const previewerHostSupported = process.platform === "darwin" || process.platform === "win32";
  const defaultDevecoHome = process.platform === "darwin"
    ? "/Applications/DevEco-Studio.app/Contents"
    : process.platform === "win32"
      ? path.join(process.env.ProgramFiles?.trim() || "C:\\Program Files", "Huawei", "DevEco Studio")
      : undefined;
  const devecoResolution = firstEnvironment(["DEVECO_STUDIO_HOME"]) ?? {
    source: defaultDevecoHome ? "viewer default" : "not configured",
    value: defaultDevecoHome ?? path.join(homedir(), ".deveco-studio-unavailable"),
  };
  const devecoHome = path.resolve(devecoResolution.value);
  const hvigor = path.join(devecoHome, "tools", "hvigor", "bin", process.platform === "win32" ? "hvigorw.bat" : "hvigorw");
  const nodeHome = path.join(devecoHome, "tools", "node");
  const nodeCandidates = process.platform === "win32"
    ? [path.join(nodeHome, "node.exe"), path.join(nodeHome, "bin", "node.exe")]
    : [path.join(nodeHome, "bin", "node")];
  const node = nodeCandidates.find(isExecutable) ?? nodeCandidates[0];
  const sdk = path.join(devecoHome, "sdk");
  const openHarmonySdk = path.join(sdk, "default", "openharmony");
  const previewer = path.join(openHarmonySdk, "previewer", "common", "bin", process.platform === "win32" ? "Previewer.exe" : "Previewer");
  const hmsPreviewer = path.join(sdk, "default", "hms", "previewer");
  const hdcOverride = firstEnvironment(["CANVAS_HARMONY_HDC_BIN", "DEVICE_HARMONY_HDC_BIN"]);
  const hdcSdkPath = process.env.HDC_SDK_PATH?.trim();
  const hdcName = process.platform === "win32" ? "hdc.exe" : "hdc";
  const hdcFromPath = findExecutableOnPath(hdcName);
  const hdc = hdcOverride?.value ?? [
    hdcSdkPath ? path.join(hdcSdkPath, hdcName) : undefined,
    path.join(sdk, "default", "HarmonyOS", "toolchains", hdcName),
    path.join(sdk, "default", "openharmony", "toolchains", hdcName),
    hdcFromPath,
  ].filter(Boolean).map((candidate) => path.resolve(candidate)).find((candidate) => isExecutable(candidate));

  const previewerChecks = [
    fileCheck("harmony.deveco", "DevEco Studio home", devecoHome, "directory"),
    fileCheck("harmony.hvigor", "DevEco Hvigor wrapper", hvigor, process.platform === "win32" ? "file" : "executable"),
    fileCheck("harmony.node", "DevEco bundled Node.js", node, "executable"),
    fileCheck("harmony.sdk", "OpenHarmony SDK", openHarmonySdk, "directory"),
    fileCheck("harmony.previewer", "DevEco Previewer binary", previewer, "executable"),
    fileCheck("harmony.hms-previewer", "HMS Previewer runtime", hmsPreviewer, "directory"),
  ];
  checks.push(...(previewerHostSupported ? previewerChecks : previewerChecks.map(optional)));
  if (process.platform === "win32") {
    checks.push(fileCheck(
      "harmony.comspec",
      "Windows command processor",
      process.env.ComSpec?.trim() || "C:\\Windows\\System32\\cmd.exe",
      "file",
    ));
  }
  let hdcVersion;
  let hdcTargets = [];
  if (hdc && isExecutable(hdc)) {
    const version = run(hdc, ["version"], 10_000);
    hdcVersion = version.ok ? (version.stdout || version.stderr).trim().split(/\r?\n/u).find(Boolean) : undefined;
    checks.push(version.ok
      ? pass("harmony.hdc", "HarmonyOS Device Connector", `${hdc}${hdcVersion ? ` (${hdcVersion})` : ""}`)
      : previewerHostSupported
        ? optionalWarn("harmony.hdc", "HarmonyOS Device Connector", version.error)
        : fail("harmony.hdc", "HarmonyOS Device Connector", version.error));
    const targets = run(hdc, ["list", "targets"], 15_000);
    if (targets.ok) {
      hdcTargets = targets.stdout.split(/\r?\n/u).map((line) => line.trim()).filter((line) => line && line !== "[Empty]").map((line) => line.split(/\s+/u)[0]);
      checks.push(hdcTargets.length
        ? pass("harmony.hdc-targets", "Connected HarmonyOS HDC target", `${hdcTargets.length} found: ${hdcTargets.join(", ")}`)
        : previewerHostSupported
          ? optionalWarn("harmony.hdc-targets", "Connected HarmonyOS HDC target", "No target returned by hdc list targets; Previewer remains available")
          : fail("harmony.hdc-targets", "Connected HarmonyOS HDC target", "Linux fallback is attach-only and requires a target from hdc list targets"));
    } else {
      checks.push(previewerHostSupported
        ? optionalWarn("harmony.hdc-targets", "Connected HarmonyOS HDC target", targets.error)
        : fail("harmony.hdc-targets", "Connected HarmonyOS HDC target", targets.error));
    }
  } else {
    const detail = hdcOverride
      ? `${hdcOverride.value} from ${hdcOverride.source} is missing or unusable`
      : previewerHostSupported
        ? "No HDC executable found in HarmonyOS/OpenHarmony SDK toolchains or PATH; Previewer remains available"
        : "Linux fallback requires an HDC executable from CANVAS_HARMONY_HDC_BIN, HDC_SDK_PATH, or PATH";
    checks.push(previewerHostSupported
      ? optionalWarn("harmony.hdc", "HarmonyOS Device Connector", detail)
      : fail("harmony.hdc", "HarmonyOS Device Connector", detail));
  }

  const configResolution = resolveHarmonyDeviceConfig(devecoHome, projectPath);
  if (configResolution) {
    const configCheck = fileCheck(
      "harmony.device-config",
      "Previewer phone configuration",
      configResolution.value,
      "file",
    );
    configCheck.detail = `${configCheck.detail} (${configResolution.source})`;
    checks.push(previewerHostSupported ? configCheck : optional(configCheck));
  } else {
    const missingConfig = fail(
      "harmony.device-config",
      "Previewer phone configuration",
      "No explicit, project, or DevEco fallback phone configuration was found",
    );
    checks.push(previewerHostSupported ? missingConfig : optional(missingConfig));
  }

  checks.push(previewerHostSupported
    ? pass("harmony.host-mode", "Host runtime mode", "DevEco Previewer plus optional HDC targets")
    : hdc && hdcTargets.length > 0
      ? pass("harmony.host-mode", "Host runtime mode", "Linux HDC-only attach fallback")
      : fail("harmony.host-mode", "Host runtime mode", "DevEco Previewer is unavailable on Linux; connect an HDC target for attach-only mode"));

  return platformResult("HarmonyOS DevEco Previewer and HDC", checks, {
    devecoHome,
    devecoSource: devecoResolution.source,
    project: projectPath ? path.resolve(projectPath) : undefined,
    deviceConfig: configResolution?.value,
    deviceConfigSource: configResolution?.source,
    hdc,
    hdcSource: hdcOverride?.source
      ?? (hdcSdkPath && hdc?.startsWith(path.resolve(hdcSdkPath))
        ? "HDC_SDK_PATH"
        : hdcFromPath && hdc === path.resolve(hdcFromPath)
          ? "PATH"
          : hdc
            ? "DevEco SDK"
            : undefined),
    hdcVersion,
    hdcTargets,
    runtimeMode: previewerHostSupported ? "previewer-and-hdc" : "hdc-attach-only",
  });
}

function inspectIos(prepareInteractionRuntime) {
  if (process.platform !== "darwin") {
    return {
      name: "iOS Simulator",
      status: "unsupported",
      ready: false,
      checks: [fail("ios.host", "macOS host", `Unsupported host: ${process.platform}`)],
      details: {},
    };
  }

  const checks = [];
  const developerDirResult = run("xcode-select", ["-p"], 10_000);
  const developerDir = developerDirResult.ok ? developerDirResult.stdout.trim() : undefined;
  const installedXcodeDeveloperDirs = findFullXcodeDeveloperDirectories(developerDir);
  checks.push(installedXcodeDeveloperDirs.length > 0
    ? pass("ios.xcode-installation", "Installed full Xcode developer directory", installedXcodeDeveloperDirs.join(", "))
    : fail("ios.xcode-installation", "Installed full Xcode developer directory", "No full Xcode application was found"));
  checks.push(developerDir && isFullXcodeDeveloperDirectory(developerDir)
    ? pass("ios.xcode-select", "Active full Xcode developer directory", developerDir)
    : fail("ios.xcode-select", "Active full Xcode developer directory", developerDir || developerDirResult.error));

  const xcodeVersionResult = run("xcodebuild", ["-version"], 15_000);
  checks.push(xcodeVersionResult.ok
    ? pass("ios.xcodebuild", "Xcode build tools", xcodeVersionResult.stdout.trim().replace(/\r?\n/gu, " · "))
    : fail("ios.xcodebuild", "Xcode build tools", xcodeVersionResult.error));

  const simctlResult = run("xcrun", ["--find", "simctl"], 10_000);
  checks.push(simctlResult.ok
    ? pass("ios.simctl", "Simulator control tool", simctlResult.stdout.trim())
    : fail("ios.simctl", "Simulator control tool", simctlResult.error));

  let iosRuntimes = [];
  const runtimeResult = run("xcrun", ["simctl", "list", "runtimes", "available", "--json"], 20_000);
  if (runtimeResult.ok) {
    try {
      iosRuntimes = (JSON.parse(runtimeResult.stdout).runtimes ?? []).filter((runtime) => (
        runtime?.isAvailable !== false
        && (/^iOS\b/u.test(runtime?.name ?? "") || /\.SimRuntime\.iOS-/u.test(runtime?.identifier ?? ""))
      ));
      checks.push(iosRuntimes.length > 0
        ? pass("ios.runtime", "Installed iOS Simulator runtime", `${iosRuntimes.length} found: ${iosRuntimes.map((runtime) => runtime.name ?? runtime.identifier).join(", ")}`)
        : fail("ios.runtime", "Installed iOS Simulator runtime", "No available iOS Simulator runtime was found"));
    } catch (error) {
      checks.push(fail("ios.runtime", "Installed iOS Simulator runtime", `Could not parse simctl JSON: ${error.message}`));
    }
  } else {
    checks.push(fail("ios.runtime", "Installed iOS Simulator runtime", runtimeResult.error));
  }

  let iphones = [];
  const deviceResult = run("xcrun", ["simctl", "list", "devices", "available", "--json"], 20_000);
  if (deviceResult.ok) {
    try {
      const devices = JSON.parse(deviceResult.stdout).devices ?? {};
      iphones = Object.values(devices).flat().filter((device) => device?.isAvailable !== false && /^iPhone\b/u.test(device?.name ?? ""));
      checks.push(iphones.length > 0
        ? pass("ios.iphone", "Available iPhone Simulator", `${iphones.length} found: ${iphones.slice(0, 5).map((device) => device.name).join(", ")}`)
        : fail(
          "ios.iphone",
          "Available iPhone Simulator",
          iosRuntimes.length > 0
            ? "An iOS runtime is installed, but no available iPhone Simulator was found"
            : "Cannot discover an available iPhone until an iOS Simulator runtime is installed",
        ));
    } catch (error) {
      checks.push(fail("ios.iphone", "Available iPhone Simulator", `Could not parse simctl JSON: ${error.message}`));
    }
  } else {
    checks.push(fail("ios.iphone", "Available iPhone Simulator", deviceResult.error));
  }

  const scriptDir = path.dirname(fileURLToPath(import.meta.url));
  const pluginRoot = path.resolve(scriptDir, "../../..");
  const interactionRuntime = readIosInteractionRuntime(pluginRoot);
  const previewRuntime = readIosPreviewRuntime(pluginRoot);
  const helper = path.join(
    pluginRoot,
    "canvases",
    "ios-project",
    "simulator",
    "Qoder iOS Simulator Helper.app",
    "Contents",
    "MacOS",
    "QoderIOSSimulatorHelper",
  );
  checks.push(!existsSync(helper)
    ? pass("ios.helper", "Prebuilt iOS helper", "Not packaged; the Canvas Node host prepares interaction on first use")
    : fail("ios.helper", "Prebuilt iOS helper", `Unexpected bundled executable: ${helper}`));

  const nodePath = isExecutable(process.execPath)
    ? process.execPath
    : findExecutableOnPath(process.platform === "win32" ? "node.exe" : "node");
  const nodeSource = process.versions.electron
    ? /qoder/iu.test(path.basename(process.execPath))
      ? "Qoder Electron-as-Node"
      : "Electron-as-Node"
    : nodePath === process.execPath
      ? "checker process runtime"
      : nodePath
        ? "PATH"
        : undefined;
  const npmPath = findExecutableOnPath(process.platform === "win32" ? "npm.cmd" : "npm");
  const npxResolution = resolveIosNpx();
  const npxPath = npxResolution.value;
  const runtimeEnvironment = iosRuntimeEnvironment({ nodePath, npmPath, npxPath });

  const nodeResult = nodePath
    ? run(nodePath, ["--version"], 10_000, { env: runtimeEnvironment })
    : { ok: false, error: "No Node.js executable was resolved" };
  const nodeMajor = nodeResult.ok ? parseNodeMajor(nodeResult.stdout) : undefined;
  checks.push(nodeResult.ok && (nodeMajor ?? 0) >= 20
    ? pass("ios.node", "Node.js runtime", `${nodeResult.stdout.trim()} · ${nodePath} (${nodeSource})`)
    : fail("ios.node", "Node.js runtime", nodeResult.ok
      ? `${nodePath} reports Node ${nodeResult.stdout.trim()}; Mobile Use requires Node 20 or newer`
      : nodeResult.error));

  const npmResult = npmPath
    ? run(npmPath, ["--version"], 10_000, { env: runtimeEnvironment })
    : { ok: false, error: "No npm executable was found on PATH" };
  checks.push(npmResult.ok
    ? optional(pass("ios.npm", "npm package manager", `npm ${npmResult.stdout.trim()} · ${npmPath}`))
    : optionalWarn("ios.npm", "npm package manager", `${npmResult.error}; Mobile Use invokes npx directly`));

  const npxResult = npxPath
    ? run(npxPath, ["--version"], 10_000, { env: runtimeEnvironment })
    : { ok: false, error: npxResolution.error };
  checks.push(npxResult.ok
    ? pass("ios.npx", "npx package launcher", `npx ${npxResult.stdout.trim()} · ${npxPath} (${npxResolution.source})`)
    : fail("ios.npx", "npx package launcher", npxResult.error));

  if (prepareInteractionRuntime) {
    if (npxResult.ok) {
      const prepareResult = run(
        npxPath,
        ["--yes", `serve-sim@${interactionRuntime.version}`, "--version"],
        120_000,
        { env: runtimeEnvironment },
      );
      const actualVersion = prepareResult.ok ? prepareResult.stdout.trim() : "";
      checks.push(prepareResult.ok && actualVersion === interactionRuntime.version
        ? pass("ios.serve-sim", "Pinned iOS interaction runtime", `serve-sim ${actualVersion} prepared through ${npxPath}`)
        : fail(
          "ios.serve-sim",
          "Pinned iOS interaction runtime",
          prepareResult.ok
            ? `Expected serve-sim ${interactionRuntime.version}, received ${actualVersion || "no version"}`
            : prepareResult.error,
        ));
    } else {
      checks.push(fail(
        "ios.serve-sim",
        "Pinned iOS interaction runtime",
        `Cannot prepare serve-sim ${interactionRuntime.version} until npx is available`,
      ));
    }
  } else {
    checks.push(optionalWarn(
      "ios.serve-sim",
      "Pinned iOS interaction runtime",
      `Not prepared by this read-only check; after approval run with --prepare-ios-interaction-runtime to cache and verify serve-sim ${interactionRuntime.version}`,
    ));
  }
  checks.push(process.arch === "arm64"
    ? pass("ios.arch", "Apple silicon host", process.arch)
    : fail("ios.arch", "Apple silicon host", `serve-sim runtime is not qualified for ${process.arch}`));
  const packagedPreviewRoot = path.join(pluginRoot, "canvases", "ios-project", "simulator", "swift-package-preview");
  const sourcePreviewRoot = path.join(pluginRoot, "runtime", "ios", "swift-package-preview");
  const previewInputs = existsSync(packagedPreviewRoot)
    ? [
      "swift-package-preview.mjs",
      "lib/swift-package-preview-project.mjs",
      "templates/CanvasPreviewHost.swift",
      "templates/CanvasPreviewReload.swift",
      "templates/CanvasPreviewRegistry.swift",
    ].map((relativePath) => path.join(packagedPreviewRoot, relativePath))
    : [
      "swift-package-preview.mjs",
      "lib/swift-package-preview-project.mjs",
      "templates/CanvasPreviewHost.swift",
      "templates/CanvasPreviewReload.swift",
      "templates/CanvasPreviewRegistry.swift",
    ].map((relativePath) => path.join(sourcePreviewRoot, relativePath));
  checks.push(previewInputs.every((candidate) => existsSync(candidate))
    ? pass("ios.swiftui-preview", "SwiftUI package preview compiler", "3 Swift templates + generated module configuration")
    : fail("ios.swiftui-preview", "SwiftUI package preview compiler", "Packaged compiler inputs are incomplete"));

  return platformResult("iOS Simulator", checks, {
    developerDir,
    installedXcodeDeveloperDirs,
    iosRuntimes: iosRuntimes.map(({ name, identifier, version }) => ({ name, identifier, version })),
    iphones: iphones.map(({ name, udid, state }) => ({ name, udid, state })),
    interactionRuntime,
    interactionRuntimePrepared: Boolean(prepareInteractionRuntime && checks.find(({ id }) => id === "ios.serve-sim")?.status === "pass"),
    interactionRuntimeVerifiedThisRun: Boolean(prepareInteractionRuntime && checks.find(({ id }) => id === "ios.serve-sim")?.status === "pass"),
    nodePath,
    nodeSource,
    npmPath,
    npxPath,
    npxSource: npxResolution.source,
    recommendedIdeEnvironment: npxPath
      ? {
        CANVAS_SERVE_SIM_NPX: npxPath,
        pathEntries: runtimePathEntries({ nodePath, npmPath, npxPath }),
      }
      : undefined,
    previewRuntime,
  });
}

function readIosInteractionRuntime(pluginRoot) {
  try {
    const provenance = JSON.parse(readFileSync(path.join(pluginRoot, "canvases", "BUILD_PROVENANCE.json"), "utf8"));
    if (provenance.iosInteractionRuntime?.backend === "serve-sim") return provenance.iosInteractionRuntime;
  } catch {
    // Fall through to the source default when checking an unassembled tree.
  }
  return { backend: "serve-sim", version: "0.1.46", delivery: "host-node-runtime" };
}

function readIosPreviewRuntime(pluginRoot) {
  try {
    const provenance = JSON.parse(readFileSync(path.join(pluginRoot, "canvases", "BUILD_PROVENANCE.json"), "utf8"));
    if (provenance.iosSwiftPackagePreview?.delivery === "generated-xcode-project") {
      return provenance.iosSwiftPackagePreview;
    }
  } catch {
    // Fall through to the source default when checking an unassembled tree.
  }
  return { delivery: "generated-xcode-project", templateSources: 3, generatedSources: 4, reload: "dylib-dlopen" };
}

function resolveJavaHome() {
  const explicitOverride = firstEnvironment([
    "CANVAS_ANDROID_JAVA_HOME",
    "DEVICE_ANDROID_JAVA_HOME",
  ]);
  if (explicitOverride) return explicitOverride;

  const candidates = [];
  const javaHome = process.env.JAVA_HOME?.trim();
  if (javaHome) candidates.push({ source: "JAVA_HOME", value: javaHome });
  if (process.platform === "darwin") {
    candidates.push({
      source: "Android Studio default",
      value: "/Applications/Android Studio.app/Contents/jbr/Contents/Home",
    });
    for (const version of ["21", "17"]) {
      const result = run("/usr/libexec/java_home", ["-v", version], 10_000);
      const value = result.ok ? result.stdout.trim() : "";
      if (value && !candidates.some((candidate) => candidate.value === value)) {
        candidates.push({ source: `/usr/libexec/java_home -v ${version}`, value });
      }
    }
  } else if (process.platform === "win32") {
    candidates.push({
      source: "Android Studio default",
      value: path.join(process.env.ProgramFiles?.trim() || "C:\\Program Files", "Android", "Android Studio", "jbr"),
    });
  } else if (process.platform === "linux") {
    candidates.push(
      { source: "Android Studio default", value: "/opt/android-studio/jbr" },
      { source: "Android Studio user install", value: path.join(homedir(), "android-studio", "jbr") },
    );
  }

  for (const candidate of candidates) {
    const java = path.join(candidate.value, "bin", process.platform === "win32" ? "java.exe" : "java");
    const result = run(java, ["-version"], 10_000);
    if (result.ok && (parseJavaMajor(`${result.stdout}\n${result.stderr}`) ?? 0) >= 17) {
      return candidate;
    }
  }
  return candidates[0];
}

function resolveHarmonyDeviceConfig(devecoHome, projectPath) {
  const configured = firstEnvironment([
    "CANVAS_HARMONY_DEVICE_CONFIG",
    "DEVICE_HARMONY_DEVICE_CONFIG",
  ]);
  if (configured) return configured;

  const candidates = [];
  if (projectPath) {
    candidates.push({
      source: "project .idea previewer",
      value: path.join(path.resolve(projectPath), ".idea", "previewer", "phone", "phoneSettingConfig_rd.json"),
    });
  }
  candidates.push(
    {
      source: "DevEco OpenHarmony preview server",
      value: path.join(devecoHome, "plugins", "openharmony", "openharmony-preview-server", "deviceConfigJson", "phoneSettingConfig.json"),
    },
    {
      source: "DevEco CodeGenie preview template",
      value: path.join(devecoHome, "plugins", "codegenie-plugin", "previewProjectTemplate", "phoneSettingConfig_Phone.json"),
    },
  );
  return candidates.find((candidate) => existsSync(candidate.value));
}

function newestBuildTool(sdkRoot, executableName) {
  const root = path.join(sdkRoot, "build-tools");
  try {
    return readdirSync(root, { withFileTypes: true })
      .filter((entry) => entry.isDirectory())
      .map((entry) => path.join(root, entry.name, executableName))
      .filter((candidate) => isExecutable(candidate))
      .sort((left, right) => right.localeCompare(left, undefined, { numeric: true }))[0];
  } catch {
    return undefined;
  }
}

function platformResult(name, checks, details) {
  const ready = checks.filter((check) => check.required).every((check) => check.status === "pass");
  return { name, status: ready ? "ready" : "needs-setup", ready, checks, details };
}

function fileCheck(id, label, target, kind) {
  try {
    const stats = statSync(target);
    const validType = kind === "directory" ? stats.isDirectory() : stats.isFile();
    if (!validType) return fail(id, label, `${target} is not a ${kind}`);
    if (kind === "executable") accessSync(target, constants.X_OK);
    return pass(id, label, target);
  } catch {
    return fail(id, label, `${target} is missing or unusable`);
  }
}

function isExecutable(target) {
  try {
    accessSync(target, process.platform === "win32" ? constants.F_OK : constants.X_OK);
    return statSync(target).isFile();
  } catch {
    return false;
  }
}

function findExecutableOnPath(executableName) {
  for (const entry of (process.env.PATH ?? "").split(path.delimiter)) {
    const directory = entry.trim().replace(/^"|"$/gu, "");
    if (!directory) continue;
    const candidate = path.join(directory, executableName);
    if (isExecutable(candidate)) return candidate;
  }
  return undefined;
}

function resolveExecutable(command) {
  if (!command) return undefined;
  if (path.isAbsolute(command) || command.includes(path.sep)) {
    const candidate = path.resolve(command);
    return isExecutable(candidate) ? candidate : undefined;
  }
  return findExecutableOnPath(command);
}

function resolveIosNpx() {
  const configured = firstEnvironment(["CANVAS_SERVE_SIM_NPX"]);
  if (configured) {
    const value = resolveExecutable(configured.value);
    return value
      ? { value, source: configured.source }
      : {
        value: undefined,
        source: configured.source,
        error: `${configured.value} from ${configured.source} is missing or unusable`,
      };
  }

  const executableName = process.platform === "win32" ? "npx.cmd" : "npx";
  const fromPath = findExecutableOnPath(executableName);
  if (fromPath) return { value: fromPath, source: "PATH" };

  if (process.platform !== "win32") {
    const shells = [process.env.SHELL?.trim(), "/bin/zsh", "/bin/bash"]
      .filter((value) => value && path.isAbsolute(value));
    for (const shell of [...new Set(shells)]) {
      if (!isExecutable(shell)) continue;
      const result = run(shell, ["-ilc", "command -v npx"], 10_000);
      if (!result.ok) continue;
      const candidates = result.stdout.split(/\r?\n/u).map((value) => value.trim()).filter(Boolean).reverse();
      const value = candidates.find((candidate) => path.isAbsolute(candidate) && isExecutable(candidate));
      if (value) return { value, source: `login shell ${shell}` };
    }
  }

  return {
    value: undefined,
    source: "unresolved",
    error: "No npx executable was found through CANVAS_SERVE_SIM_NPX, PATH, or the login shell",
  };
}

function findFullXcodeDeveloperDirectories(activeDeveloperDir) {
  const candidates = [activeDeveloperDir, process.env.DEVELOPER_DIR?.trim()];
  try {
    candidates.push(...readdirSync("/Applications", { withFileTypes: true })
      .filter((entry) => (entry.isDirectory() || entry.isSymbolicLink()) && /^Xcode.*\.app$/u.test(entry.name))
      .map((entry) => path.join("/Applications", entry.name, "Contents", "Developer")));
  } catch {
    // A nonstandard host may not expose /Applications; explicit and active
    // developer directories remain eligible.
  }
  return [...new Set(candidates.filter(Boolean).map((candidate) => path.resolve(candidate)))]
    .filter(isFullXcodeDeveloperDirectory);
}

function isFullXcodeDeveloperDirectory(candidate) {
  try {
    return statSync(candidate).isDirectory()
      && statSync(path.join(candidate, "Platforms")).isDirectory()
      && !candidate.endsWith("/CommandLineTools");
  } catch {
    return false;
  }
}

function runtimePathEntries({ nodePath, npmPath, npxPath }) {
  return [...new Set([nodePath, npmPath, npxPath]
    .filter(Boolean)
    .map((candidate) => path.dirname(candidate)))];
}

function iosRuntimeEnvironment(paths) {
  const entries = runtimePathEntries(paths);
  const currentPath = process.env.PATH ?? "";
  return {
    ...process.env,
    ...(process.versions.electron ? { ELECTRON_RUN_AS_NODE: "1" } : {}),
    PATH: [...entries, ...currentPath.split(path.delimiter).filter(Boolean)]
      .filter((entry, index, values) => values.indexOf(entry) === index)
      .join(path.delimiter),
  };
}

function pass(id, label, detail) {
  return { id, label, status: "pass", required: true, detail };
}

function fail(id, label, detail) {
  return { id, label, status: "fail", required: true, detail };
}

function optionalWarn(id, label, detail) {
  return { id, label, status: "warn", required: false, detail };
}

function optional(check) {
  return {
    ...check,
    status: check.status === "fail" ? "warn" : check.status,
    required: false,
  };
}

function firstEnvironment(names) {
  for (const name of names) {
    const value = process.env[name]?.trim();
    if (value) return { source: name, value };
  }
  return undefined;
}

function parseJavaMajor(output) {
  const raw = /(?:openjdk|java) version "([\d.]+)/iu.exec(output)?.[1];
  if (!raw) return undefined;
  const parts = raw.split(".").map(Number);
  return parts[0] === 1 ? parts[1] : parts[0];
}

function parseNodeMajor(output) {
  const raw = /^v?(\d+)/u.exec(output.trim())?.[1];
  return raw ? Number(raw) : undefined;
}

function run(command, commandArgs, timeout, options = {}) {
  const isWindowsWrapper = process.platform === "win32" && /\.(?:bat|cmd)$/iu.test(command);
  const executable = isWindowsWrapper
    ? process.env.ComSpec?.trim() || "C:\\Windows\\System32\\cmd.exe"
    : command;
  const executableArgs = isWindowsWrapper
    ? ["/d", "/s", "/c", command, ...commandArgs]
    : commandArgs;
  const result = spawnSync(executable, executableArgs, {
    encoding: "utf8",
    maxBuffer: 4 * 1024 * 1024,
    timeout,
    windowsHide: true,
    ...(options.env ? { env: options.env } : {}),
  });
  const stdout = result.stdout ?? "";
  const stderr = result.stderr ?? "";
  if (result.status === 0) return { ok: true, stdout, stderr };
  const reason = result.error?.message
    ?? stderr.trim()
    ?? stdout.trim()
    ?? `${executable} exited with ${String(result.status)}`;
  return { ok: false, stdout, stderr, error: reason };
}

function printHuman(value) {
  process.stdout.write(`Mobile Use environment (${value.host.platform}/${value.host.arch})\n`);
  for (const platform of Object.values(value.platforms)) {
    process.stdout.write(`\n${platform.ready ? "READY" : platform.status.toUpperCase()}: ${platform.name}\n`);
    for (const check of platform.checks) {
      const marker = check.status === "pass" ? "✓" : check.status === "warn" ? "!" : "✗";
      process.stdout.write(`  ${marker} ${check.label}: ${check.detail}\n`);
    }
  }
}

function parseArgs(values) {
  let platform = "all";
  let project;
  let json = false;
  let strict = false;
  let prepareIosInteractionRuntime = false;
  for (let index = 0; index < values.length; index += 1) {
    const value = values[index];
    if (value === "--platform") platform = values[++index];
    else if (value === "--project") project = values[++index];
    else if (value === "--json") json = true;
    else if (value === "--strict") strict = true;
    else if (value === "--prepare-ios-interaction-runtime") prepareIosInteractionRuntime = true;
    else if (value === "--help" || value === "-h") {
      process.stdout.write("Usage: check-mobile-environment.mjs [--platform android|harmony|ios|all] [--project PATH] [--json] [--strict] [--prepare-ios-interaction-runtime]\n");
      process.exit(0);
    } else {
      throw new Error(`Unknown argument: ${value}`);
    }
  }
  if (!["android", "harmony", "ios", "all"].includes(platform)) {
    throw new Error(`Unsupported platform: ${String(platform)}`);
  }
  if (project === undefined && values.includes("--project")) {
    throw new Error("--project requires a path");
  }
  if (prepareIosInteractionRuntime && platform !== "ios" && platform !== "all") {
    throw new Error("--prepare-ios-interaction-runtime requires --platform ios or --platform all");
  }
  return { platform, project, json, strict, prepareIosInteractionRuntime };
}
