# HarmonyOS arkXtest and UITest

Read this reference for the HDC target's semantic snapshot, input, or device
screenshot implementation. Previewer still uses DevEco Inspector, not these
commands. For source provenance, see
[Source and design notes](source-notes.md).

## Qualification

The shell grammar below is documented by the official OpenHarmony arkXtest
component. It is not automatically a capability guarantee for every HarmonyOS
device. Probe these surfaces on the selected target before advertising them:

```text
["shell", "uitest", "--version"]
["shell", "uitest", "uiInput", "help"]
```

## Input argv

```text
["shell", "uitest", "uiInput", "click", x, y]
["shell", "uitest", "uiInput", "doubleClick", x, y]
["shell", "uitest", "uiInput", "longClick", x, y]
["shell", "uitest", "uiInput", "text", text]
["shell", "uitest", "uiInput", "inputText", x, y, text]
["shell", "uitest", "uiInput", "swipe", x1, y1, x2, y2, velocityPxPerSecond]
["shell", "uitest", "uiInput", "keyEvent", "Back" | "Home" | "Power"]
```

Use `longClick`; a zero-distance swipe may report success without dispatching a
long-press gesture. The optional `swipe` fifth argument is velocity in px/s,
not duration; the documented range is 200-40000 with a default of 600.

Never log typed text or echo it in evidence. Coordinates must come from the
current frame and UI revision.

## Semantic snapshot

Generate a unique remote and local path for every request:

```text
["shell", "uitest", "dumpLayout", "-p", remoteJsonPath]
["file", "recv", remoteJsonPath, localJsonPath]
```

Clean both paths in `finally`. Parse and normalize, at minimum:

- `text` or `originalText` to value;
- `description` to accessible label;
- `id` or `key` to identifier;
- bounds in `[left,top][right,bottom]` form;
- `enabled`, `focused`, `visible`, and `clickable` state.

Cap node count and depth, then issue revision-scoped Canvas refs. A complete
observation authorizes only its own ref frame; the first possible UI mutation
expires that frame. Internal read-only captures must not silently reindex it.
HDC output must not create a second selector or ref system beside
`DeviceUiSnapshot`.

## Screenshot

The official arkXtest shell surface is `screenCap`:

```text
["shell", "uitest", "screenCap", "-p", remotePngPath]
["file", "recv", remotePngPath, localPngPath]
```

Use a unique `.png` path below `/data/local/tmp`. Validate the received file as
PNG, and clean up on success, failure, cancellation, and timeout. Return
broker-owned artifact metadata through the CLI rather than base64 in JSON.

## Capability boundaries

Do not advertise keyboard input, orientation, multitouch, or recording merely
because another framework wraps them. Each needs a qualified implementation on
the selected HarmonyOS/UITest version and a matching Canvas operation contract.
