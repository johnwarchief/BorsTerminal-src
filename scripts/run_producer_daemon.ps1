# run_producer_daemon.ps1 — Windows PowerShell supervisor for bors-producer daemon
#
# Runs and supervises bors-producer in daemon mode on Windows.
# Features:
#   - Automatic restart on unexpected crash / non-zero exit code
#   - Clean exit when daemon shuts down cleanly (exit code 0) or on Ctrl+C
#   - Optional environment file loading (.env)
#   - Flexible binary location (pre-built EXE or go run fallback)
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts/run_producer_daemon.ps1
#   powershell -ExecutionPolicy Bypass -File scripts/run_producer_daemon.ps1 -Config deploy/config/producer_config.json
#   powershell -ExecutionPolicy Bypass -File scripts/run_producer_daemon.ps1 -DataDir ./data -MaxRestarts 5

param(
    [string]$Config = "deploy/config/producer_config.json",
    [string]$DataDir = "",
    [string]$ExePath = "",
    [string]$EnvFile = "deploy/config/producer.env",
    [int]$MaxRestarts = 0,
    [int]$RestartDelaySec = 5
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

# Load environment file if present
$ResolvedEnvFile = Join-Path $RepoRoot $EnvFile
if (-not (Test-Path $ResolvedEnvFile)) {
    $ResolvedEnvFile = Join-Path $RepoRoot "deploy/config/producer.env.example"
}
if (Test-Path $ResolvedEnvFile) {
    Write-Host "[supervisor] Reading environment template from $ResolvedEnvFile"
    Get-Content $ResolvedEnvFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and ($line -match "^([^=]+)=(.*)$")) {
            $name = $matches[1].Trim()
            $val = $matches[2].Trim()
            if ($val -and -not [Environment]::GetEnvironmentVariable($name)) {
                [Environment]::SetEnvironmentVariable($name, $val, "Process")
            }
        }
    }
}

# Resolve config path
$ResolvedConfig = $Config
if (-not [System.IO.Path]::IsPathRooted($ResolvedConfig)) {
    $ResolvedConfig = Join-Path $RepoRoot $ResolvedConfig
}

# Locate binary or fallback to 'go run ./cmd/bors-producer'
$UseGoRun = $false
$TargetExe = $ExePath
if (-not $TargetExe) {
    $candidates = @(
        (Join-Path $RepoRoot "backend-go\bors-producer.exe"),
        (Join-Path $RepoRoot "dist\bors-producer.exe"),
        (Join-Path $RepoRoot "bors-producer.exe")
    )
    foreach ($cand in $candidates) {
        if (Test-Path $cand) {
            $TargetExe = $cand
            break
        }
    }
}

if (-not $TargetExe -or -not (Test-Path $TargetExe)) {
    # Check if 'go' is available
    $go = Get-Command "go" -ErrorAction SilentlyContinue
    if ($go) {
        $UseGoRun = $true
        Write-Host "[supervisor] Pre-compiled bors-producer.exe not found; using 'go run ./cmd/bors-producer'"
    } else {
        Write-Error "[supervisor] Neither bors-producer.exe nor 'go' compiler was found on PATH."
        exit 1
    }
} else {
    Write-Host "[supervisor] Using binary: $TargetExe"
}

# Build daemon arguments
$daemonArgs = @("daemon")
if (Test-Path $ResolvedConfig) {
    $daemonArgs += "--config=$ResolvedConfig"
    Write-Host "[supervisor] Config file: $ResolvedConfig"
}
if ($DataDir) {
    $daemonArgs += "--data-dir=$DataDir"
    Write-Host "[supervisor] Data dir override: $DataDir"
}

$restarts = 0
Write-Host "[supervisor] Starting BorsTerminal Producer Daemon supervisor loop..."

while ($true) {
    $startTime = Get-Date

    if ($UseGoRun) {
        $backendDir = Join-Path $RepoRoot "backend-go"
        Push-Location $backendDir
        try {
            $allArgs = @("run", "./cmd/bors-producer") + $daemonArgs
            & go $allArgs
            $exitCode = $LASTEXITCODE
        } finally {
            Pop-Location
        }
    } else {
        & $TargetExe $daemonArgs
        $exitCode = $LASTEXITCODE
    }

    $duration = (Get-Date) - $startTime

    if ($exitCode -eq 0) {
        Write-Host "[supervisor] Daemon exited cleanly (code 0) after $($duration.TotalSeconds.ToString('F1'))s. Shutting down supervisor."
        exit 0
    }

    $restarts++
    Write-Warning "[supervisor] Daemon crashed/exited with code $exitCode after $($duration.TotalSeconds.ToString('F1'))s (restart #$restarts)."

    if ($MaxRestarts -gt 0 -and $restarts -ge $MaxRestarts) {
        Write-Error "[supervisor] Maximum restart count ($MaxRestarts) reached. Exiting."
        exit $exitCode
    }

    Write-Host "[supervisor] Restarting in $RestartDelaySec seconds... (Press Ctrl+C to abort)"
    Start-Sleep -Seconds $RestartDelaySec
}
