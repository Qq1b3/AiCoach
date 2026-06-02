#!/usr/bin/env python3
"""
Test script to verify Garmin Connect connection.
Run this after setup_config.py to verify your credentials work.
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    import garth
    from garmindb import GarminConnectConfigManager
except ImportError as e:
    print(f"ERROR: Import error: {e}")
    print("Make sure you've activated the virtual environment:")
    print("  .\\venv\\Scripts\\Activate.ps1")
    sys.exit(1)


def test_connection():
    """Test the Garmin Connect connection."""
    print("=" * 60)
    print("AiCoach - Testing Garmin Connect Connection")
    print("=" * 60)
    print()
    
    # Check config exists
    config_path = Path.home() / ".GarminDb" / "GarminConnectConfig.json"
    if not config_path.exists():
        print("ERROR: Config file not found!")
        print(f"  Expected: {config_path}")
        print("  Run: python scripts/setup_config.py")
        return False
    
    print("[OK] Config file found")
    
    # Load config
    try:
        config = GarminConnectConfigManager()
        print("[OK] Config loaded successfully")
    except Exception as e:
        print(f"ERROR: Failed to load config: {e}")
        return False
    
    # Test Garmin Connect authentication
    print()
    print("Attempting to authenticate with Garmin Connect...")
    print("(This may take a moment)")
    print()
    
    try:
        # Use garth for authentication (this is what GarminDB uses internally)
        session_file = config.get_session_file()
        
        # Try to resume existing session first
        session_loaded = False
        if os.path.isfile(session_file):
            try:
                with open(session_file, "r", encoding="utf-8") as f:
                    garth.client.loads(f.read())
                print("[OK] Resumed existing session")
                session_loaded = True
            except Exception:
                pass
        
        if not session_loaded:
            print("No existing session, logging in...")
            garth.login(config.get_user(), config.get_password())
            # Save session in the format GarminDB expects (JSON string to file)
            with open(session_file, "w", encoding="utf-8") as f:
                f.write(garth.client.dumps())
            print("[OK] New session created")
        
        # Get user profile to verify connection
        profile = garth.client.username
        print("[OK] Successfully authenticated!")
        print(f"  Connected as: {profile}")
        print(f"  Session saved to: {session_file}")
        
    except Exception as e:
        print(f"ERROR: Authentication failed: {e}")
        print()
        print("Common issues:")
        print("  - Wrong email/password")
        print("  - 2FA enabled (may need to use app password)")
        print("  - Account locked (try logging in via browser)")
        return False
    
    print()
    print("=" * 60)
    print("All tests passed! You're ready to sync data.")
    print()
    print("Data will be stored in:")
    project_data = Path(__file__).parent.parent / "data"
    print(f"  {project_data}")
    print()
    print("Next step:")
    print("  python scripts/run_sync.py --initial")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)
