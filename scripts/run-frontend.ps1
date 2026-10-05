<#
.SYNOPSIS
    PRISM Frontend Service Runner
#>
$Host.UI.RawUI.WindowTitle = "PRISM Frontend (Next.js :3000)"
$ScriptDir = $PSScriptRoot
$RepoRoot = Split-Path -Parent $ScriptDir
$WebDir = Join-Path $RepoRoot "apps\web"

Set-Location $WebDir
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  PRISM Next.js Frontend (Port 3000)                        " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Working Directory: $WebDir" -ForegroundColor Gray
Write-Host "Command:           npm run dev" -ForegroundColor Gray
Write-Host ""

npm run dev
