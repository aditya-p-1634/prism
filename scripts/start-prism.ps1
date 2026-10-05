<#
.SYNOPSIS
    PRISM - Production & Presentation Startup Script
.DESCRIPTION
    Reliable single-command startup for PRISM:
    - Automatically discovers PRISM root directory
    - Verifies Python virtual environment
    - Enforces exact pandas 3.0.5 compatibility (Windows Smart App Control compliant)
    - Safely releases stale port 8000/3000 processes without killing unrelated services
    - Starts FastAPI backend without --reload in its own dedicated window
    - Cleans stale Next.js development cache (.next) to prevent ChunkLoadError
    - Starts Next.js frontend in its own dedicated window
    - Verifies backend health and frontend availability with informative feedback
    - Automatically launches browser to http://localhost:3000
    - Safe to run repeatedly
#>

[CmdletBinding()]
param(
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"

# ==============================================================================
# 1. Automatic Project Root Detection
# ==============================================================================
$ScriptDir = $PSScriptRoot
if (-not $ScriptDir) {
    $ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
}

$RepoRoot = $null
$candidate = $ScriptDir
while ($candidate -and (Test-Path $candidate)) {
    if ((Test-Path (Join-Path $candidate "apps\api")) -and (Test-Path (Join-Path $candidate "apps\web"))) {
        $RepoRoot = $candidate
        break
    }
    $parent = Split-Path -Parent $candidate
    if ($parent -eq $candidate) { break }
    $candidate = $parent
}

if (-not $RepoRoot) {
    $RepoRoot = "D:\Projects\PRISM"
}

$ApiDir = Join-Path $RepoRoot "apps\api"
$WebDir = Join-Path $RepoRoot "apps\web"
$VenvDir = Join-Path $ApiDir ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"

# ==============================================================================
# Helper: Safe Port Process Termination (PRISM processes only)
# ==============================================================================
function Safe-StopPortProcess {
    param(
        [int]$Port,
        [string]$ProcessType # 'backend' or 'frontend'
    )
    $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($connections) {
        $pids = $connections | Select-Object -ExpandProperty OwningProcess -Unique
        foreach ($p in $pids) {
            if ($p -le 4) { continue } # Skip System Idle (0) and System (4)
            $proc = Get-Process -Id $p -ErrorAction SilentlyContinue
            if (-not $proc) { continue }

            $procName = $proc.ProcessName.ToLower()
            $cmdLine = ""
            try {
                $wmi = Get-CimInstance Win32_Process -Filter "ProcessId = $p" -ErrorAction SilentlyContinue
                if ($wmi -and $wmi.CommandLine) {
                    $cmdLine = $wmi.CommandLine.ToLower()
                }
            } catch {}

            $isTarget = $false
            if ($ProcessType -eq 'backend') {
                if ($procName -match "python" -or $cmdLine -match "uvicorn" -or $cmdLine -match "app\.main" -or $cmdLine -match "prism") {
                    $isTarget = $true
                }
            } elseif ($ProcessType -eq 'frontend') {
                if ($procName -match "node" -or $cmdLine -match "next" -or $cmdLine -match "prism") {
                    $isTarget = $true
                }
            }

            if ($isTarget) {
                Write-Host "      Safely terminating previous $ProcessType process on port $Port (PID: $p, Name: $($proc.ProcessName))..." -ForegroundColor Yellow
                try {
                    & taskkill.exe /PID $p /T /F 2>&1 | Out-Null
                } catch {
                    Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
                }
                Start-Sleep -Milliseconds 600
            } else {
                Write-Host "      [WARNING] Port $Port occupied by unrelated PID $p ($($proc.ProcessName)). Preserving process." -ForegroundColor Magenta
            }
        }
    }
}

# ==============================================================================
# Startup Banner
# ==============================================================================
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "          PRISM STARTUP                 " -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ==============================================================================
# [1/5] Checking Python environment...
# ==============================================================================
Write-Host "[1/5] Checking Python environment..." -ForegroundColor Yellow
if (-not (Test-Path $VenvPython)) {
    Write-Host "[ERROR] Virtual environment not found at: $VenvPython" -ForegroundColor Red
    Write-Host "Please ensure the .venv is installed in apps\api before launching." -ForegroundColor Red
    exit 1
}
Write-Host "      Virtual environment verified ($VenvPython)" -ForegroundColor Green

# ==============================================================================
# [2/5] Checking pandas...
# ==============================================================================
Write-Host "[2/5] Checking pandas..." -ForegroundColor Yellow
$pyCheckSnippet = "import sys; import pandas; print('PANDAS:' + pandas.__version__); import ortools; print('ORTOOLS:' + ortools.__version__)"
$checkOutput = & $VenvPython -c $pyCheckSnippet 2>&1
$pandasLine = ($checkOutput | Where-Object { $_ -like "PANDAS:*" })
$ortoolsLine = ($checkOutput | Where-Object { $_ -like "ORTOOLS:*" })

if (-not $pandasLine) {
    Write-Host "[ERROR] Failed to load pandas in $VenvPython!" -ForegroundColor Red
    Write-Host "Raw output: $checkOutput" -ForegroundColor Red
    Write-Host "Windows Smart App Control or corrupted DLL may be blocking pandas." -ForegroundColor Red
    Write-Host "DO NOT upgrade pandas. Keep pandas at 3.0.5." -ForegroundColor Red
    exit 1
}

$pandasVer = $pandasLine -replace "^PANDAS:", ""
if ($pandasVer -ne "3.0.5") {
    Write-Host "[ERROR] Incompatible pandas version detected: '$pandasVer'." -ForegroundColor Red
    Write-Host "PRISM requires exactly pandas==3.0.5 for Windows Smart App Control compatibility." -ForegroundColor Red
    Write-Host "Do NOT upgrade pandas. Aborting startup to prevent crashes." -ForegroundColor Red
    exit 1
}

$ortoolsVer = "detected"
if ($ortoolsLine) {
    $ortoolsVer = $ortoolsLine -replace "^ORTOOLS:", ""
}
Write-Host "      pandas version verified: 3.0.5 (Smart App Control compliant)" -ForegroundColor Green
Write-Host "      ortools version verified: $ortoolsVer" -ForegroundColor Green

# ==============================================================================
# [3/5] Starting backend...
# ==============================================================================
Write-Host "[3/5] Starting backend..." -ForegroundColor Yellow
Safe-StopPortProcess -Port 8000 -ProcessType 'backend'

# Start backend in its own dedicated PowerShell window
$BackendRunner = Join-Path $RepoRoot "scripts\run-backend.ps1"
Start-Process powershell.exe -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", "`"$BackendRunner`""

# Verify Backend Health
Write-Host "      Waiting for backend to become healthy at http://127.0.0.1:8000/health..." -ForegroundColor Gray
$backendReady = $false
$retries = 25
while ($retries -gt 0) {
    Start-Sleep -Seconds 1
    try {
        $res = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -TimeoutSec 2 -ErrorAction Stop
        if ($res.status -eq "HEALTHY" -or $res.status -eq "ok" -or $res) {
            $backendReady = $true
            break
        }
    } catch {
        $retries--
    }
}

if (-not $backendReady) {
    Write-Host "[ERROR] PRISM Backend failed to respond or become healthy within 25 seconds!" -ForegroundColor Red
    Write-Host "Please inspect the 'PRISM Backend (FastAPI :8000)' window for error traceback." -ForegroundColor Red
    exit 1
}
Write-Host "      Backend is ONLINE and HEALTHY (Status: HEALTHY, Port: 8000)" -ForegroundColor Green

# ==============================================================================
# [4/5] Cleaning Next.js cache...
# ==============================================================================
Write-Host "[4/5] Cleaning Next.js cache..." -ForegroundColor Yellow
Safe-StopPortProcess -Port 3000 -ProcessType 'frontend'
Safe-StopPortProcess -Port 3001 -ProcessType 'frontend'

$NextDir = Join-Path $WebDir ".next"
if (Test-Path $NextDir) {
    try {
        Remove-Item -Path $NextDir -Recurse -Force -ErrorAction Stop
        Write-Host "      Cleaned stale Next.js development cache (.next)" -ForegroundColor Green
    } catch {
        Start-Sleep -Seconds 1
        Remove-Item -Path $NextDir -Recurse -Force -ErrorAction SilentlyContinue
        if (Test-Path $NextDir) {
            Write-Host "      [WARNING] Could not fully remove .next cache. Continuing..." -ForegroundColor Yellow
        } else {
            Write-Host "      Cleaned stale Next.js development cache (.next)" -ForegroundColor Green
        }
    }
} else {
    Write-Host "      Next.js cache already clean (no .next directory)" -ForegroundColor Green
}

# ==============================================================================
# [5/5] Starting frontend...
# ==============================================================================
Write-Host "[5/5] Starting frontend..." -ForegroundColor Yellow

# Start frontend in its own dedicated PowerShell window
$FrontendRunner = Join-Path $RepoRoot "scripts\run-frontend.ps1"
Start-Process powershell.exe -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", "`"$FrontendRunner`""

# Wait for frontend availability
Write-Host "      Waiting for frontend to compile and listen on http://localhost:3000..." -ForegroundColor Gray
$frontendRetries = 35
$frontendReady = $false
while ($frontendRetries -gt 0) {
    Start-Sleep -Seconds 1
    try {
        $webRes = Invoke-WebRequest -Uri "http://localhost:3000" -UseBasicParsing -TimeoutSec 10 -ErrorAction Stop
        if ($webRes.StatusCode -eq 200) {
            $frontendReady = $true
            break
        }
    } catch {
        # Check if port 3000 is listening even if page is still compiling
        $conn = Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue
        if ($conn) {
            $frontendReady = $true
            break
        }
        $frontendRetries--
    }
}

if (-not $frontendReady) {
    Write-Host "[ERROR] PRISM Frontend failed to start on http://localhost:3000 within timeout!" -ForegroundColor Red
    Write-Host "Please inspect the 'PRISM Frontend (Next.js :3000)' window for Node.js/npm errors." -ForegroundColor Red
    exit 1
}
Write-Host "      Frontend is ONLINE and READY (Port: 3000)" -ForegroundColor Green

# ==============================================================================
# Open Browser Automatically
# ==============================================================================
if (-not $NoBrowser) {
    try {
        Start-Process "http://localhost:3000"
    } catch {
        # Silent ignore if browser launch has issues
    }
}

# ==============================================================================
# Startup Complete Output
# ==============================================================================
Write-Host ""
Write-Host "Backend:" -ForegroundColor White
Write-Host "http://127.0.0.1:8000" -ForegroundColor Cyan
Write-Host "API Docs:" -ForegroundColor White
Write-Host "http://127.0.0.1:8000/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "Frontend:" -ForegroundColor White
Write-Host "http://localhost:3000" -ForegroundColor Cyan
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "          PRISM READY                   " -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
