#!/usr/bin/env python3
"""Explore the Garmin databases - shows available metrics and recent data."""

import sqlite3
from pathlib import Path
from datetime import datetime, timedelta

db_path = Path.home() / 'HealthData' / 'DBs'


def get_connection(db_name):
    """Get database connection."""
    return sqlite3.connect(db_path / db_name)


def list_all_tables():
    """List all tables across all databases."""
    print("=" * 70)
    print("DATABASE SCHEMA OVERVIEW")
    print("=" * 70)
    
    for db_file in sorted(db_path.glob("*.db")):
        conn = sqlite3.connect(db_file)
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
        
        print(f"\n{db_file.name}:")
        for t in tables:
            if t[0].startswith('_'):
                continue
            cols = conn.execute(f"PRAGMA table_info({t[0]})").fetchall()
            col_names = [c[1] for c in cols]
            count = conn.execute(f"SELECT COUNT(*) FROM {t[0]}").fetchone()[0]
            print(f"  {t[0]} ({count} rows): {', '.join(col_names[:8])}{'...' if len(col_names) > 8 else ''}")
        conn.close()


def show_recent_activities(limit=10):
    """Show recent activities with key metrics."""
    print("\n" + "=" * 70)
    print("RECENT ACTIVITIES")
    print("=" * 70)
    
    conn = get_connection('garmin_activities.db')
    
    query = f"""
        SELECT start_time, name, sport, distance, elapsed_time, 
               avg_hr, max_hr, calories, training_effect, avg_cadence
        FROM activities 
        ORDER BY start_time DESC 
        LIMIT {limit}
    """
    rows = conn.execute(query).fetchall()
    
    print(f"\n{'Date':<12} {'Name':<25} {'Sport':<12} {'Dist':<8} {'Time':<9} {'AvgHR':<6} {'MaxHR':<6} {'Cal':<5} {'TE'}")
    print("-" * 95)
    
    for row in rows:
        date = str(row[0])[:10] if row[0] else ""
        name = (row[1] or "")[:23]
        sport = str(row[2] or "")[:10]
        dist = f"{row[3]:.1f}km" if row[3] else "-"
        time = str(row[4]).split('.')[0][:8] if row[4] else "-"
        avg_hr = str(int(row[5])) if row[5] else "-"
        max_hr = str(int(row[6])) if row[6] else "-"
        cal = str(int(row[7])) if row[7] else "-"
        te = f"{row[8]:.1f}" if row[8] else "-"
        print(f"{date:<12} {name:<25} {sport:<12} {dist:<8} {time:<9} {avg_hr:<6} {max_hr:<6} {cal:<5} {te}")
    
    conn.close()


def show_vo2_max_summary():
    """Show VO2 max summary (latest values only)."""
    print("\n" + "=" * 70)
    print("VO2 MAX SUMMARY")
    print("=" * 70)
    
    conn = get_connection('garmin_activities.db')
    
    # Latest cycling VO2 max
    query = """
        SELECT a.start_time, c.vo2_max
        FROM activities a
        JOIN cycle_activities c ON a.activity_id = c.activity_id
        WHERE c.vo2_max IS NOT NULL
        ORDER BY a.start_time DESC
        LIMIT 5
    """
    rows = conn.execute(query).fetchall()
    if rows:
        print(f"\nCycling VO2max (last 5):")
        for row in rows:
            print(f"  {str(row[0])[:10]}: {row[1]}")
    
    # Latest running VO2 max
    query = """
        SELECT a.start_time, s.vo2_max
        FROM activities a
        JOIN steps_activities s ON a.activity_id = s.activity_id
        WHERE s.vo2_max IS NOT NULL
        ORDER BY a.start_time DESC
        LIMIT 5
    """
    rows = conn.execute(query).fetchall()
    if rows:
        print(f"\nRunning VO2max (last 5):")
        for row in rows:
            print(f"  {str(row[0])[:10]}: {row[1]}")
    
    conn.close()


