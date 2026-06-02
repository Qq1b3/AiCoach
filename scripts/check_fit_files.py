from pathlib import Path
import sqlite3

conn = sqlite3.connect('data/DBs/garmin_activities.db')

# Check total activity records
total = conn.execute('SELECT COUNT(*) FROM activity_records').fetchone()[0]
print(f'Total activity_records: {total}')

# Check records per recent running activity
print()
print('Records per recent running activity:')
query = """
    SELECT a.activity_id, a.name, a.start_time, COUNT(ar.record) as cnt
    FROM activities a
    LEFT JOIN activity_records ar ON a.activity_id = ar.activity_id
    WHERE a.sport = 'running'
    GROUP BY a.activity_id
    ORDER BY a.start_time DESC
    LIMIT 10
"""
for r in conn.execute(query).fetchall():
    print(f'  {r[2][:10]} - {r[1]}: {r[3]} records')

# Check FIT files
print()
print('Available FIT files (latest 5):')
fit_dir = Path('data/FitFiles/Activities')
fit_files = sorted(fit_dir.glob('*.fit'), key=lambda x: x.stat().st_mtime, reverse=True)[:5]
for f in fit_files:
    print(f'  {f.name}')
