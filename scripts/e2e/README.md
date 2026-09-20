# E2E / regression harness for BorsTerminal Ultimate releases

These scripts are the exact harness used to verify the v1.0.9 release
(build -> installer -> silent update -> publish). All paths are relative to
the repo root (resolved via `$PSScriptRoot`), so they work from any clone.

Run with PowerShell (bash mangles `/FLAG` style arguments, so always use
`-File`, never inline `-Command`).

| script | what it proves | result file |
|---|---|---|
| `check_install.ps1` | install registry keys (DisplayVersion, InstallLocation) + whether the app is running | stdout |
| `updater_verify.ps1` | post-install facts: reg/file/product version, exe exists, running pids | stdout (JSON) |
| `install_silent.ps1` | full silent-update E2E with the **same flags `api/update.py` builds**; reg DisplayVersion + exe FileVersion + app API + screener must all agree | `%TEMP%\cline\install_e2e_result.json` |
| `maint_silent_test.ps1` | regression test for the Inno maintenance mode: runs an arbitrary setup `/VERYSILENT` and asserts the app comes back healthy | `%TEMP%\cline\maint_silent_result.json` |
| `final_check.ps1` | live app on port 8001: `/api/update/version`, `/api/update/check` (current==latest), `/api/screener` rows | stdout |
| `e2e_readonly.ps1` | runs the frozen build from a **read-only** dir (simulates `Program Files` for a standard user): screener must still return 200 with `market.db` + cache landing under `%LOCALAPPDATA%`, and nothing written into the read-only dir | `%TEMP%\cline\e2e_result.json` |

Notes
- `install_silent.ps1` reads the installer password the same way the app's own
  updater does (`installer/.setup_password.iss`, gitignored). If the file is
  missing it fails fast instead of silently degrading to a visible wizard.
- `Start-Process -Wait` must NOT be used on the setup exe: the `[Run]` section
  (nowait postinstall) launches the detached app and `-Wait` hangs. Both install
  scripts poll the uninstall registry key / setup process exit instead.
- The app is single-instance and the postinstall `[Run]` entry starts it on the
  default port 8001, so the harness probes that instance (do not try to launch a
  second one on a custom port).
