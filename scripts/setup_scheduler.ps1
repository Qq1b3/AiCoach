# PowerShell script to set up Windows Task Scheduler for automated Garmin sync
# Run this script as Administrator to create scheduled tasks

# Derive all paths from this script's location (scripts/ -> project root)
# so it works on any machine without editing.
$ProjectPath = Split-Path -Parent $PSScriptRoot
$PythonPath = Join-Path $ProjectPath "venv\Scripts\python.exe"
$SyncScript = Join-Path $ProjectPath "scripts\run_sync.py"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  AiCoach - Setting up Scheduled Sync Tasks" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Check if running as admin
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "ERROR: This script must be run as Administrator!" -ForegroundColor Red
    Write-Host "Right-click PowerShell and select 'Run as Administrator'" -ForegroundColor Yellow
    exit 1
}

# Verify paths exist
if (-not (Test-Path $PythonPath)) {
    Write-Host "ERROR: Python not found at $PythonPath" -ForegroundColor Red
    Write-Host "Make sure you've created the virtual environment first." -ForegroundColor Yellow
    exit 1
}

if (-not (Test-Path $SyncScript)) {
    Write-Host "ERROR: Sync script not found at $SyncScript" -ForegroundColor Red
    exit 1
}

Write-Host "Creating scheduled tasks for Garmin data sync..." -ForegroundColor Green
Write-Host ""

# Task 1: Morning Sync at 6:00 AM
$TaskName1 = "AiCoach-MorningSync"
$Action1 = New-ScheduledTaskAction -Execute $PythonPath -Argument "$SyncScript --latest" -WorkingDirectory $ProjectPath
$Trigger1 = New-ScheduledTaskTrigger -Daily -At 6:00AM
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

try {
    Unregister-ScheduledTask -TaskName $TaskName1 -Confirm:$false -ErrorAction SilentlyContinue
    Register-ScheduledTask -TaskName $TaskName1 -Action $Action1 -Trigger $Trigger1 -Settings $Settings -Description "AiCoach morning Garmin sync - captures overnight sleep data"
    Write-Host "  [OK] Created: $TaskName1 (6:00 AM)" -ForegroundColor Green
} catch {
    Write-Host "  [FAIL] $TaskName1 : $_" -ForegroundColor Red
}

# Task 2: Afternoon Sync at 2:00 PM
$TaskName2 = "AiCoach-AfternoonSync"
$Action2 = New-ScheduledTaskAction -Execute $PythonPath -Argument "$SyncScript --latest" -WorkingDirectory $ProjectPath
$Trigger2 = New-ScheduledTaskTrigger -Daily -At 2:00PM

try {
    Unregister-ScheduledTask -TaskName $TaskName2 -Confirm:$false -ErrorAction SilentlyContinue
    Register-ScheduledTask -TaskName $TaskName2 -Action $Action2 -Trigger $Trigger2 -Settings $Settings -Description "AiCoach afternoon Garmin sync - captures morning activities"
    Write-Host "  [OK] Created: $TaskName2 (2:00 PM)" -ForegroundColor Green
} catch {
    Write-Host "  [FAIL] $TaskName2 : $_" -ForegroundColor Red
}

# Task 3: Evening Sync at 9:00 PM
$TaskName3 = "AiCoach-EveningSync"
$Action3 = New-ScheduledTaskAction -Execute $PythonPath -Argument "$SyncScript --latest" -WorkingDirectory $ProjectPath
$Trigger3 = New-ScheduledTaskTrigger -Daily -At 9:00PM

try {
    Unregister-ScheduledTask -TaskName $TaskName3 -Confirm:$false -ErrorAction SilentlyContinue
    Register-ScheduledTask -TaskName $TaskName3 -Action $Action3 -Trigger $Trigger3 -Settings $Settings -Description "AiCoach evening Garmin sync - captures full day's data"
    Write-Host "  [OK] Created: $TaskName3 (9:00 PM)" -ForegroundColor Green
} catch {
    Write-Host "  [FAIL] $TaskName3 : $_" -ForegroundColor Red
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Setup Complete!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Scheduled syncs:"
Write-Host "  - 6:00 AM  : Morning sync (sleep data)" -ForegroundColor Yellow
Write-Host "  - 2:00 PM  : Afternoon sync (morning activities)" -ForegroundColor Yellow
Write-Host "  - 9:00 PM  : Evening sync (full day)" -ForegroundColor Yellow
Write-Host ""
Write-Host "To view/edit tasks, open Task Scheduler and look for 'AiCoach-*' tasks"
Write-Host ""
Write-Host "To remove all tasks, run:" -ForegroundColor Gray
Write-Host "  Unregister-ScheduledTask -TaskName 'AiCoach-*' -Confirm:`$false" -ForegroundColor Gray
