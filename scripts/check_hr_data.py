import sqlite3
from pathlib import Path

activities_db = Path.home() / 'HealthData' / 'DBs' / 'garmin_activities.db'
garmin_db = Path.home() / 'HealthData' / 'DBs' / 'garmin.db'

print("=" * 60)
print("CHECKING ACTIVITY HR DATA")
print("=" * 60)

conn = sqlite3.connect(activities_db)

# List all tables
print("\n=== ALL TABLES IN garmin_activities.db ===")
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
for t in tables:
    print(f"  {t[0]}")

# Check for activity_records table (per-second data)
print("\n=== Checking activity_records table ===")
try:
    cols = conn.execute("PRAGMA table_info(activity_records)").fetchall()
    if cols:
        print("Columns:")
        for c in cols:
            print(f"  {c[1]}")
        
        # Count records
        count = conn.execute("SELECT COUNT(*) FROM activity_records").fetchone()[0]
        print(f"\nTotal records: {count}")
        
        if count > 0:
            # Sample data from latest activity
            print("\nSample from latest running activity:")
            query = """
                SELECT ar.timestamp, ar.heart_rate, ar.speed, ar.distance
                FROM activity_records ar
                JOIN activities a ON ar.activity_id = a.activity_id
                WHERE a.sport = 'running'
                ORDER BY a.start_time DESC, ar.timestamp
                LIMIT 20
            """
            rows = conn.execute(query).fetchall()
            for r in rows:
                print(f"  {r}")
    else:
        print("Table exists but no columns found")
except Exception as e:
    print(f"Table not found or error: {e}")

# Check monitoring_hr in garmin.db for continuous HR
print("\n" + "=" * 60)
print("CHECKING MONITORING HR DATA (garmin.db)")
print("=" * 60)

conn2 = sqlite3.connect(garmin_db)

print("\n=== monitoring_hr table ===")
try:
    cols = conn2.execute("PRAGMA table_info(monitoring_hr)").fetchall()
    print("Columns:")
    for c in cols:
        print(f"  {c[1]}")
    
    print("\nSample data:")
    rows = conn2.execute("SELECT * FROM monitoring_hr ORDER BY timestamp DESC LIMIT 10").fetchall()
    for r in rows:
        print(f"  {r}")
except Exception as e:
    print(f"Error: {e}")

# Check FIT files location
print("\n" + "=" * 60)
print("CHECKING FIT FILES")
print("=" * 60)

fit_dir = Path.home() / 'HealthData' / 'FitFiles' / 'Activities'
if fit_dir.exists():
    files = list(fit_dir.glob("*.fit"))
    print(f"FIT files found: {len(files)}")
    if files:
        print("Latest 5 files:")
        for f in sorted(files, key=lambda x: x.stat().st_mtime, reverse=True)[:5]:
            print(f"  {f.name} ({f.stat().st_size / 1024:.1f} KB)")
else:
    print(f"FIT directory not found: {fit_dir}")
