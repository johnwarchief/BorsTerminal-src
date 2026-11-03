# Node Runtime Discovery

Use this reference before running a Mobile Use Skill-local `.mjs` launcher when
`node` is absent from `PATH` or `node --version` fails. Use the validated
invocation in place of `node` in the other setup references.

Discovery is read-only. Do not install Node.js, mutate `PATH`, create symlinks,
or edit a shell profile merely to launch the Skill.

## Discovery order

1. Use an absolute Node.js path supplied by the user when present.
2. Use `node` from `PATH` only when its validation succeeds.
3. Use Qoder's Electron executable as a final fallback, with
   `ELECTRON_RUN_AS_NODE=1` on that invocation:
   - macOS current app:
     `/Applications/Qoder.app/Contents/MacOS/Qoder`
   - macOS legacy app:
     `/Applications/Qoder IDE.app/Contents/MacOS/Qoder`
   - Windows default:
     `%LOCALAPPDATA%\Programs\Qoder\Qoder.exe`

Qoder executables are Electron launchers, not standalone Node helpers. Never
run them as Node without `ELECTRON_RUN_AS_NODE=1`, and reject a candidate that
opens the application, hangs, or fails validation.

## Validate a candidate

For a standalone Node candidate:

```bash
"/absolute/path/to/node" -p 'JSON.stringify({node:process.versions.node,electron:process.versions.electron||null})'
```

For Qoder on macOS:

```bash
ELECTRON_RUN_AS_NODE=1 "/Applications/Qoder.app/Contents/MacOS/Qoder" \
  -p 'JSON.stringify({node:process.versions.node,electron:process.versions.electron||null})'
```

On Windows PowerShell:

```powershell
$env:ELECTRON_RUN_AS_NODE="1"
& "$env:LOCALAPPDATA\Programs\Qoder\Qoder.exe" -p 'JSON.stringify({node:process.versions.node,electron:process.versions.electron||null})'
Remove-Item Env:ELECTRON_RUN_AS_NODE
```

Use a short timeout. Accept only valid JSON with Node.js 20 or newer and a
quick zero exit. Preserve `ELECTRON_RUN_AS_NODE=1` on every later invocation
that uses a Qoder executable.

## Run Mobile Use tools

Use the validated runtime directly with the absolute loaded-Skill path. For
example, the macOS Qoder fallback is:

```bash
ELECTRON_RUN_AS_NODE=1 "/Applications/Qoder.app/Contents/MacOS/Qoder" \
  "/absolute/loaded-setup-mobile-use-skill/scripts/check-mobile-environment.mjs" \
  --platform ios --json
```

For Windows PowerShell, keep the environment change scoped to the invocation
sequence and remove it afterward:

```powershell
$env:ELECTRON_RUN_AS_NODE="1"
& "$env:LOCALAPPDATA\Programs\Qoder\Qoder.exe" `
  "C:\absolute\loaded-setup-mobile-use-skill\scripts\check-mobile-environment.mjs" `
  --platform android --json
Remove-Item Env:ELECTRON_RUN_AS_NODE
```

Report the executable, Node version, and whether it was standalone Node or
Qoder Electron-as-Node.

This fallback runs Mobile Use JavaScript tools only. It does not supply `npm`
or `npx`. The iOS interaction backend still requires a separately resolved
`npx` from `CANVAS_SERVE_SIM_NPX`, the inherited `PATH`, or the user's login
shell. If none resolves, the iOS session remains view-only until the user
provides a complete Node.js/npm distribution or an explicit working `npx`.
