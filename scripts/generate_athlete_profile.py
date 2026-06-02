#!/usr/bin/env python3
"""
Generate athlete_profile.md with dynamic data from Garmin.
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime, timedelta
import statistics

PROJECT_DIR = Path(__file__).parent.parent
DB_DIR = PROJECT_DIR / 'data' / 'DBs'
FIT_DIR = PROJECT_DIR / 'data' / 'FitFiles'
COACH_DIR = PROJECT_DIR / 'coach'


def get_db(name):
    return sqlite3.connect(DB_DIR / name)


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
    if not seconds:
        return '-'
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def format_pace(pace_sec_km):
    if not pace_sec_km or pace_sec_km <= 0:
        return '-'
    m, s = divmod(int(pace_sec_km), 60)
    return f"{m}:{s:02d}"


def format_dur(seconds):
    if not seconds:
        return "-"
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, _ = divmod(rem, 60)
    return f"{h}h{m:02d}min" if h else f"{m}min"


def get_user_profile():
    """Get user profile from JSON files."""
    profile = {}
    
    pi_file = FIT_DIR / 'personal-information.json'
    if pi_file.exists():
        data = json.loads(pi_file.read_text(encoding='utf-8'))
        profile['birth_date'] = data.get('userInfo', {}).get('birthDate')
        bio = data.get('biometricProfile', {})
        profile['height_cm'] = bio.get('height')
        profile['weight_g'] = bio.get('weight')
        profile['vo2_max_run'] = bio.get('vo2Max')
        profile['lthr'] = bio.get('lactateThresholdHeartRate')
    
    # Get latest weight
    weight_dir = PROJECT_DIR / 'data' / 'Weight'
    if weight_dir.exists():
        weight_files = sorted(weight_dir.glob('weight_*.json'), reverse=True)
        for wf in weight_files:
            try:
                w_data = json.loads(wf.read_text(encoding='utf-8'))
                if w_data and 'dateWeightList' in w_data and w_data['dateWeightList']:
                    for entry in reversed(w_data['dateWeightList']):
                        if entry.get('weight'):
                            profile['weight_g'] = entry['weight']
                            break
                if profile.get('weight_g'):
                    break
            except:
                pass
    
    return profile


def get_all_running_activities():
    """Get ALL running activities from database."""
    conn = get_db('garmin_activities.db')
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


def find_best_performances(activities):
    """Find best performances at various distances."""
    best = {}
    
    distance_ranges = {
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


def get_recent_race_efforts(activities, count=10):
    """Get recent race-distance efforts."""
    races = []
    
    race_distances = [
        (5.0, '5K'),
        (10.0, '10K'),
        (15.0, '15K'),
        (21.1, 'Half Marathon'),
        (42.2, 'Marathon'),
    ]
    
    for act in activities:
        act_id, start, name, dist, elapsed, avg_hr, max_hr, cal, te, asc, desc, cad, avg_speed = act
        
        if not dist or not elapsed:
            continue
        
        elapsed_sec = parse_time(elapsed)
        if elapsed_sec <= 0:
            continue
        
        pace_sec_km = elapsed_sec / dist if dist > 0 else 0
        
        for target_dist, race_name in race_distances:
            if abs(dist - target_dist) / target_dist <= 0.05:
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
                    'elevation': asc
                })
                break
    
    return races[:count]


def calculate_training_paces(best_performances):
    """Calculate training paces from best race performance."""
    # Use HM or 10K as reference
    ref = best_performances.get('Half Marathon') or best_performances.get('10K')
    
    if not ref:
        return None
    
    # Estimate threshold pace from race pace
    # HM is roughly 95% of threshold, 10K is roughly 98%
    if 'Half Marathon' in best_performances and ref == best_performances['Half Marathon']:
        threshold_sec = ref['time_sec'] / ref['distance'] / 0.95
    else:
        threshold_sec = ref['time_sec'] / ref['distance'] / 0.98
    
    paces = {
        'easy': {'min': threshold_sec * 1.25, 'max': threshold_sec * 1.35},
        'long': {'min': threshold_sec * 1.15, 'max': threshold_sec * 1.25},
        'threshold': {'min': threshold_sec * 0.98, 'max': threshold_sec * 1.02},
        'interval': {'min': threshold_sec * 0.90, 'max': threshold_sec * 0.95},
        'repetition': {'min': threshold_sec * 0.82, 'max': threshold_sec * 0.88},
    }
    
    return paces


def analyze_training_volume(activities, months=12):
    """Analyze training volume trends."""
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
        
        if (now - date).days > months * 30:
            continue
        
        month_key = date.strftime('%Y-%m')
        
        if month_key not in monthly_data:
            monthly_data[month_key] = {'runs': 0, 'distance': 0, 'time': 0}
        
        monthly_data[month_key]['runs'] += 1
        monthly_data[month_key]['distance'] += dist or 0
        monthly_data[month_key]['time'] += parse_time(elapsed)
    
    return monthly_data


def calculate_age(birth_date_str):
    """Calculate age from birth date string."""
    try:
        birth = datetime.strptime(birth_date_str, '%Y-%m-%d')
        today = datetime.now()
        age = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
        return age
    except:
        return None


def generate():
    today = datetime.now().strftime('%d/%m/%Y')
    
    activities = get_all_running_activities()
    best = find_best_performances(activities)
    paces = calculate_training_paces(best)
    
    md = []
    md.append("# ATHLETE PROFILE")
    md.append(f"*Generated: {today}*")
    md.append("")
    md.append("This file contains historical performance data and calculated training paces.")
    md.append("Use this alongside coach_briefing.md (daily data) and goals.md (targets).")
    md.append("")
    
    # Personal Bests - the key reference for fitness level
    md.append("## PERSONAL BESTS")
    md.append("All-time best performances at standard race distances:")
    md.append("")
    if best:
        for dist_name in ['5K', '10K', '15K', 'Half Marathon', 'Marathon']:
            if dist_name in best:
                b = best[dist_name]
                md.append(f"- **{dist_name}**: {b['time_str']} ({b['pace_str']}/km) on {b['date']}")
    else:
        md.append("No race-distance performances found.")
    md.append("")
    
    # Training paces - the key output for planning
    if paces:
        md.append("## TRAINING PACES")
        md.append("Calculated from personal best performance:")
        md.append("")
        md.append(f"- **Easy**: {format_pace(paces['easy']['min'])}-{format_pace(paces['easy']['max'])}/km (recovery, base building)")
        md.append(f"- **Long Run**: {format_pace(paces['long']['min'])}-{format_pace(paces['long']['max'])}/km (endurance)")
        md.append(f"- **Threshold**: {format_pace(paces['threshold']['min'])}-{format_pace(paces['threshold']['max'])}/km (lactate threshold)")
        md.append(f"- **Interval**: {format_pace(paces['interval']['min'])}-{format_pace(paces['interval']['max'])}/km (VO2max)")
        md.append(f"- **Repetition**: {format_pace(paces['repetition']['min'])}-{format_pace(paces['repetition']['max'])}/km (speed)")
        md.append("")
    
    # Write
    out = '\n'.join(md)
    (COACH_DIR / 'athlete_profile.md').write_text(out, encoding='utf-8')
    print(f"[OK] {COACH_DIR / 'athlete_profile.md'}")


if __name__ == "__main__":
    generate()

