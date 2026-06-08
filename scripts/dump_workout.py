#!/usr/bin/env python3
"""Probe Garmin Connect's workout JSON schema for THIS account.

Read-before-write step for the workout uploader. Logs in with the existing cached
token, lists the structured workouts already in your Connect account, and dumps the
full JSON of each so we can confirm the exact target/condition encoding (pace.zone
vs speed.zone, m/s value ordering, distance/time condition IDs) before building the
writer. Writes nothing to Garmin -- it only reads.

Usage:
    python scripts/dump_workout.py            # list + dump all existing workouts
    python scripts/dump_workout.py --limit 5  # cap how many to fetch
"""

import argparse
import json
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

OUT_DIR = Path(__file__).parent.parent / "data" / "workout_probe"


def main() -> int:
    parser = argparse.ArgumentParser(description="Dump existing Garmin workouts to JSON.")
    parser.add_argument("--limit", type=int, default=50, help="max workouts to fetch")
    args = parser.parse_args()

    print("Logging in to Garmin Connect (using cached token)...")
    try:
        adapter = garmin_auth.login()
    except GarminConnectAuthError as e:
        print(f"ERROR: login failed: {e}")
        print("Refresh the token with: python scripts/test_connection.py")
        return 1

    garmin = adapter.client
    print(f"Logged in as {adapter.full_name or adapter.display_name}.")

    workouts = garmin.get_workouts(0, args.limit)
    print(f"\nFound {len(workouts)} workout(s) in your account.")

    if not workouts:
        print(
            "\nNo structured workouts found. To capture the schema, create ONE workout\n"
            "by hand in Garmin Connect (e.g. a short run with a pace target and an HR\n"
            "target), then re-run this script -- the dumped JSON is our ground truth."
        )
        return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for w in workouts:
        wid = w.get("workoutId")
        name = w.get("workoutName", "unnamed")
        sport = (w.get("sportType") or {}).get("sportTypeKey", "?")
        print(f"  - {wid}  [{sport}]  {name}")

        # The list payload is a summary; fetch the full step detail per workout.
        full = garmin.get_workout_by_id(wid)
        out = OUT_DIR / f"workout_{wid}.json"
        out.write_text(json.dumps(full, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nDumped full JSON for {len(workouts)} workout(s) to: {OUT_DIR}")
    print("Open one and check: targetType (pace.zone/heart.rate.zone), targetValueOne/Two")
    print("units (m/s for pace, bpm for HR), and endCondition (distance vs time) IDs.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