def show_sleep_summary(days=7):
    """Show recent sleep data."""
    print("\n" + "=" * 70)
    print(f"SLEEP DATA (Last {days} days)")
    print("=" * 70)
    
    conn = get_connection('garmin.db')
    
    query = f"""
        SELECT day, total_sleep, deep_sleep, light_sleep, rem_sleep, awake,
               score, avg_rr
        FROM sleep
        ORDER BY day DESC
        LIMIT {days}
    """
    
    try:
        rows = conn.execute(query).fetchall()
        print(f"\n{'Date':<12} {'Total':<8} {'Deep':<8} {'Light':<8} {'REM':<8} {'Awake':<8} {'Score':<6} {'RR'}")
        print("-" * 75)
        
        for row in rows:
            date = str(row[0])
            total = _format_duration(row[1])
            deep = _format_duration(row[2])
            light = _format_duration(row[3])
            rem = _format_duration(row[4])
            awake = _format_duration(row[5])
            score = str(row[6]) if row[6] else "-"
            rr = f"{row[7]:.1f}" if row[7] else "-"
            print(f"{date:<12} {total:<8} {deep:<8} {light:<8} {rem:<8} {awake:<8} {score:<6} {rr}")
    except Exception as e:
        print(f"Error: {e}")
    
    conn.close()


def show_resting_hr(days=14):
    """Show resting heart rate trend."""
    print("\n" + "=" * 70)
    print(f"RESTING HEART RATE (Last {days} days)")
    print("=" * 70)
    
    conn = get_connection('garmin.db')
    
    query = f"""
        SELECT day, resting_heart_rate
        FROM resting_hr
        ORDER BY day DESC
        LIMIT {days}
    """
    
    try:
        rows = conn.execute(query).fetchall()
        print(f"\n{'Date':<12} {'RHR':<6} {'Trend'}")
        print("-" * 30)
        
        prev_rhr = None
        for row in rows:
            date = str(row[0])
            rhr = row[1]
            if prev_rhr:
                diff = rhr - prev_rhr
                trend = f"+{diff}" if diff > 0 else str(diff) if diff < 0 else "="
            else:
                trend = ""
            prev_rhr = rhr
            print(f"{date:<12} {rhr:<6} {trend}")
    except Exception as e:
        print(f"Error: {e}")
    
    conn.close()


def show_weight_data(days=14):
    """Show weight trend."""
    print("\n" + "=" * 70)
    print(f"WEIGHT DATA (Last {days} days)")
    print("=" * 70)
    
    conn = get_connection('garmin.db')
    
    query = f"""
        SELECT day, weight
        FROM weight
        WHERE weight IS NOT NULL
        ORDER BY day DESC
        LIMIT {days}
    """
    
    try:
        rows = conn.execute(query).fetchall()
        if rows:
            print(f"\n{'Date':<12} {'Weight (kg)'}")
            print("-" * 25)
            for row in rows:
                print(f"{row[0]:<12} {row[1]:.1f}")
        else:
            print("\nNo weight data found.")
    except Exception as e:
        print(f"Error: {e}")
    
    conn.close()


def show_daily_summary(days=7):
    """Show daily activity summary."""
    print("\n" + "=" * 70)
    print(f"DAILY SUMMARY (Last {days} days)")
    print("=" * 70)
    
    conn = get_connection('garmin.db')
    
    query = f"""
        SELECT day, steps, calories_active, rhr, stress_avg, 
               bb_max, bb_min, bb_charged, floors_up
        FROM daily_summary
        ORDER BY day DESC
        LIMIT {days}
    """
    
    try:
        rows = conn.execute(query).fetchall()
        
        print(f"\n{'Date':<12} {'Steps':<8} {'ActCal':<8} {'RHR':<5} {'Stress':<7} {'BB(max/min/chg)':<16} {'Floors'}")
        print("-" * 75)
        
        for row in rows:
            date = str(row[0])
            steps = str(row[1]) if row[1] else "-"
            cal = str(row[2]) if row[2] else "-"
            rhr = str(row[3]) if row[3] else "-"
            stress = str(row[4]) if row[4] else "-"
            bb = f"{row[5]}/{row[6]}/{row[7]}" if row[5] else "-"
            floors = f"{row[8]:.1f}" if row[8] else "-"
            print(f"{date:<12} {steps:<8} {cal:<8} {rhr:<5} {stress:<7} {bb:<16} {floors}")
            
    except Exception as e:
        print(f"Error: {e}")
    
    conn.close()


def show_monitoring_hr_sample():
    """Show sample of heart rate monitoring data."""
    print("\n" + "=" * 70)
    print("HEART RATE MONITORING (Sample)")
    print("=" * 70)
    
    conn = get_connection('garmin_monitoring.db')
    
    query = """
        SELECT DATE(timestamp) as day, COUNT(*) as readings, 
               MIN(heart_rate) as min_hr, 
               AVG(heart_rate) as avg_hr, 
               MAX(heart_rate) as max_hr
        FROM monitoring_hr
        GROUP BY DATE(timestamp)
        ORDER BY day DESC
        LIMIT 7
    """
    
    try:
        rows = conn.execute(query).fetchall()
        print(f"\n{'Date':<12} {'Readings':<10} {'Min HR':<8} {'Avg HR':<8} {'Max HR'}")
        print("-" * 50)
        for row in rows:
            print(f"{row[0]:<12} {row[1]:<10} {row[2]:<8} {row[3]:.0f}{'':>5} {row[4]}")
    except Exception as e:
        print(f"Error: {e}")
    
    conn.close()


