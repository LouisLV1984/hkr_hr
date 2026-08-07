@echo off
setlocal

set "ROOT=D:\HKR_HR"
set "PORT=5000"
set "FIXED_URL=http://192.168.128.70:5000/login"
set "CHECK_ONLY="
set "NO_PAUSE="

:parse_args
if "%~1"=="" goto args_done
if /I "%~1"=="--check" set "CHECK_ONLY=1"
if /I "%~1"=="--no-pause" set "NO_PAUSE=1"
shift
goto parse_args

:args_done

echo HKR HR Operating Console - setup venv and restart web app
echo Root: %ROOT%
echo Port: %PORT%
echo Database: PostgreSQL local hkr_hr_db
echo Fixed URL: %FIXED_URL%
echo.

if defined CHECK_ONLY (
    echo Check mode only. No command will be executed.
    echo App root: "%ROOT%\_system\app"
    echo Venv:     "%ROOT%\_system\.venv"
    echo Logs:     "%ROOT%\03.Output\logs"
    echo powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\scripts\setup_system_venv.ps1" -Root "%ROOT%"
    echo powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\scripts\init_hkr_hr_database.ps1" -Root "%ROOT%" -Username "admin" -Password "[configured]"
    echo powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\scripts\stop_hkr_hr_app.ps1" -Port %PORT% -Root "%ROOT%"
    echo powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\scripts\start_hkr_hr_app.ps1" -Port %PORT% -Root "%ROOT%"
    echo powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\scripts\status_hkr_hr_app.ps1" -Port %PORT% -Root "%ROOT%"
    exit /b 0
)

if not exist "%ROOT%\scripts\setup_system_venv.ps1" (
    echo ERROR: Cannot find "%ROOT%\scripts\setup_system_venv.ps1"
    echo Please confirm the HR app scripts have been deployed to the mini PC root.
    pause
    exit /b 1
)

cd /d "%ROOT%" || (
    echo ERROR: Cannot enter "%ROOT%"
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\scripts\setup_system_venv.ps1" -Root "%ROOT%"
if errorlevel 1 goto failed

powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\scripts\init_hkr_hr_database.ps1" -Root "%ROOT%" -Username "admin"
if %ERRORLEVEL% EQU 20 goto schema_upgrade_required
if errorlevel 1 goto failed

powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\scripts\stop_hkr_hr_app.ps1" -Port %PORT% -Root "%ROOT%"
if errorlevel 1 goto failed

powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\scripts\start_hkr_hr_app.ps1" -Port %PORT% -Root "%ROOT%"
if errorlevel 1 goto failed

powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\scripts\status_hkr_hr_app.ps1" -Port %PORT% -Root "%ROOT%"
if errorlevel 1 goto failed

echo.
echo Done. HR web app should be available on:
echo http://127.0.0.1:%PORT%
echo http://%COMPUTERNAME%:%PORT%
echo %FIXED_URL%
if not defined NO_PAUSE pause
exit /b 0

:schema_upgrade_required
echo.
echo ERROR: This mini PC still has the old HKR HR test database schema.
echo Run this one-time upgrade file:
echo %ROOT%\scripts\mini_pc_upgrade_hkr_hr_v1_and_restart.bat
echo.
echo Normal restart does not delete or reset the database automatically.
if not defined NO_PAUSE pause
exit /b 20

:failed
echo.
echo ERROR: Restart failed. Please check the message above and logs:
echo %ROOT%\03.Output\logs\hkr_hr_app.err.log
if not defined NO_PAUSE pause
exit /b 1
