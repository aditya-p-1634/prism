<#
.SYNOPSIS
    PRISM Backend Service Runner
#>
$Host.UI.RawUI.WindowTitle = "PRISM Backend (FastAPI :8000)"
$ScriptDir = $PSScriptRoot
$RepoRoot = Split-Path -Parent $ScriptDir
$ApiDir = Join-Path $RepoRoot "apps\api"
$VenvPython = Join-Path $ApiDir ".venv\Scripts\python.exe"

Set-Location $ApiDir
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  PRISM FastAPI Backend (Port 8000)                         " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Working Directory: $ApiDir" -ForegroundColor Gray
Write-Host "Python Executable: $VenvPython" -ForegroundColor Gray
Write-Host "Binding to:        127.0.0.1:8000" -ForegroundColor Gray
Write-Host ""

& $VenvPython -m uvicorn app.main:app --host 127.0.0.1 --port 8000
