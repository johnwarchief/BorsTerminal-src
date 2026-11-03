# Visual evidence

Read this reference when the task asks for screenshots, screen recording,
visual regression evidence, or an explanation of what appeared on the device.
Use [CLI](cli.md) for the command and plan schemas.

## Keep the claims separate

Report these as different evidence layers:

- **Captured:** the operation receipt succeeded and contains the artifact URI,
  SHA-256 digest, media type, size, source, target, session, and revision.
- **Visually inspected:** an image- or video-capable tool actually opened the
  returned artifact and the Agent evaluated its visible content.
- **Behavior verified:** semantic `assert` or one exact native test established
  the behavior. Pixels alone do not establish this layer.

Never describe an artifact as visually inspected merely because its path,
digest, or media type was returned. A text file reader is not an image viewer.

## Screenshots

Use an explicit `capture_screenshot` plan step for a named milestone or final
state. For diagnostics, set:

```json
{"evidence":{"screenshots":"on-failure"}}
```

Failure capture is best-effort. If both the step and screenshot fail, preserve
the step as the primary error and report the capture problem from
`error.details.evidence.errors`.

When visual inspection is required and the runtime provides an image-capable
file tool, open the exact returned `file:` URI only after confirming the tool
and artifact are on the same host. Use the artifact as-is; do not copy it into
the repository or print base64 through the terminal. If the URI belongs to a
remote host or no image-capable tool exists, report **captured, not visually
inspected** and keep the transport boundary explicit.

When the claim also requires local artifact integrity, use the Skill-local
receipt verifier described in [Tools and boundaries](tools.md#verify-a-local-artifact-receipt).
Digest verification proves that the current local bytes match the receipt; it
still does not prove the image or video was visually inspected.

## Screen recordings

Prefer transactional plan recording:

```json
{"evidence":{"recording":"native"}}
```

The selected session must advertise `device.recording.native`. The plan starts
recording before its first step and stops it on success or failure before it
stops a plan-owned session. Do not silently fall back to host-level screen
recording or another device when the capability is absent.

Use direct `record_screen start|status|stop` only when the user needs manual
recording lifecycle. Always attempt `stop` in cleanup and report a missing stop
artifact. Raw MP4 capture is not automatically model-visible; pair recordings
with screenshots at the key states when the visual content must be reviewed.

## Privacy and retention

Device media can contain account data, notifications, typed text, tokens, or
customer content. Capture only when it is material to the task. Do not publish,
upload, attach, or open media in another application unless the request
authorizes that action. Preserve provenance metadata in the verification
record, but do not claim the digest was independently recomputed unless it was.
