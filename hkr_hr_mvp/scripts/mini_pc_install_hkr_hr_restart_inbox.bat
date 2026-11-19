@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_hkr_hr_restart_inbox.ps1"
set "RESULT=%ERRORLEVEL%"
if not "%RESULT%"=="0" echo HKR HR restart inbox installation failed. Keep this window open for the error above.
pause
exit /b %RESULT%
