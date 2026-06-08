#!/usr/bin/env python3
"""Single source of the athlete's HR/pace thresholds.

Reads coach/thresholds.json (the machine-readable mirror of coach/lab_tests.md) so no
HR or pace number is hardcoded in the workout scripts. Change a threshold in ONE place
(thresholds.json, kept in sync with lab_tests.md) and every script picks it up.
"""

import json
from functools import lru_cache
from pathlib import Path

_PATH = Path(__file__).parent.parent / "coach" / "thresholds.json"


@lru_cache(maxsize=1)
def load() -> dict:
    """Load and cache the thresholds config."""
    return json.loads(_PATH.read_text(encoding="utf-8"))


def hr_band(name: str) -> tuple[int, int]:
    """On-watch HR target range (low, high) for a session type: easy/long/wu_cd/quality."""
    lo, hi = load()["hr_bands"][name]
    return int(lo), int(hi)


def hr(name: str) -> int:
    """A single HR threshold value: max/ap/anp/lthr."""
    return int(load()["hr"][name])


def pace_zone(name: str) -> tuple[str, str]:
    """Reference pace window (fast, slow) as 'M:SS' for a named zone."""
    z = load()["pace_zones"][name]
    return z["fast"], z["slow"]
