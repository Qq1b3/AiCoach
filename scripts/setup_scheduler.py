#!/usr/bin/env python3
"""
Windows Task Scheduler Setup for AiCoach

Creates a scheduled task that runs daily to:
1. Sync Garmin data (run_sync.py --latest)
2. Generate athlete_profile.md
3. Generate coach_briefing.md

Run as Administrator for best results.
"""

import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent
TASK_NAME = "AiCoach_GarminSync"

# Detect Python environment
PYTHON_EXE = sys.executable
SCRIPT_PATH = PROJECT_DIR / "scripts" / "run_sync.py"

# Default schedule
DEFAULT_TIME = "06:00"


def create_task(run_time: str = DEFAULT_TIME):
    """Create the Windows scheduled task."""
    
    # Command to run
    command = f'"{PYTHON_EXE}" "{SCRIPT_PATH}" --latest --profile --briefing'
    
    print("=" * 60)
    print("AiCoach - Windows Task Scheduler Setup")
    print("=" * 60)
    print(f"Task Name: {TASK_NAME}")
    print(f"Python: {PYTHON_EXE}")
    print(f"Script: {SCRIPT_PATH}")
    print(f"Schedule: Daily at {run_time}")
    print(f"Command: {command}")
    print()
    
    # Delete existing task if present
    result = subprocess.run(
        ["schtasks", "/query", "/tn", TASK_NAME],
        capture_output=True
    )
    if result.returncode == 0:
        print("Existing task found. Deleting...")
        subprocess.run(
            ["schtasks", "/delete", "/tn", TASK_NAME, "/f"],
            capture_output=True
        )
    
    # Create new task
    print("Creating scheduled task...")
    result = subprocess.run([
        "schtasks", "/create",
        "/tn", TASK_NAME,
        "/tr", command,
        "/sc", "daily",
        "/st", run_time,
        "/rl", "highest",
        "/f"
    ], capture_output=True, text=True)
    
    if result.returncode == 0:
        print()
        print("=" * 60)
        print("SUCCESS! Task created.")
        print()
        print(f"The task will run daily at {run_time} and:")
        print("  1. Sync latest data from Garmin Connect")
        print("  2. Generate athlete_profile.md")
        print("  3. Generate coach_briefing.md")
        print()
        print(f'To run manually: schtasks /run /tn "{TASK_NAME}"')
        print(f'To delete:       schtasks /delete /tn "{TASK_NAME}" /f')
        print(f'To view:         schtasks /query /tn "{TASK_NAME}" /v')
        print("=" * 60)
        return True
    else:
        print()
        print("ERROR: Failed to create task.")
        print(result.stderr)
        print("Try running this script as Administrator.")
        return False


def delete_task():
    """Delete the scheduled task."""
    result = subprocess.run(
        ["schtasks", "/delete", "/tn", TASK_NAME, "/f"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        print(f"Task '{TASK_NAME}' deleted successfully.")
    else:
        print(f"Failed to delete task: {result.stderr}")


def run_task():
    """Manually trigger the scheduled task."""
    result = subprocess.run(
        ["schtasks", "/run", "/tn", TASK_NAME],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        print(f"Task '{TASK_NAME}' started.")
    else:
        print(f"Failed to run task: {result.stderr}")


def show_status():
    """Show task status."""
    result = subprocess.run(
        ["schtasks", "/query", "/tn", TASK_NAME, "/v", "/fo", "list"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        print(result.stdout)
    else:
        print(f"Task '{TASK_NAME}' not found.")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="AiCoach Task Scheduler Setup")
    parser.add_argument("--create", action="store_true", help="Create the scheduled task")
    parser.add_argument("--delete", action="store_true", help="Delete the scheduled task")
    parser.add_argument("--run", action="store_true", help="Run the task now")
    parser.add_argument("--status", action="store_true", help="Show task status")
    parser.add_argument("--time", default=DEFAULT_TIME, help=f"Time to run (default: {DEFAULT_TIME})")
    
    args = parser.parse_args()
    
    if args.create:
        create_task(args.time)
    elif args.delete:
        delete_task()
    elif args.run:
        run_task()
    elif args.status:
        show_status()
    else:
        parser.print_help()
        print()
        print("Example: python setup_scheduler.py --create --time 07:00")
