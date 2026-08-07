@echo off
setlocal

set "ROOT=D:\HKR_HR"
set "CONFIRM="

if /I "%~1"=="--check" (
    echo Check mode only. No database or service changes will be made.
    echo One-time V1 database rebuild:
    echo   call "%ROOT%\scripts\mini_pc_init_hkr_hr_database.bat" --reset --no-pause
    echo Normal restart after rebuild:
    echo   call "%ROOT%\scripts\mini_pc_restart_hkr_hr_app.bat" --no-pause
    exit /b 0
)

echo HKR HR V1 - one-time database rebuild and restart
echo.
echo WARNING:
echo   This will permanently delete the OLD TEST DATA in PostgreSQL hkr_hr_db.
echo   It will not touch TMC or any other database.
echo   Do not use this file for normal future restarts.
echo.
set /p "CONFIRM=Type RESET and press Enter to continue: "
if /I not "%CONFIRM%"=="RESET" (
    echo Cancelled. No changes were made.
    pause
    exit /b 2
)

if not exist "%ROOT%\scripts\mini_pc_init_hkr_hr_database.bat" (
    echo ERROR: Database initialization file is missing.
    pause
    exit /b 1
)
if not exist "%ROOT%\scripts\mini_pc_restart_hkr_hr_app.bat" (
    echo ERROR: Restart file is missing.
    pause
    exit /b 1
)

call "%ROOT%\scripts\mini_pc_init_hkr_hr_database.bat" --reset --no-pause
if errorlevel 1 goto failed

call "%ROOT%\scripts\mini_pc_restart_hkr_hr_app.bat" --no-pause
if errorlevel 1 goto failed

echo.
echo HKR HR V1 database rebuild and restart completed.
echo Future restarts only need:
echo   %ROOT%\scripts\mini_pc_restart_hkr_hr_app.bat
pause
exit /b 0

:failed
echo.
echo ERROR: HKR HR V1 rebuild or restart failed.
echo Review:
echo   %ROOT%\03.Output\logs\hkr_hr_app.err.log
pause
exit /b 1
