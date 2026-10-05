[CmdletBinding()]
param(
    [switch]$NoBrowser
)

$TargetScript = Join-Path $PSScriptRoot "scripts\start-prism.ps1"
if ($NoBrowser) {
    & $TargetScript -NoBrowser
} else {
    & $TargetScript
}
