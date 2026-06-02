#!/usr/bin/env python3
"""
Main sync script for AiCoach.
Downloads health and activity data from Garmin Connect including FIT files.

Usage:
    python run_sync.py --initial    # First-time full download
    python run_sync.py --latest     # Incremental update (daily use)
    python run_sync.py --all        # Re-download everything
    python run_sync.py --stats      # Show statistics
"""

import argparse
import shutil
import subprocess
import sys
import logging
from datetime import datetime, date, timedelta
from pathlib import Path

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
LOG_DIR = PROJECT_ROOT / "logs"
ARCHIVE_DIR = PROJECT_ROOT / "coach" / "archive"
LOG_DIR.mkdir(exist_ok=True)

# Data retention settings
KEEP_LOGS_DAYS = 30
KEEP_ARCHIVES_DAYS = 30

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / f"sync_{datetime.now().strftime('%Y%m%d')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def find_garmindb_cli() -> Path:
    """Locate the garmindb_cli.py installed by the garmindb package.

    The garmindb package installs its scripts next to the active Python
    interpreter (venv/Scripts on Windows, venv/bin on POSIX). Fall back to
    PATH in case it was installed elsewhere.
    """
    candidates = [
        Path(sys.executable).parent / "garmindb_cli.py",
        Path(sys.executable).parent / "garmindb_cli",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate

    for name in ("garmindb_cli.py", "garmindb_cli"):
        found = shutil.which(name)
        if found:
            return Path(found)

    raise FileNotFoundError(
        "Could not find garmindb_cli. Install dependencies with:\n"
        "  pip install -r requirements.txt"
    )


def run_garmindb_cli(args: list) -> bool:
    """Run the GarminDB CLI with given arguments."""
    try:
        cli_script = find_garmindb_cli()
    except FileNotFoundError as e:
        logger.error(str(e))
        return False

    python_exe = sys.executable
    cmd = [python_exe, str(cli_script)] + args
    logger.info(f"Running: {' '.join(cmd)}")

    try:
        subprocess.run(
            cmd,
            capture_output=False,
            text=True,
            check=True,
            cwd=str(PROJECT_ROOT)
        )
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed with exit code {e.returncode}")
        return False
    except Exception as e:
        logger.error(f"Error running command: {e}")
        return False


def sync_initial():
    """Perform initial full download of all data including FIT files."""
    logger.info("=" * 60)
    logger.info("Starting INITIAL sync - Full data download with FIT files")
    logger.info("This may take a while...")
    logger.info("=" * 60)
    
    # Step 1: Download all data
    logger.info("Step 1/3: Downloading data from Garmin Connect...")
    success = run_garmindb_cli([
        "--all",
        "--download"
    ])
    if not success:
        logger.error("Download failed")
        return False
    
    # Step 2: Import all data including FIT records
    logger.info("Step 2/3: Importing data into database...")
    success = run_garmindb_cli([
        "--all",
        "--import"
    ])
    if not success:
        logger.error("Import failed")
        return False
    
    # Step 3: Analyze
    logger.info("Step 3/3: Analyzing data...")
    success = run_garmindb_cli([
        "--analyze"
    ])
    
    if success:
        cleanup_old_files()
        logger.info("=" * 60)
        logger.info("Initial sync completed successfully!")
        show_stats()
        logger.info("=" * 60)
    else:
        logger.error("Sync failed. Check logs for details.")
    
    return success


def fetch_recent_data(days=7):
    """Fetch recent data dynamically - rolling window of last N days."""
    logger.info(f"Fetching recent data (last {days} days)...")
    
    try:
        from garmindb.download import Download
        from garmindb.garmin_connect_config_manager import GarminConnectConfigManager
        
        gc = GarminConnectConfigManager()
        dl = Download(gc)
        dl.login()
        
        # Calculate start date (N days ago)
        start_date = date.today() - timedelta(days=days-1)
        
        sleep_dir = DATA_DIR / "Sleep"
        rhr_dir = DATA_DIR / "RHR"
        weight_dir = DATA_DIR / "Weight"
        monitoring_dir = DATA_DIR / "FitFiles" / "Monitoring"
        
        # Ensure directories exist
        sleep_dir.mkdir(parents=True, exist_ok=True)
        rhr_dir.mkdir(parents=True, exist_ok=True)
        weight_dir.mkdir(parents=True, exist_ok=True)
        
        # Fetch sleep (rolling window)
        logger.info(f"  Fetching sleep ({start_date} to today)...")
        dl.get_sleep(str(sleep_dir), start_date, days, overwrite=True)
        
        # Fetch RHR (rolling window)
        logger.info(f"  Fetching RHR ({start_date} to today)...")
        dl.get_rhr(str(rhr_dir), start_date, days, overwrite=True)
        
        # Fetch weight (rolling window)
        logger.info(f"  Fetching weight ({start_date} to today)...")
        dl.get_weight(str(weight_dir), start_date, days, overwrite=True)
        
        # Fetch daily summaries (rolling window)
        logger.info(f"  Fetching daily summaries ({start_date} to today)...")
        dl.get_daily_summaries(lambda y: str(monitoring_dir / str(y)), start_date, days, overwrite=True)
        
        logger.info("Recent data fetched successfully!")
        return True
        
    except Exception as e:
        logger.error(f"Failed to fetch recent data: {e}")
        import traceback
        traceback.print_exc()
        return False


def sync_latest():
    """Perform incremental sync of latest data."""
    logger.info("=" * 60)
    logger.info(f"Starting INCREMENTAL sync - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    logger.info("=" * 60)
    
    # Download, import, analyze latest
    success = run_garmindb_cli([
        "--all",
        "--download",
        "--import",
        "--analyze",
        "--latest"
    ])
    
    if success:
        # Fetch recent data with rolling window (last 7 days)
        fetch_recent_data(days=7)
        # Cleanup old files to prevent bloat
        cleanup_old_files()
        logger.info("Incremental sync completed!")
    else:
        logger.error("Sync failed. Check logs.")
    
    return success


def sync_all():
    """Re-download all data with overwrite."""
    logger.info("=" * 60)
    logger.info("Starting FULL RE-SYNC with overwrite")
    logger.info("This will re-download all FIT files...")
    logger.info("=" * 60)
    
    # Download with overwrite to get all FIT files
    success = run_garmindb_cli([
        "--all",
        "--download",
        "--overwrite"
    ])
    if not success:
        return False
    
    # Import everything
    success = run_garmindb_cli([
        "--all",
        "--import"
    ])
    if not success:
        return False
    
    # Analyze
    success = run_garmindb_cli([
        "--analyze"
    ])
    
    if success:
        cleanup_old_files()
        logger.info("Full re-sync completed!")
        show_stats()
    
    return success


def show_stats():
    """Show database and FIT file statistics."""
    logger.info("")
    logger.info("=== Data Statistics ===")
    
    if not DATA_DIR.exists():
        logger.info("No data downloaded yet.")
        return
    
    # Database files
    db_dir = DATA_DIR / "DBs"
    if db_dir.exists():
        logger.info("Databases:")
        db_files = list(db_dir.glob("*.db"))
        for db_file in db_files:
            size_mb = db_file.stat().st_size / (1024 * 1024)
            logger.info(f"  {db_file.name}: {size_mb:.2f} MB")
    
    # FIT files
    fit_dir = DATA_DIR / "FitFiles" / "Activities"
    if fit_dir.exists():
        fit_files = list(fit_dir.glob("*.fit"))
        json_files = list(fit_dir.glob("*.json"))
        logger.info(f"Activity files: {len(fit_files)} FIT, {len(json_files)} JSON")
    
    # Activity count from DB
    import sqlite3
    db_path = db_dir / "garmin_activities.db"
    if db_path.exists():
        conn = sqlite3.connect(db_path)
        total_activities = conn.execute("SELECT COUNT(*) FROM activities").fetchone()[0]
        running = conn.execute("SELECT COUNT(*) FROM activities WHERE sport='running'").fetchone()[0]
        records = conn.execute("SELECT COUNT(*) FROM activity_records").fetchone()[0]
        conn.close()
        logger.info(f"Activities: {total_activities} total, {running} runs")
        logger.info(f"Activity records (HR data points): {records}")


def cleanup_old_files():
    """Remove old log files and archived briefings to prevent folder bloat."""
    cutoff_date = datetime.now() - timedelta(days=KEEP_LOGS_DAYS)
    removed_count = 0
    
    # Cleanup old log files
    if LOG_DIR.exists():
        for log_file in LOG_DIR.glob("sync_*.log"):
            try:
                file_date = datetime.fromtimestamp(log_file.stat().st_mtime)
                if file_date < cutoff_date:
                    log_file.unlink()
                    removed_count += 1
            except Exception:
                pass
    
    # Cleanup old archived briefings
    if ARCHIVE_DIR.exists():
        archive_cutoff = datetime.now() - timedelta(days=KEEP_ARCHIVES_DAYS)
        for archive_file in ARCHIVE_DIR.glob("coach_briefing_*.md"):
            try:
                file_date = datetime.fromtimestamp(archive_file.stat().st_mtime)
                if file_date < archive_cutoff:
                    archive_file.unlink()
                    removed_count += 1
            except Exception:
                pass
    
    if removed_count > 0:
        logger.info(f"Cleaned up {removed_count} old files (logs/archives older than {KEEP_LOGS_DAYS} days)")


def generate_profile():
    """Generate the athlete profile."""
    profile_script = PROJECT_ROOT / "scripts" / "generate_athlete_profile.py"
    if profile_script.exists():
        logger.info("Generating athlete profile...")
        subprocess.run([sys.executable, str(profile_script)], cwd=str(PROJECT_ROOT))


def generate_briefing():
    """Generate the coach briefing."""
    briefing_script = PROJECT_ROOT / "scripts" / "generate_briefing.py"
    if briefing_script.exists():
        logger.info("Generating coach briefing...")
        subprocess.run([sys.executable, str(briefing_script)], cwd=str(PROJECT_ROOT))


def main():
    parser = argparse.ArgumentParser(
        description="AiCoach Garmin Data Sync",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_sync.py --initial    # First time setup
  python run_sync.py --latest     # Daily sync
  python run_sync.py --all        # Force re-download everything
        """
    )
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--initial", action="store_true",
                       help="First-time full download")
    group.add_argument("--latest", action="store_true",
                       help="Incremental update (daily use)")
    group.add_argument("--all", action="store_true",
                       help="Re-download everything with overwrite")
    group.add_argument("--stats", action="store_true",
                       help="Show database statistics")
    
    parser.add_argument("--briefing", action="store_true",
                        help="Generate coach briefing after sync")
    parser.add_argument("--profile", action="store_true",
                        help="Generate athlete profile after sync")
    
    args = parser.parse_args()
    
    if args.initial:
        success = sync_initial()
    elif args.latest:
        success = sync_latest()
    elif args.all:
        success = sync_all()
    elif args.stats:
        show_stats()
        success = True
    else:
        parser.print_help()
        success = False
    
    if success:
        if args.profile:
            generate_profile()
        if args.briefing:
            generate_briefing()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
