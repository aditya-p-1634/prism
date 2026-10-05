@echo off
REM PRISM Single Command Launcher (Windows Batch wrapper)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-prism.ps1" %*
