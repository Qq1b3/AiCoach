#!/usr/bin/env python3
"""
Analyze training history to extract race performances and training trends.
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime, timedelta
import statistics

PROJECT_DIR = Path(__file__).parent.parent
DB_DIR = PROJECT_DIR / 'data' / 'DBs'
FIT_DIR = PROJECT_DIR / 'data' / 'FitFiles'


def get_db(name):
    return sqlite3.connect(DB_DIR / name)


def get_user_profile():
    """Get user profile from JSON files."""
    profile = {}
    
    # Personal info
    pi_file = FIT_DIR / 'personal-information.json'
    if pi_file.exists():
        data = json.loads(pi_file.read_text(encoding='utf-8'))
        profile['birth_date'] = data.get('userInfo', {}).get('birthDate')
        bio = data.get('biometricProfile', {})
        profile['height_cm'] = bio.get('height')
        profile['weight_g'] = bio.get('weight')
        profile['vo2_max_run'] = bio.get('vo2Max')
        profile['lthr'] = bio.get('lactateThresholdHeartRate')
    
    # User settings
    settings_file = FIT_DIR / 'user-settings.json'
    if settings_file.exists():
        data = json.loads(settings_file.read_text(encoding='utf-8'))
        ud = data.get('userData', {})
        profile['lt_speed_ms'] = ud.get('lactateThresholdSpeed')  # m/s
        
    return profile


def get_all_running_activities():
    """Get ALL running activities from database."""
    conn = get_db('garmin_activities.db')
    
    # Get table structure first
    cursor = conn.execute("PRAGMA table_info(activities)")
    columns = [col[1] for col in cursor.fetchall()]
    print(f"Available columns: {columns}")
    
    # Get all running activities
    rows = conn.execute("""
        SELECT activity_id, start_time, name, distance, elapsed_time, 
               avg_hr, max_hr, calories, training_effect, ascent, descent,
               avg_cadence, avg_speed
        FROM activities
        WHERE sport = 'running'
        ORDER BY start_time DESC
    """).fetchall()
    conn.close()
    
    return rows


def analyze_race_performances(activities):
    """Identify potential race performances (fast efforts at standard distances)."""
    races = []
    
    for act in activities:
        act_id, start, name, dist, elapsed, avg_hr, max_hr, cal, te, asc, desc, cad, avg_speed = act
        
        if not dist or not elapsed:
            continue
            
        # Parse elapsed time
        elapsed_sec = parse_time(elapsed)
        if elapsed_sec <= 0:
            continue
        
        # Calculate pace
        pace_sec_km = elapsed_sec / dist if dist > 0 else 0
        
        # Distance categories (in km)
        name_lower = (name or '').lower()
        
        # Check for known race keywords
        is_race = any(kw in name_lower for kw in ['race', 'marathon', 'parkrun', 'halfmarathon', '10k', '5k', 'competition', 'závod'])
        
        # Standard race distances (+/- 5%)
        race_distances = [
            (5.0, '5K'),
            (10.0, '10K'),
            (15.0, '15K'),
            (21.1, 'Half Marathon'),
            (42.2, 'Marathon'),
        ]
        
        for target_dist, race_name in race_distances:
            if abs(dist - target_dist) / target_dist <= 0.05:  # Within 5%
                races.append({
                    'date': str(start)[:10],
                    'name': name,
                    'distance': dist,
                    'distance_category': race_name,
                    'time_sec': elapsed_sec,
                    'time_str': format_time(elapsed_sec),
                    'pace_sec_km': pace_sec_km,
                    'pace_str': format_pace(pace_sec_km),
                    'avg_hr': avg_hr,
                    'max_hr': max_hr,
                    'is_likely_race': is_race,
                    'elevation': asc
                })
                break
    
    return races


def analyze_training_volume(activities, months=12):
    """Analyze training volume trends over time."""
    now = datetime.now()
    
    monthly_data = {}
    
    for act in activities:
        act_id, start, name, dist, elapsed, avg_hr, max_hr, cal, te, asc, desc, cad, avg_speed = act
        
        if not start:
            continue
            
        date_str = str(start)[:10]
        try:
            date = datetime.strptime(date_str, '%Y-%m-%d')
        except:
            continue
        
        # Only last N months
        if (now - date).days > months * 30:
            continue
        
        month_key = date.strftime('%Y-%m')
        
        if month_key not in monthly_data:
            monthly_data[month_key] = {'runs': 0, 'distance': 0, 'time': 0}
        
        monthly_data[month_key]['runs'] += 1
        monthly_data[month_key]['distance'] += dist or 0
        monthly_data[month_key]['time'] += parse_time(elapsed)
    
    return monthly_data


def calculate_current_fitness_paces(profile, recent_runs):
    """Estimate current training paces based on LTHR and recent performance."""
    paces = {}
    
    lthr = profile.get('lthr')
    lt_speed = profile.get('lt_speed_ms')
    
    if lt_speed:
        # Lactate threshold pace from Garmin
        lt_pace_sec = 1000 / lt_speed  # sec per km
        paces['threshold'] = {
            'pace_sec_km': lt_pace_sec,
            'pace_str': format_pace(lt_pace_sec),
            'source': 'Garmin LT detection'
        }
        
        # Derive other paces from threshold
        # Easy: 65-75% of threshold effort (~25-35% slower)
        paces['easy'] = {
            'pace_sec_km': lt_pace_sec * 1.30,
            'pace_str': format_pace(lt_pace_sec * 1.30),
            'source': 'Derived from LT (30% slower)'
        }
        
        # Long: 70-80% of threshold effort (~20-30% slower)
        paces['long'] = {
            'pace_sec_km': lt_pace_sec * 1.25,
            'pace_str': format_pace(lt_pace_sec * 1.25),
            'source': 'Derived from LT (25% slower)'
        }
        
        # Interval (VO2max): 95-100% of threshold effort (~5% faster)
        paces['interval'] = {
            'pace_sec_km': lt_pace_sec * 0.95,
            'pace_str': format_pace(lt_pace_sec * 0.95),
            'source': 'Derived from LT (5% faster)'
        }
        
        # Repetition: 105-110% sprint efforts
        paces['repetition'] = {
            'pace_sec_km': lt_pace_sec * 0.88,
            'pace_str': format_pace(lt_pace_sec * 0.88),
            'source': 'Derived from LT (12% faster)'
        }
    
    return paces


def find_best_performances(activities):
    """Find best performances at various distances."""
    best = {}
    
    distance_ranges = {
        '1K': (0.9, 1.1),
        '5K': (4.8, 5.2),
        '10K': (9.5, 10.5),
        '15K': (14.5, 15.5),
        'Half Marathon': (20.5, 21.5),
        'Marathon': (41.5, 43),
    }
    
    for act in activities:
        act_id, start, name, dist, elapsed, avg_hr, max_hr, cal, te, asc, desc, cad, avg_speed = act
        
        if not dist or not elapsed:
            continue
        
        elapsed_sec = parse_time(elapsed)
        if elapsed_sec <= 0:
            continue
        
        for dist_name, (min_d, max_d) in distance_ranges.items():
            if min_d <= dist <= max_d:
                # Check for flat terrain (less than 50m elevation gain)
                is_flat = not asc or asc < 50
                
                if dist_name not in best or elapsed_sec < best[dist_name]['time_sec']:
                    best[dist_name] = {
                        'date': str(start)[:10],
                        'name': name,
                        'distance': dist,
                        'time_sec': elapsed_sec,
                        'time_str': format_time(elapsed_sec),
                        'pace_str': format_pace(elapsed_sec / dist),
                        'avg_hr': avg_hr,
                        'elevation': asc,
                        'is_flat': is_flat
                    }
    
    return best


def parse_time(t):
    if not t:
        return 0
    p = str(t).split(':')
    if len(p) >= 3:
        return int(p[0]) * 3600 + int(p[1]) * 60 + int(float(p[2]))
    if len(p) == 2:
        return int(p[0]) * 60 + int(p[1])
    return 0


def format_time(seconds):
    """Format seconds to HH:MM:SS or MM:SS."""
    if not seconds:
        return '-'
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def format_pace(pace_sec_km):
    """Format pace in sec/km to MM:SS."""
    if not pace_sec_km or pace_sec_km <= 0:
        return '-'
    m, s = divmod(int(pace_sec_km), 60)
    return f"{m}:{s:02d}"


def format_dur(seconds):
    """Format duration."""
    if not seconds:
        return "-"
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, _ = divmod(rem, 60)
    return f"{h}h{m:02d}min" if h else f"{m}min"


def main():
    print("=" * 60)
    print("TRAINING HISTORY ANALYSIS")
    print("=" * 60)
    
    # Get profile
    profile = get_user_profile()
    print("\n--- USER PROFILE ---")
    print(f"Birth Date: {profile.get('birth_date')}")
    print(f"Height: {profile.get('height_cm')}cm")
    print(f"Weight: {(profile.get('weight_g') or 0)/1000:.1f}kg")
    print(f"VO2max (Run): {profile.get('vo2_max_run')}")
    print(f"LTHR: {profile.get('lthr')}")
    if profile.get('lt_speed_ms'):
        lt_pace = 1000 / profile['lt_speed_ms']
        print(f"LT Pace: {format_pace(lt_pace)}/km ({profile['lt_speed_ms']:.3f} m/s)")
    
    # Get all activities
    activities = get_all_running_activities()
    print(f"\n--- FOUND {len(activities)} RUNNING ACTIVITIES ---")
    
    # Best performances
    best = find_best_performances(activities)
    print("\n--- BEST PERFORMANCES (All Time) ---")
    for dist_name in ['5K', '10K', '15K', 'Half Marathon', 'Marathon']:
        if dist_name in best:
            b = best[dist_name]
            flat_str = " (flat)" if b['is_flat'] else f" (+{b['elevation']:.0f}m)"
            print(f"{dist_name}: {b['time_str']} @ {b['pace_str']}/km on {b['date']}{flat_str}")
    
    # Race performances
    races = analyze_race_performances(activities)
    print(f"\n--- RACE-DISTANCE EFFORTS ({len(races)} found) ---")
    for r in races[:10]:  # Top 10 most recent
        race_indicator = " [RACE]" if r['is_likely_race'] else ""
        print(f"{r['date']} {r['distance_category']}: {r['time_str']} @ {r['pace_str']}/km{race_indicator}")
    
    # Training paces
    paces = calculate_current_fitness_paces(profile, activities[:30])
    print("\n--- CALCULATED TRAINING PACES ---")
    for name, pace in paces.items():
        print(f"{name.capitalize()}: {pace['pace_str']}/km ({pace['source']})")
    
    # Volume trends
    monthly = analyze_training_volume(activities, 12)
    print("\n--- MONTHLY VOLUME (Last 12 months) ---")
    for month in sorted(monthly.keys(), reverse=True)[:6]:
        m = monthly[month]
        print(f"{month}: {m['runs']} runs, {m['distance']:.1f}km, {format_dur(m['time'])}")
    
    # Weekly peak volume
    print("\n--- TRAINING CONSISTENCY ---")
    total_runs = len(activities)
    if activities:
        first_run = str(activities[-1][1])[:10]
        last_run = str(activities[0][1])[:10]
        print(f"Training period: {first_run} to {last_run}")
        print(f"Total runs: {total_runs}")
        
        # Calculate weeks
        try:
            start = datetime.strptime(first_run, '%Y-%m-%d')
            end = datetime.strptime(last_run, '%Y-%m-%d')
            weeks = max(1, (end - start).days / 7)
            print(f"Avg runs/week: {total_runs/weeks:.1f}")
        except:
            pass


if __name__ == "__main__":
    main()
