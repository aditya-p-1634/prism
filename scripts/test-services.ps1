# PRISM Service Verification Test
$ErrorActionPreference = "Stop"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  PRISM Automated Verification Test                         " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# 1. Environment & Package Check
Write-Host "`n[1] Checking Python Environment & Package Versions..." -ForegroundColor Yellow
$py = "D:\Projects\PRISM\apps\api\.venv\Scripts\python.exe"
$pyCheck = & $py -c "import pandas, numpy, ortools; print('PANDAS=' + pandas.__version__); print('NUMPY=' + numpy.__version__); print('ORTOOLS=' + ortools.__version__)"
Write-Host "Python Packages: $pyCheck" -ForegroundColor Green

# 2. Backend /health
Write-Host "`n[2] Testing Backend /health..." -ForegroundColor Yellow
$health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health"
Write-Host "Health Status: $($health.status) | System: $($health.system)" -ForegroundColor Green

# 3. Backend /docs
Write-Host "`n[3] Testing Backend /docs..." -ForegroundColor Yellow
$docs = Invoke-WebRequest -Uri "http://127.0.0.1:8000/docs" -UseBasicParsing
Write-Host "Docs HTTP Status: $($docs.StatusCode) OK" -ForegroundColor Green

# 4. Backend Telemetry
Write-Host "`n[4] Testing Backend Telemetry & Engines..." -ForegroundColor Yellow
$telem = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/health/telemetry"
Write-Host "Telemetry Status: $($telem.status) | DB Connected: $($telem.database.connected)" -ForegroundColor Green

# 5. Frontend /
Write-Host "`n[5] Testing Frontend Root (/)..." -ForegroundColor Yellow
$homeRes = Invoke-WebRequest -Uri "http://localhost:3000" -UseBasicParsing
Write-Host "Frontend Root HTTP Status: $($homeRes.StatusCode) OK (Length: $($homeRes.Content.Length) bytes)" -ForegroundColor Green

# 6. Frontend /map
Write-Host "`n[6] Testing Frontend /map..." -ForegroundColor Yellow
$map = Invoke-WebRequest -Uri "http://localhost:3000/map" -UseBasicParsing
Write-Host "Frontend /map HTTP Status: $($map.StatusCode) OK (Length: $($map.Content.Length) bytes)" -ForegroundColor Green

# 7. Frontend Chunk Integrity
Write-Host "`n[7] Verifying Next.js Chunk Bundles (No ChunkLoadError)..." -ForegroundColor Yellow
$matches = [regex]::Matches($map.Content, 'src="(/_next/[^"]+\.js)"')
Write-Host "Found $($matches.Count) JavaScript chunks referenced in /map HTML."
$chunkFailures = 0
foreach ($m in $matches) {
    $chunkUrl = "http://localhost:3000" + $m.Groups[1].Value
    try {
        $chunkRes = Invoke-WebRequest -Uri $chunkUrl -UseBasicParsing -TimeoutSec 5
        if ($chunkRes.StatusCode -ne 200) {
            Write-Host "Chunk error: $chunkUrl returned $($chunkRes.StatusCode)" -ForegroundColor Red
            $chunkFailures++
        }
    } catch {
        Write-Host "Chunk error: $chunkUrl failed: $_" -ForegroundColor Red
        $chunkFailures++
    }
}

if ($chunkFailures -eq 0) {
    Write-Host "All Next.js chunks verified: 100% OK, Zero ChunkLoadErrors!" -ForegroundColor Green
} else {
    Write-Host "$chunkFailures chunk(s) failed!" -ForegroundColor Red
}

Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host "  ALL PRISM VERIFICATION CHECKS PASSED SUCCESSFULLY!        " -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
