@echo off
REM ============================================================
REM AiCoach Windows Task Scheduler Setup
REM Creates a daily scheduled task to sync Garmin data
REM ============================================================

REM Paths are derived from this script's location so it works on any machine.
set TASK_NAME=AiCoach_GarminSync
set PROJECT_DIR=%~dp0..
set PYTHON_EXE=%PROJECT_DIR%\venv\Scripts\python.exe
set SCRIPT_PATH=%PROJECT_DIR%\scripts\run_sync.py

REM Default run time: 6:00 AM daily
set RUN_TIME=06:00

echo ============================================================
echo AiCoach - Windows Task Scheduler Setup
echo ============================================================
echo.
echo Task Name: %TASK_NAME%
echo Script: %SCRIPT_PATH%
echo Python: %PYTHON_EXE%
echo Schedule: Daily at %RUN_TIME%
echo.

REM Check if task already exists
schtasks /query /tn "%TASK_NAME%" >nul 2>&1
if %errorlevel%==0 (
    echo Task already exists. Deleting old task...
    schtasks /delete /tn "%TASK_NAME%" /f
)

REM Create the scheduled task
echo Creating scheduled task...
schtasks /create ^
    /tn "%TASK_NAME%" ^
    /tr "\"%PYTHON_EXE%\" \"%SCRIPT_PATH%\" --latest --briefing" ^
    /sc daily ^
    /st %RUN_TIME% ^
    /rl highest ^
    /f

if %errorlevel%==0 (
    echo.
    echo ============================================================
    echo SUCCESS! Task created.
    echo.
    echo The task will run daily at %RUN_TIME% and:
    echo   1. Sync latest data from Garmin Connect
    echo   2. Generate athlete_profile.md
    echo   3. Generate coach_briefing.md
    echo.
    echo To run manually: schtasks /run /tn "%TASK_NAME%"
    echo To delete:       schtasks /delete /tn "%TASK_NAME%" /f
    echo To view:         schtasks /query /tn "%TASK_NAME%" /v
    echo ============================================================
) else (
    echo.
    echo ERROR: Failed to create task.
    echo Try running this script as Administrator.
)

pause
