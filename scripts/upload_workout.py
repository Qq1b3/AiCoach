#!/usr/bin/env python3
"""Generate a week's workouts from the plan and push them to Garmin Connect.

Hybrid targets (coach rule): HR caps on easy/recovery effort, pace windows on quality.
HR/pace numbers come from coach/thresholds.json (single source). Dates are computed
from the ISO week number -- nothing is hardcoded. Defaults to the current ISO week;
override with --week / --year.

Usage:
    python scripts/upload_workout.py                 # dry-run current week, no network
    python scripts/upload_workout.py --week 24       # dry-run a specific ISO week
    python scripts/upload_workout.py --verify        # round-trip test the HR encoding, then clean up
    python scripts/upload_workout.py --week 24 --upload              # upload (no calendar)
    python scripts/upload_workout.py --week 24 --upload --schedule   # upload AND place on calendar
    python scripts/upload_workout.py --json          # also print the raw JSON payloads
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import garmin_workouts as gw
import thresholds as th

# HR target bands come from coach/thresholds.json (single source, mirrors lab_tests.md).
EASY = gw.hr_target(*th.hr_band("easy"))    # easy/recovery runs -- cap 146
LONG = gw.hr_target(*th.hr_band("long"))    # long run -- ceiling 150
WUCD = gw.hr_target(*th.hr_band("wu_cd"))   # warm-up / cool-down around quality

# Dates are computed from the ISO week, never hardcoded. CW24 = ISO week 24, 2026
# (Mon 08/06 - Sun 14/06), matching coach/weekly_planCW24.md.
_WEEKDAY = {"Mon": 1, "Tue": 2, "Wed": 3, "Thu": 4, "Fri": 5, "Sat": 6, "Sun": 7}


def session_date(year: int, week: int, weekday: str) -> str:
    """ISO 'YYYY-MM-DD' for a given weekday of an ISO week (e.g. Tue of CW24)."""
    return date.fromisocalendar(year, week, _WEEKDAY[weekday]).isoformat()


def build_week(year: int, week: int):
    """Return [(date 'YYYY-MM-DD', workout_dict), ...] for the given ISO week.

    Session content is the coach's plan for CW24; dates/labels derive from year+week.
    """
    tag = f"CW{week}"

    def on(weekday):
        return session_date(year, week, weekday)

    sessions = []

    # Tue - Easy 35-40 min, HR ceiling 146
    sessions.append((on("Tue"), gw.running_workout(
        f"{tag} Tue - Easy",
        [gw.easy_run(minutes=40, target=EASY, desc="Easy, HR cap 146")],
        description="Comeback wk2. Easy by HR, let pace be the result.",
    )))

    # Wed - Easy 30-35 min recovery, HR ceiling 146
    sessions.append((on("Wed"), gw.running_workout(
        f"{tag} Wed - Easy recovery",
        [gw.easy_run(minutes=35, target=EASY, desc="Genuinely light, HR cap 146")],
        description="Recovery run. Legs may be sore from Strength A -- keep it light.",
    )))

    # Thu - Sub-threshold feeler: WU 15' + 5x1000m @ 5:10-5:15 (90s rec) + CD 10'
    # Pace is a per-week coaching choice (conservative slice of the subthreshold zone).
    sessions.append((on("Thu"), gw.running_workout(
        f"{tag} Thu - Sub-threshold feeler",
        [
            gw.warmup(minutes=15, target=WUCD, desc="15 min easy"),
            gw.repeat(5, [
                gw.interval(meters=1000, target=gw.pace_target(fast="5:10", slow="5:15"), desc="1km @ 5:10-5:15"),
                gw.recovery(seconds=90, target=gw.no_target(), desc="90s easy jog"),
            ]),
            gw.cooldown(minutes=10, target=WUCD, desc="10 min easy"),
        ],
        description="First quality of the block. Pace is the target; if HR hits 167, back off. ANP 169 = hard ceiling.",
    )))

    # Sat - Long run 60-70 min easy, HR ceiling 150
    sessions.append((on("Sat"), gw.running_workout(
        f"{tag} Sat - Long run",
        [gw.easy_run(minutes=65, target=LONG, desc="Easy long, HR ceiling 150")],
        description="Longest since the layoff. Honestly easy the whole way.",
    )))

    return sessions


def verify_hr_encoding(garmin):
    """Upload a throwaway workout with HR + pace targets, read it back, then delete it.

    The trainer's workouts used pace targets only, so the HR encoding is the one piece
    not confirmed from real data -- this proves Garmin stores it the way we send it.
    """
    probe = gw.running_workout(
        "AICOACH HR PROBE (delete me)",
        [
            gw.easy_run(minutes=5, target=gw.hr_target(*th.hr_band("easy")), desc="hr step"),
            gw.interval(meters=1000, target=gw.pace_target(*th.pace_zone("subthreshold")), desc="pace step"),
        ],
    )
    print("Uploading throwaway probe workout...")
    res = gw.upload(garmin, probe)
    wid = res.get("workoutId")
    print(f"  uploaded workoutId={wid}; reading it back...")
    full = garmin.get_workout_by_id(wid)
    steps = full["workoutSegments"][0]["workoutSteps"]
    for s in steps:
        t = s.get("targetType", {})
        print(f"  stored step: target={t.get('workoutTargetTypeKey')} "
              f"id={t.get('workoutTargetTypeId')} "
              f"v1={s.get('targetValueOne')} v2={s.get('targetValueTwo')} "
              f"zone={s.get('zoneNumber')}")
    print("Deleting throwaway probe workout...")
    garmin.delete_workout(wid)
    print("  deleted. HR encoding check complete.")


def main() -> int:
    today = date.today().isocalendar()
    ap = argparse.ArgumentParser(description="Build + upload this week's Garmin workouts.")
    ap.add_argument("--week", type=int, default=today.week, help="ISO week number (default: current week)")
    ap.add_argument("--year", type=int, default=today.year, help="year (default: current year)")
    ap.add_argument("--upload", action="store_true", help="upload workouts to Garmin Connect")
    ap.add_argument("--schedule", action="store_true", help="also place each on its calendar date")
    ap.add_argument("--verify", action="store_true", help="round-trip test the HR encoding, then clean up")
    ap.add_argument("--json", action="store_true", help="also print raw JSON payloads")
    args = ap.parse_args()

    sessions = build_week(args.year, args.week)

    print("=" * 64)
    print(f"CW{args.week} {args.year} workouts (hybrid targets: HR caps easy, pace quality)")
    print("=" * 64)
    for date_str, w in sessions:
        print(f"\n[{date_str}]")
        print(gw.render(w))
        if args.json:
            print(json.dumps(w, indent=2))

    if not (args.upload or args.verify):
        print("\n(dry-run -- nothing sent. Re-run with --verify, then --upload --schedule.)")
        return 0

    print("\nConnecting to Garmin Connect (cached token)...")
    garmin = gw.connect()

    if args.verify:
        print("\n--- HR encoding round-trip ---")
        verify_hr_encoding(garmin)

    if args.upload:
        print("\n--- Uploading week ---")
        for date_str, w in sessions:
            res = gw.upload(garmin, w)
            wid = res.get("workoutId")
            print(f"  uploaded '{w['workoutName']}' -> workoutId={wid}")
            if args.schedule:
                gw.schedule(garmin, wid, date_str)
                print(f"    scheduled on {date_str}")
        print("\nDone. Open Garmin Connect calendar to confirm, then send to your watch.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
