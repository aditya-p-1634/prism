[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$ApiDir = Join-Path $RepoRoot "apps\api"
$WebDir = Join-Path $RepoRoot "apps\web"

Write-Host "Running PRISM final research verification..." -ForegroundColor Cyan
Push-Location $ApiDir
try {
    $env:PYTHONPATH = "."
    python -m compileall -q app
    if ($LASTEXITCODE -ne 0) { throw "Python compilation failed." }
    pytest tests/test_phase14_asset_audit.py tests/test_phase15_telemetry_normalization.py tests/test_phase16_real_evaluation.py tests/test_phase17_spatial_event_evidence.py tests/test_phase18_research_evidence_endpoint.py -q
    if ($LASTEXITCODE -ne 0) { throw "Research regression tests failed." }
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

Write-Host "PRISM final research verification passed." -ForegroundColor Green
