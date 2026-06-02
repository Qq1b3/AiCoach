#!/usr/bin/env python3
"""
Test/refresh the Garmin Connect connection.

Run after setup_config.py to verify your credentials work. This also refreshes the
cached login token (~/.GarminDb/garmin_tokens.json), so re-run it if a sync ever
fails with an authentication error.
"""

import sys
from pathlib import Path

# Make sibling modules (garmin_auth) importable regardless of CWD.
sys.path.insert(0, str(Path(__file__).parent))

try:
    import garmin_auth
    from garmin_auth import GarminConnectAuthError
except ImportError as e:
    print(f"ERROR: Import error: {e}")
    print("Activate the virtual environment and install dependencies:")
    print("  .\\venv\\Scripts\\Activate.ps1")
    print("  pip install -r requirements.txt")
    sys.exit(1)


def test_connection() -> bool:
    """Authenticate to Garmin Connect and report the result."""
    print("=" * 60)
    print("AiCoach - Testing Garmin Connect Connection")
    print("=" * 60)
    print()

    config_path = Path.home() / ".GarminDb" / "GarminConnectConfig.json"
    if not config_path.exists():
        print("ERROR: Config file not found!")
        print(f"  Expected: {config_path}")
        print("  Run: python scripts/setup_config.py")
        return False
    print("[OK] Config file found")

    print()
    print("Authenticating with Garmin Connect...")
    print("(Uses the cached token if present, otherwise your stored password.)")
    print("(If your account has 2FA enabled, you'll be prompted for a code.)")
    print()

    try:
        adapter = garmin_auth.login()
    except GarminConnectAuthError as e:
        print(f"ERROR: Authentication failed: {e}")
        print()
        print("Common issues:")
        print("  - Wrong email/password (re-run: python scripts/setup_config.py)")
        print("  - Incorrect or expired 2FA code")
        print("  - Account temporarily locked / rate-limited (try again later)")
        return False
    except Exception as e:
        print(f"ERROR: Unexpected error: {e}")
        return False

    name = adapter.full_name or adapter.display_name or "(unknown)"
    print("[OK] Successfully authenticated!")
    print(f"  Connected as: {name}")
    print(f"  Token cached at: {Path.home() / '.GarminDb' / 'garmin_tokens.json'}")

    print()
    print("=" * 60)
    print("All tests passed! You're ready to sync data.")
    print()
    print("Next step:")
    print("  python scripts/run_sync.py --initial")
    print("=" * 60)
    return True


if __name__ == "__main__":
    sys.exit(0 if test_connection() else 1)
