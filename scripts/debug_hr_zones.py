#!/usr/bin/env python3
"""Debug HR zone calculation."""

from pathlib import Path
from fitparse import FitFile

PROJECT_DIR = Path(__file__).parent.parent
FIT_DIR = PROJECT_DIR / 'data' / 'FitFiles' / 'Activities'

# Get the most recent activity
fits = sorted(FIT_DIR.glob('*_ACTIVITY.fit'), reverse=True)
fit_path = fits[0]

print(f"Analyzing: {fit_path.name}")
fit = FitFile(str(fit_path))

records = []
session = {}

for record in fit.get_messages():
    if record.name == 'record':
        data = {}
        for field in record.fields:
            data[field.name] = field.value
        records.append(data)
    elif record.name == 'session':
        for field in record.fields:
            session[field.name] = field.value

# Analyze HR data
hr_records = [(r.get('timestamp'), r.get('heart_rate')) for r in records]
hr_with_data = [(ts, hr) for ts, hr in hr_records if hr]
hr_without_data = [(ts, hr) for ts, hr in hr_records if not hr]

print(f"\nTotal records: {len(records)}")
print(f"Records WITH HR: {len(hr_with_data)}")
print(f"Records WITHOUT HR: {len(hr_without_data)}")

elapsed = session.get('total_elapsed_time', 0)
print(f"\nSession elapsed_time: {elapsed}s = {elapsed/60:.1f}min")

if hr_with_data:
    first_ts = hr_with_data[0][0]
    last_ts = hr_with_data[-1][0]
    if first_ts and last_ts:
        hr_span = (last_ts - first_ts).total_seconds()
        print(f"HR data time span: {hr_span}s = {hr_span/60:.1f}min")
        print(f"Missing time: {elapsed - hr_span:.1f}s = {(elapsed - hr_span)/60:.1f}min")

# Count time per zone with proper deltas
LTHR = 174
bounds = {
    'z1_max': int(LTHR * 0.85),  # 147
    'z2_max': int(LTHR * 0.89),  # 154
    'z3_max': int(LTHR * 0.94),  # 163
    'z4_max': int(LTHR * 0.99),  # 172
}

print(f"\nZone boundaries: Z1<{bounds['z1_max']} | Z2:{bounds['z1_max']}-{bounds['z2_max']} | Z3:{bounds['z2_max']+1}-{bounds['z3_max']} | Z4:{bounds['z3_max']+1}-{bounds['z4_max']} | Z5>{bounds['z4_max']}")

zone_times = {'z1': 0, 'z2': 0, 'z3': 0, 'z4': 0, 'z5': 0}
prev_ts = None
total_counted = 0

for ts, hr in hr_with_data:
    if not hr:
        continue
    
    # Calculate delta
    if ts and prev_ts:
        delta = (ts - prev_ts).total_seconds()
        delta = max(delta, 0)  # Only reject negative
    else:
        delta = 1
    
    total_counted += delta
    
    # Classify
    if hr < bounds['z1_max']:
        zone_times['z1'] += delta
    elif hr <= bounds['z2_max']:
        zone_times['z2'] += delta
    elif hr <= bounds['z3_max']:
        zone_times['z3'] += delta
    elif hr <= bounds['z4_max']:
        zone_times['z4'] += delta
    else:
        zone_times['z5'] += delta
    
    prev_ts = ts

print(f"\nZone times (seconds):")
for z, t in zone_times.items():
    print(f"  {z.upper()}: {t:.0f}s = {t/60:.1f}min")

print(f"\nTotal zone time: {total_counted:.0f}s = {total_counted/60:.1f}min")
print(f"Session elapsed: {elapsed:.0f}s = {elapsed/60:.1f}min")
print(f"Difference: {elapsed - total_counted:.0f}s = {(elapsed - total_counted)/60:.1f}min")
