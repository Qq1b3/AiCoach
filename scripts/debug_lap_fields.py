#!/usr/bin/env python3
"""Debug script to check FIT lap field names."""

from pathlib import Path
from fitparse import FitFile

PROJECT_DIR = Path(__file__).parent.parent
FIT_DIR = PROJECT_DIR / 'data' / 'FitFiles' / 'Activities'

# Get most recent activity
fit_files = sorted(FIT_DIR.glob('*_ACTIVITY.fit'), reverse=True)
if fit_files:
    fit_path = fit_files[0]
    print(f"Checking: {fit_path.name}")
    
    fit = FitFile(str(fit_path))
    
    for record in fit.get_messages('session'):
        print("\n=== SESSION FIELDS ===")
        for field in record.fields:
            if 'temp' in field.name.lower():
                print(f"  {field.name}: {field.value}")
        break  # Just first session
