#!/usr/bin/env python3
"""
Setup script to configure Garmin Connect credentials.
Run this once to set up your Garmin Connect configuration.
"""

import json
import os
import sys
import shutil
from pathlib import Path
from getpass import getpass

import keyring


def get_garmin_db_config_path() -> Path:
    """Get the path to the GarminDB config directory."""
    return Path.home() / ".GarminDb"


def get_config_file_path() -> Path:
    """Get the path to the config file."""
    return get_garmin_db_config_path() / "GarminConnectConfig.json"


def setup_config():
    """Interactive setup for Garmin Connect configuration."""
    config_dir = get_garmin_db_config_path()
    config_file = get_config_file_path()
    template_file = Path(__file__).parent.parent / "config" / "GarminConnectConfig.json.template"
    
    print("=" * 60)
    print("AiCoach - Garmin Connect Setup")
    print("=" * 60)
    print()
    
    # Check if config already exists
    if config_file.exists():
        response = input("WARNING: Config file already exists. Overwrite? (y/N): ").strip().lower()
        if response != 'y':
            print("Setup cancelled.")
            return
    
    # Ensure config directory exists
    config_dir.mkdir(parents=True, exist_ok=True)
    
    # Load template
    with open(template_file, 'r') as f:
        config = json.load(f)
    
    # Get user credentials
    print("\nEnter your Garmin Connect credentials:")
    print("(These are stored locally and never shared)")
    print()
    
    email = input("   Email: ").strip()
    password = getpass("   Password: ")
    
    config["credentials"]["user"] = email
    config["credentials"]["secure_password"] = True
    config["credentials"]["password"] = ""

    # Store password securely in OS credential store
    try:
        keyring.set_password("GarminConnect", email, password)
        print("   Password stored in OS credential manager.")
    except Exception as e:
        print(f"   ERROR: Failed to store password securely: {e}")
        print("   Falling back to config file storage.")
        config["credentials"]["secure_password"] = False
        config["credentials"]["password"] = password
    
    # Get data start date
    print("\nEnter the start date for data download:")
    print("Format: MM/DD/YYYY (e.g., 01/01/2024)")
    print("This is how far back to fetch your historical data.")
    print()
    
    start_date = input("   Start date (press Enter for 01/01/2024): ").strip()
    if not start_date:
        start_date = "01/01/2024"
    
    config["data"]["weight_start_date"] = start_date
    config["data"]["sleep_start_date"] = start_date
    config["data"]["rhr_start_date"] = start_date
    config["data"]["monitoring_start_date"] = start_date
    
    # Metric or imperial
    print("\nUse metric units? (km, kg)")
    use_metric = input("Metric (Y/n): ").strip().lower()
    config["settings"]["metric"] = use_metric != 'n'
    
    # Set data directory to project folder
    project_data_dir = Path(__file__).parent.parent / "data"
    config["directories"]["relative_to_home"] = False
    config["directories"]["base_dir"] = str(project_data_dir).replace("\\", "/")
    
    # Save config
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=4)
    
    print()
    print("=" * 60)
    print("Configuration saved successfully!")
    print(f"Location: {config_file}")
    print()
    print("Health data will be stored in:")
    print(f"  {project_data_dir}")
    print()
    print("Next steps:")
    print("  1. Run: python scripts/test_connection.py")
    print("  2. Run: python scripts/run_sync.py --initial")
    print("=" * 60)


if __name__ == "__main__":
    setup_config()
