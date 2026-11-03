# HarmonyOS Hvigor Builds

Read this reference for Previewer builds, HAP/HSP/HAR/APP tasks, product and
target selection, or build-artifact qualification. For source provenance, see
[Source and design notes](source-notes.md).

## Previewer versus installable packages

Previewer and installable packages are separate target kinds. Huawei documents
`PreviewBuild` as an Hvigor task. The extra `previewer.replace.*` parameters
below are this repository's qualified DevEco integration seam, not a public
HarmonyOS command contract:

```text
["PreviewBuild", "--no-daemon", "--stacktrace",
 "-p", "buildRoot=.preview",
 "-p", "module=<module>@<target>",
 "-p", "product=<product>",
 "-p", "previewer.replace.page=<route>",
 "-p", "previewer.replace.srcPath=src/main",
 "-p", "pageType=page",
 "-p", "mainModule=<module>"]
```

The current Previewer adapter maps its single `variant` setting to both target
and product. Preserve that compatibility for Previewer, but do not generalize
the equality to HAP/HDC project discovery.

## Official installable-package shapes

HAP:

```text
["--mode", "module",
 "-p", "product=<product>",
 "-p", "module=<module>@<target>",
 "-p", "buildMode=<debug|release>",
 "assembleHap"]
```

APP:

```text
["--mode", "project",
 "-p", "product=<product>",
 "-p", "buildMode=<debug|release>",
 "assembleApp"]
```

Official task documentation defines `assembleHap`, `assembleHsp`,
`assembleHar`, and `assembleApp`. For HSP and HAR, derive the exact argv from
the installed project's `hvigorw taskTree` and DevEco/Hvigor version rather
than copying third-party argument ordering.

When `buildMode` is omitted, official behavior defaults APP to `release` and
HAP/HSP/HAR to `debug`. Pass it explicitly for deterministic automation.
`module=<module>@<target>` binds a module target, not a product, even when both
happen to be named `default`.

## Artifact oracle

Do not select an artifact by guessing a fixed output path or taking the newest
HAP in the project.

1. Record the build start time.
2. Constrain candidates to the selected module's `build/**/outputs` directory.
3. Match module, product, target, and build mode.
4. Reject candidates older than the build invocation.
5. Fail closed on zero or multiple candidates.
6. Verify the selected package identity before installation.

Prefer the SDK's official `app_unpacking_tool.jar` or its
`UncompressEntrance.parseHap` API to verify bundle, module, module type, device
type, and entry Ability. Do not treat a successful Hvigor exit alone as proof
that the correct artifact was selected.

## Adapter constraints

- Pass argv arrays without shell interpolation.
- Bound build time and output, while retaining structured stderr evidence.
- Keep generated packages in the project build tree; do not copy them into the
  plugin.
- Discover the installed task graph before claiming HSP/HAR support.
- Never log signing material or package credentials.
