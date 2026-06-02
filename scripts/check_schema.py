#!/usr/bin/env python3
"""Quick check of actual database schema."""

import sqlite3
from pathlib import Path

db_path = Path.home() / 'HealthData' / 'DBs'

# Check garmin.db
conn = sqlite3.connect(db_path / 'garmin.db')

print("=== SLEEP columns ===")
cols = conn.execute("PRAGMA table_info(sleep)").fetchall()
for c in cols:
    print(f"  {c[1]} ({c[2]})")

print("\n=== garmin.db tables ===")
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
for t in tables:
    print(f"  {t[0]}")

print("\n=== resting_hr sample ===")
rows = conn.execute("SELECT * FROM resting_hr LIMIT 3").fetchall()
for r in rows:
    print(f"  {r}")

conn.close()

# Check monitoring_hr
conn2 = sqlite3.connect(db_path / 'garmin_monitoring.db')
print("\n=== monitoring_hr columns ===")
cols = conn2.execute("PRAGMA table_info(monitoring_hr)").fetchall()
for c in cols:
    print(f"  {c[1]} ({c[2]})")

print("\n=== monitoring_hr sample ===")
rows = conn2.execute("SELECT * FROM monitoring_hr LIMIT 3").fetchall()
for r in rows:
    print(f"  {r}")

conn2.close()
