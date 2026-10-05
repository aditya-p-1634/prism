<#
.SYNOPSIS
    PRISM - Emergency Stop Script
.DESCRIPTION
    Safely terminates PRISM backend (8000) and frontend (3000) servers.
#>

[CmdletBinding()]
param()

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "          PRISM SHUTDOWN                " -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

function Stop-PrismPort([int]$Port) {
    $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($connections) {
        $pids = $connections | Select-Object -ExpandProperty OwningProcess -Unique
        foreach ($p in $pids) {
            if ($p -le 4) { continue }
            $proc = Get-Process -Id $p -ErrorAction SilentlyContinue
            $name = if ($proc) { $proc.ProcessName } else { "unknown" }
            Write-Host "Stopping process on port $Port (PID: $p, Name: $name)..." -ForegroundColor Yellow
            try {
                & taskkill.exe /PID $p /T /F 2>&1 | Out-Null
            } catch {
                Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
            }
        }
    } else {
        Write-Host "Port $Port is not currently in use." -ForegroundColor Gray
    }
}

Stop-PrismPort 8000
Stop-PrismPort 3000
Stop-PrismPort 3001

Write-Host "PRISM services stopped cleanly." -ForegroundColor Green
