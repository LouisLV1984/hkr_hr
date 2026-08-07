@echo off
setlocal

set "ROOT=D:\HKR_HR"
set "USERNAME=admin"
set "RESET_FLAG="
set "CHECK_ONLY="
set "NO_PAUSE="

:parse_args
if "%~1"=="" goto args_done
if /I "%~1"=="--reset" set "RESET_FLAG=-Reset"
if /I "%~1"=="--check" set "CHECK_ONLY=1"
if /I "%~1"=="--no-pause" set "NO_PAUSE=1"
shift
goto parse_args

:args_done

echo HKR HR Operating Console - initialize production database
echo Root: %ROOT%
echo Database: PostgreSQL local hkr_hr_db
echo Admin: %USERNAME%
echo.

if defined CHECK_ONLY (
    echo Check mode only. No command will be executed.
    echo Admin password source: HKR_HR_ADMIN_PASSWORD environment variable
    echo powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\scripts\init_hkr_hr_database.ps1" -Root "%ROOT%" -Username "%USERNAME%" -ResetAdminPassword %RESET_FLAG%
    exit /b 0
)

if not defined HKR_HR_ADMIN_PASSWORD (
    echo ERROR: HKR_HR_ADMIN_PASSWORD is not set in this process environment.
    echo Set it only for this initialization or password-reset operation, then retry.
    if not defined NO_PAUSE pause
    exit /b 1
)

if not exist "%ROOT%\scripts\init_hkr_hr_database.ps1" (
    echo ERROR: Cannot find "%ROOT%\scripts\init_hkr_hr_database.ps1"
    echo Please confirm the HR app scripts have been deployed to the mini PC root.
    if not defined NO_PAUSE pause
    exit /b 1
)

cd /d "%ROOT%" || (
    echo ERROR: Cannot enter "%ROOT%"
    if not defined NO_PAUSE pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\scripts\init_hkr_hr_database.ps1" -Root "%ROOT%" -Username "%USERNAME%" -ResetAdminPassword %RESET_FLAG%
if errorlevel 1 goto failed

echo.
echo Done. You can now restart/open HKR HR:
echo %ROOT%\scripts\mini_pc_restart_hkr_hr_app.bat
echo http://192.168.128.70:5000/login
if not defined NO_PAUSE pause
exit /b 0

:failed
echo.
echo ERROR: Database initialization failed. Please check the message above.
if not defined NO_PAUSE pause
exit /b 1
