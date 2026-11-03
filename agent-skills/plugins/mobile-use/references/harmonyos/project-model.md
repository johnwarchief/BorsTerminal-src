# HarmonyOS Project Model

Read this reference when resolving a HarmonyOS project, module, product,
target, route, bundle, or Ability. For evidence provenance, see
[Source and design notes](source-notes.md).

## Canonical descriptors

Resolve project structure from descriptors instead of directory names:

- `AppScope/app.json5`: `app.bundleName`, `versionCode`, and `versionName`.
- `build-profile.json5`: `app.products[]`, `app.buildModeSet[]`, and
  `modules[]`. The current official schema requires `modules[].srcPath`; resolve
  the module from that path.
- `<module>/src/main/module.json5`: `module.name`, `type`, `mainElement`,
  `deviceTypes`, and `abilities[]`.
- `<module>/src/main/resources/base/profile/main_pages.json`: page routes for
  Previewer fallback selection.

A legacy fallback from a missing `srcPath` to `name` must be version-gated and
reported. It is not the primary grammar.

```json5
// AppScope/app.json5
{ app: { bundleName: "com.example.app", versionCode: 1000000, versionName: "1.0.0" } }

// build-profile.json5
{
  app: {
    products: [{ name: "default", runtimeOS: "HarmonyOS" }],
    buildModeSet: [{ name: "debug" }, { name: "release" }]
  },
  modules: [{ name: "entry", srcPath: "./entry", targets: [{ name: "default" }] }]
}

// entry/src/main/module.json5
{
  module: {
    name: "entry",
    type: "entry",
    mainElement: "EntryAbility",
    abilities: [{ name: "EntryAbility", srcEntry: "./ets/entryability/EntryAbility.ets" }]
  }
}
```

Use a real JSON5 parser. Do not strip comments or trailing commas with regular
expressions: strings may legally contain `//`, escaped quotes, and other JSON5
syntax.

## Module and entry identity

| `module.type` | Build product |
| --- | --- |
| `entry`, `feature` | HAP |
| `shared` | HSP |
| `har` | HAR |

Do not assume that module, target, and product are all named `default` or that
every launchable app uses `entry` and `EntryAbility`. Determine identity from
the selected project descriptors. For an already built package, prefer the
official SDK unpacking tool; for an installed bundle, HDC may provide a
qualified `bm dump -n` projection.

The Previewer route precedence is:

1. selected ArkTS page;
2. first `main_pages.json` route;
3. `pages/Index` only as the existing compatibility fallback.

## Future project projections

Other projects identify useful read-only projections beyond the current
viewer: aggregated permissions, root/module dependency conflicts, signing
configuration completeness, and an Ability/page inventory. Treat these as a
backlog, not an implemented contract. Before exposing one, verify its current
official schema, redact signing secrets, constrain paths to the project, and
return structured diagnostics for incomplete modules.
