@echo off
:: ============================================
:: SDIT Auto Start Script
:: Using Windows Terminal (wt.exe) for better UI
:: ============================================

chcp 65001 >nul 2>&1

echo ========================================
echo   SDIT Auto Start
echo ========================================
echo.

:: Check if Windows Terminal is available
where wt >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    :: Use Windows Terminal with PowerShell 7
    wt -w 0 pwsh.exe -ExecutionPolicy Bypass -File "%~dp0start.ps1"
) else (
    :: Fallback to PowerShell 7 window
    pwsh -ExecutionPolicy Bypass -File "%~dp0start.ps1"
)
