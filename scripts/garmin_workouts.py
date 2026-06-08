#!/usr/bin/env python3
"""Build and upload structured running workouts to Garmin Connect.

The JSON shape here is reverse-engineered from this account's own trainer-built
workouts (dumped by scripts/dump_workout.py), so generated workouts render on the
watch exactly like the trainer's. Confirmed encoding:

  * pace target   -> workoutTargetTypeId 6 / "pace.zone", values in m/s,
                     targetValueOne = SLOWER bound, targetValueTwo = FASTER bound
  * HR target     -> workoutTargetTypeId 4 / "heart.rate.zone", values in bpm
                     (custom range; zoneNumber stays null) -- verify via round-trip
  * end condition -> time(2) seconds | distance(3) meters | lap.button(1) | iterations(7)
  * stepId is server-assigned (omit on create); childStepId groups repeat children;
    stepOrder is sequential across the flattened step tree.

Targets follow the coach's HYBRID rule: HR caps on easy/recovery effort, pace windows
on quality reps. Build steps with the helpers, assemble with running_workout(), then
upload()/schedule() against the client from scripts/garmin_auth.py::login().
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# Make sibling modules (garmin_auth) importable regardless of CWD.
sys.path.insert(0, str(Path(__file__).parent))


# --------------------------------------------------------------------------- #
# Pace helpers
# --------------------------------------------------------------------------- #
def _to_seconds(value: str | int | float) -> float:
    """Accept '5:10' (min:sec) or a raw seconds number -> total seconds."""
    if isinstance(value, (int, float)):
        return float(value)
    m, s = value.split(":")
    return int(m) * 60 + int(s)


def pace_to_mps(pace: str | int | float) -> float:
    """Convert a per-km pace ('5:10' or seconds) to meters/second, 3 dp."""
    return round(1000.0 / _to_seconds(pace), 3)


def mps_to_pace(mps: float | None) -> str:
    """Inverse of pace_to_mps for human-readable rendering."""
    if not mps:
        return "-"
    s = 1000.0 / mps
    return f"{int(s // 60)}:{int(round(s % 60)):02d}/km"


# --------------------------------------------------------------------------- #
# Target builders -> partial dicts merged into a step
# --------------------------------------------------------------------------- #
def pace_target(fast: str | int | float, slow: str | int | float) -> dict[str, Any]:
    """Pace window. `fast`/`slow` are per-km paces ('5:10') or seconds."""
    return {
        "targetType": {"workoutTargetTypeId": 6, "workoutTargetTypeKey": "pace.zone", "displayOrder": 6},
        "targetValueOne": pace_to_mps(slow),   # slower bound = smaller m/s
        "targetValueTwo": pace_to_mps(fast),   # faster bound = larger m/s
    }


def hr_target(low: int, high: int) -> dict[str, Any]:
    """Heart-rate window in bpm. Use for easy steps; `high` is the cap."""
    return {
        "targetType": {"workoutTargetTypeId": 4, "workoutTargetTypeKey": "heart.rate.zone", "displayOrder": 4},
        "targetValueOne": int(low),
        "targetValueTwo": int(high),
    }


def no_target() -> dict[str, Any]:
    return {
        "targetType": {"workoutTargetTypeId": 1, "workoutTargetTypeKey": "no.target", "displayOrder": 1},
        "targetValueOne": None,
        "targetValueTwo": None,
    }


# --------------------------------------------------------------------------- #
# End conditions
# --------------------------------------------------------------------------- #
def _end_time(seconds: float) -> tuple[dict[str, Any], float]:
    return ({"conditionTypeId": 2, "conditionTypeKey": "time", "displayOrder": 2, "displayable": True}, float(seconds))


def _end_distance(meters: float) -> tuple[dict[str, Any], float]:
    return ({"conditionTypeId": 3, "conditionTypeKey": "distance", "displayOrder": 3, "displayable": True}, float(meters))


def _end_lap() -> tuple[dict[str, Any], None]:
    return ({"conditionTypeId": 1, "conditionTypeKey": "lap.button", "displayOrder": 1, "displayable": True}, None)


_STEP_TYPES = {
    "warmup": (1, 1),
    "cooldown": (2, 2),
    "interval": (3, 3),
    "recovery": (4, 4),
    "rest": (5, 5),
}


def _executable(step_key: str, end: tuple[dict, Any], target: dict[str, Any] | None,
                description: str | None) -> dict[str, Any]:
    """Build one ExecutableStepDTO with the full field set the watch expects.

    stepId / stepOrder / childStepId are filled in later by _finalize().
    """
    type_id, display = _STEP_TYPES[step_key]
    end_cond, end_val = end
    tgt = target or no_target()
    return {
        "type": "ExecutableStepDTO",
        "stepOrder": None,
        "stepType": {"stepTypeId": type_id, "stepTypeKey": step_key, "displayOrder": display},
        "childStepId": None,
        "description": description,
        "endCondition": end_cond,
        "endConditionValue": end_val,
        "preferredEndConditionUnit": None,
        "endConditionCompare": None,
        "targetType": tgt["targetType"],
        "targetValueOne": tgt["targetValueOne"],
        "targetValueTwo": tgt["targetValueTwo"],
        "targetValueUnit": None,
        "zoneNumber": None,
        "secondaryTargetType": None,
        "secondaryTargetValueOne": None,
        "secondaryTargetValueTwo": None,
        "secondaryTargetValueUnit": None,
        "secondaryZoneNumber": None,
        "endConditionZone": None,
        "strokeType": {"strokeTypeId": 0, "strokeTypeKey": None, "displayOrder": 0},
        "equipmentType": {"equipmentTypeId": 0, "equipmentTypeKey": None, "displayOrder": 0},
        "category": None,
        "exerciseName": None,
        "weightValue": None,
        "weightUnit": None,
    }


# --------------------------------------------------------------------------- #
# Public step builders
# --------------------------------------------------------------------------- #
def _resolve_end(minutes, seconds, meters, lap):
    if lap:
        return _end_lap()
    if meters is not None:
        return _end_distance(meters)
    if minutes is not None:
        return _end_time(minutes * 60)
    if seconds is not None:
        return _end_time(seconds)
    return _end_lap()


def warmup(*, minutes=None, lap=False, target=None, desc="Warm up"):
    return _executable("warmup", _resolve_end(minutes, None, None, lap), target, desc)


def cooldown(*, minutes=None, lap=False, target=None, desc="Cool down"):
    return _executable("cooldown", _resolve_end(minutes, None, None, lap), target, desc)


def interval(*, meters=None, minutes=None, seconds=None, lap=False, target=None, desc=None):
    return _executable("interval", _resolve_end(minutes, seconds, meters, lap), target, desc)


def recovery(*, seconds=None, minutes=None, lap=False, target=None, desc="Recovery"):
    return _executable("rest", _resolve_end(minutes, seconds, None, lap), target, desc)


def easy_run(*, minutes, target, desc="Easy run"):
    """A single-step easy/long run (one interval block, time-based, HR target)."""
    return _executable("interval", _end_time(minutes * 60), target, desc)


def repeat(times: int, steps: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "type": "RepeatGroupDTO",
        "stepOrder": None,
        "stepType": {"stepTypeId": 6, "stepTypeKey": "repeat", "displayOrder": 6},
        "childStepId": None,
        "numberOfIterations": int(times),
        "workoutSteps": steps,
        "endCondition": {"conditionTypeId": 7, "conditionTypeKey": "iterations", "displayOrder": 7, "displayable": False},
        "endConditionValue": float(times),
        "preferredEndConditionUnit": None,
        "endConditionCompare": None,
        "skipLastRestStep": None,
        "smartRepeat": False,
    }


# --------------------------------------------------------------------------- #
# Assembly
# --------------------------------------------------------------------------- #
def _finalize(steps: list[dict[str, Any]]) -> None:
    """Assign stepOrder (sequential, flattened) and childStepId (repeat grouping)."""
    order = [0]
    group = [0]

    def walk(items: list[dict[str, Any]], child_id):
        for s in items:
            order[0] += 1
            s["stepOrder"] = order[0]
            if s["type"] == "RepeatGroupDTO":
                group[0] += 1
                gid = group[0]
                s["childStepId"] = gid
                walk(s["workoutSteps"], gid)
            else:
                s["childStepId"] = child_id

    walk(steps, None)


def _estimate_seconds(steps: list[dict[str, Any]]) -> int:
    """Rough duration estimate (Garmin recomputes; this is just for display)."""
    total = 0.0
    for s in steps:
        if s["type"] == "RepeatGroupDTO":
            total += s["numberOfIterations"] * _estimate_seconds(s["workoutSteps"])
            continue
        cond = s["endCondition"]["conditionTypeKey"]
        val = s.get("endConditionValue")
        if cond == "time" and val:
            total += val
        elif cond == "distance" and val:
            mps = s.get("targetValueTwo") or s.get("targetValueOne") or 3.0
            total += val / mps
        else:  # lap.button -- nominal guess
            total += 120
    return int(total)


def running_workout(name: str, steps: list[dict[str, Any]], description: str | None = None) -> dict[str, Any]:
    """Assemble a complete running-workout payload ready for upload()."""
    _finalize(steps)
    sport = {"sportTypeId": 1, "sportTypeKey": "running", "displayOrder": 1}
    est = _estimate_seconds(steps)
    return {
        "workoutName": name,
        "description": description,
        "sportType": sport,
        "subSportType": None,
        "estimatedDurationInSecs": est,
        "workoutSegments": [
            {"segmentOrder": 1, "sportType": sport, "workoutSteps": steps}
        ],
    }


# --------------------------------------------------------------------------- #
# Connect / IO
# --------------------------------------------------------------------------- #
def connect():
    """Log in via the existing cached token and return the garminconnect client."""
    import garmin_auth
    return garmin_auth.login().client


def upload(garmin, workout: dict[str, Any]) -> dict[str, Any]:
    """POST the workout to Garmin. Returns the created workout (incl. workoutId)."""
    return garmin.upload_workout(workout)


def schedule(garmin, workout_id, date_str: str) -> dict[str, Any]:
    """Put an uploaded workout on the Connect calendar (date as 'YYYY-MM-DD')."""
    return garmin.schedule_workout(workout_id, date_str)


# --------------------------------------------------------------------------- #
# Rendering (for --dry-run)
# --------------------------------------------------------------------------- #
def _render_step(s: dict[str, Any], indent: int = 0) -> list[str]:
    pad = "  " * indent
    if s["type"] == "RepeatGroupDTO":
        out = [f"{pad}REPEAT x{s['numberOfIterations']}:"]
        for c in s["workoutSteps"]:
            out += _render_step(c, indent + 1)
        return out
    cond = s["endCondition"]["conditionTypeKey"]
    val = s.get("endConditionValue")
    if cond == "time":
        dur = f"{int(val // 60)}:{int(val % 60):02d} min"
    elif cond == "distance":
        dur = f"{val:.0f} m"
    else:
        dur = "press LAP"
    t = s.get("targetType", {})
    if t.get("workoutTargetTypeKey") == "pace.zone":
        tgt = f"@ {mps_to_pace(s['targetValueTwo'])}-{mps_to_pace(s['targetValueOne'])}"
    elif t.get("workoutTargetTypeKey") == "heart.rate.zone":
        tgt = f"@ HR {s['targetValueOne']}-{s['targetValueTwo']}"
    else:
        tgt = ""
    label = s["stepType"]["stepTypeKey"]
    return [f"{pad}- [{label}] {dur} {tgt}".rstrip()]


def render(workout: dict[str, Any]) -> str:
    lines = [f"{workout['workoutName']}  (~{workout['estimatedDurationInSecs'] // 60} min)"]
    if workout.get("description"):
        lines.append(f"  {workout['description']}")
    for s in workout["workoutSegments"][0]["workoutSteps"]:
        lines += _render_step(s)
    return "\n".join(lines)
