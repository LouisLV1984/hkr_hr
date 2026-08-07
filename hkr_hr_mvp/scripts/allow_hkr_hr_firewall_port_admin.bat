@echo off
setlocal

set "ROOT=D:\HKR_HR"
set "PORT=5000"

echo This will request Administrator permission to allow HKR HR web access on TCP %PORT%.
echo Fixed URL: http://192.168.128.70:%PORT%/login
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File ""%ROOT%\scripts\allow_hkr_hr_firewall_port.ps1"" -Port %PORT%'"
if errorlevel 1 goto failed

echo.
echo Permission request sent. Confirm the Windows UAC prompt on the mini PC.
pause
exit /b 0

:failed
echo.
echo ERROR: Failed to request Administrator permission.
pause
exit /b 1
