[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$ApiDir = Join-Path $RepoRoot "apps\api"
$WebDir = Join-Path $RepoRoot "apps\web"

Write-Host "Running PRISM release verification..." -ForegroundColor Cyan
Push-Location $ApiDir
try {
    $env:PYTHONPATH = "."
    python -m compileall -q app
    if ($LASTEXITCODE -ne 0) { throw "Python compilation failed." }
    pytest tests/test_phase10_validation.py tests/test_phase11_routing_assistance.py tests/test_phase12_field_feedback.py tests/test_operator_briefing.py tests/test_faculty_loophole_hardening.py -q
    if ($LASTEXITCODE -ne 0) { throw "Backend focused tests failed." }
} finally {
    Pop-Location
}

Push-Location $WebDir
try {
    npx tsc --noEmit
    if ($LASTEXITCODE -ne 0) { throw "Frontend typecheck failed." }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "Frontend production build failed." }
} finally {
    Pop-Location
}

Write-Host "PRISM release verification passed." -ForegroundColor Green