def show_training_load_estimate():
    """Estimate training load from recent activities."""
    print("\n" + "=" * 70)
    print("TRAINING LOAD ESTIMATE (Last 7 & 28 days)")
    print("=" * 70)
    
    conn = get_connection('garmin_activities.db')
    
    # Get activities from last 28 days
    query = """
        SELECT start_time, sport, elapsed_time, avg_hr, max_hr, 
               calories, training_effect
        FROM activities
        WHERE start_time >= date('now', '-28 days')
        ORDER BY start_time DESC
    """
    
    try:
        rows = conn.execute(query).fetchall()
        
        last_7_days = []
        last_28_days = []
        today = datetime.now().date()
        
        for row in rows:
            activity_date = datetime.strptime(str(row[0])[:10], "%Y-%m-%d").date()
            days_ago = (today - activity_date).days
            
            activity = {
                'date': activity_date,
                'sport': row[1],
                'duration_min': _parse_duration_to_minutes(row[2]),
                'avg_hr': row[3],
                'calories': row[5],
                'training_effect': row[6]
            }
            
            if days_ago <= 7:
                last_7_days.append(activity)
            last_28_days.append(activity)
        
        # Calculate summaries
        def summarize(activities):
            if not activities:
                return {'count': 0, 'duration': 0, 'calories': 0}
            return {
                'count': len(activities),
                'duration': sum(a['duration_min'] or 0 for a in activities),
                'calories': sum(a['calories'] or 0 for a in activities),
                'avg_te': sum(a['training_effect'] or 0 for a in activities) / len(activities) if activities else 0
            }
        
        s7 = summarize(last_7_days)
        s28 = summarize(last_28_days)
        
        print(f"\n{'Metric':<25} {'Last 7 days':<15} {'Last 28 days'}")
        print("-" * 55)
        print(f"{'Activities':<25} {s7['count']:<15} {s28['count']}")
        print(f"{'Total Duration':<25} {s7['duration']:.0f} min{'':<7} {s28['duration']:.0f} min")
        print(f"{'Total Calories':<25} {s7['calories']:.0f}{'':<11} {s28['calories']:.0f}")
        print(f"{'Avg Training Effect':<25} {s7['avg_te']:.1f}{'':<12} {s28['avg_te']:.1f}")
        print(f"{'Weekly Avg Duration':<25} {s7['duration']:.0f} min{'':<7} {s28['duration']/4:.0f} min")
        
        # Sport breakdown
        print(f"\nSport breakdown (last 7 days):")
        sports = {}
        for a in last_7_days:
            sport = str(a['sport'])
            if sport not in sports:
                sports[sport] = {'count': 0, 'duration': 0}
            sports[sport]['count'] += 1
            sports[sport]['duration'] += a['duration_min'] or 0
        
        for sport, data in sorted(sports.items()):
            print(f"  {sport}: {data['count']} activities, {data['duration']:.0f} min")
            
    except Exception as e:
        print(f"Error: {e}")
    
    conn.close()


def _format_duration(time_str):
    """Format duration string to HH:MM."""
    if not time_str:
        return "-"
    parts = str(time_str).split(':')
    if len(parts) >= 2:
        return f"{parts[0]}:{parts[1]}"
    return str(time_str)[:5]


def _format_minutes(time_str):
    """Convert time string to minutes."""
    if not time_str:
        return "-"
    parts = str(time_str).split(':')
    if len(parts) >= 2:
        hours = int(parts[0])
        mins = int(parts[1])
        return f"{hours * 60 + mins}m"
    return str(time_str)


def _parse_duration_to_minutes(time_str):
    """Parse duration string to total minutes."""
    if not time_str:
        return 0
    try:
        parts = str(time_str).split(':')
        if len(parts) >= 2:
            hours = int(parts[0])
            mins = int(parts[1])
            return hours * 60 + mins
    except:
        pass
    return 0


if __name__ == "__main__":
    list_all_tables()
    show_recent_activities(10)
    show_vo2_max_summary()
    show_training_load_estimate()
    show_sleep_summary(7)
    show_resting_hr(14)
    show_daily_summary(7)
    show_monitoring_hr_sample()
