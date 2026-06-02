#!/usr/bin/env python3
"""
Parse FIT files directly for accurate training data.
"""

import sqlite3
import shutil
from pathlib import Path
from datetime import datetime, timedelta
import statistics
from fitparse import FitFile

PROJECT_DIR = Path(__file__).parent.parent
DB_DIR = PROJECT_DIR / 'data' / 'DBs'
FIT_DIR = PROJECT_DIR / 'data' / 'FitFiles' / 'Activities'
COACH_DIR = PROJECT_DIR / 'coach'
ARCHIVE_DIR = COACH_DIR / 'archive'


def db(name):
    return sqlite3.connect(DB_DIR / name)


def get_last_sync_time():
    """Get the last Garmin sync time from DB modification or sync log."""
    # Check sync log first
    log_dir = PROJECT_DIR / 'logs'
    if log_dir.exists():
        logs = sorted(log_dir.glob('sync_*.log'), reverse=True)
        if logs:
            # Get modification time of most recent sync log
            mtime = logs[0].stat().st_mtime
            return datetime.fromtimestamp(mtime)
    
    # Fallback: check DB modification time
    db_file = DB_DIR / 'garmin.db'
    if db_file.exists():
        mtime = db_file.stat().st_mtime
        return datetime.fromtimestamp(mtime)
    
    return None


def archive_old_briefing():
    """Archive the current briefing only if new data was synced since last generation."""
    briefing_file = COACH_DIR / 'coach_briefing.md'
    if not briefing_file.exists():
        return
    
    # Get last sync time
    sync_time = get_last_sync_time()
    if not sync_time:
        return
    
    # Get briefing modification time
    briefing_mtime = datetime.fromtimestamp(briefing_file.stat().st_mtime)
    
    # Only archive if sync happened after the briefing was last generated
    if sync_time <= briefing_mtime:
        return  # No new data, skip archive
    
    # Create archive directory if needed
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    
    # Use briefing modification time for archive name
    archive_date = briefing_mtime.strftime('%Y%m%d_%H%M%S')
    archive_file = ARCHIVE_DIR / f'coach_briefing_{archive_date}.md'
    
    # Only archive if not already archived
    if not archive_file.exists():
        shutil.copy2(briefing_file, archive_file)
        print(f"[ARCHIVED] {archive_file.name}")


def fmt_pace_sec(pace_sec):
    """pace in seconds per km -> mm:ss"""
    if not pace_sec or pace_sec <= 0:
        return "-"
    m, s = divmod(int(pace_sec), 60)
    return f"{m}:{s:02d}"


def fmt_pace(speed_ms):
    """speed in m/s -> pace as mm:ss/km"""
    if not speed_ms or speed_ms <= 0:
        return "-"
    pace_sec = 1000 / speed_ms
    return fmt_pace_sec(pace_sec)


def fmt_dur(seconds):
    """Format duration in seconds to human readable format.
    Uses 'min' for minutes to avoid confusion with meters (m).
    """
    if not seconds:
        return "-"
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, _ = divmod(rem, 60)
    return f"{h}h{m:02d}min" if h else f"{m}min"


def get_activity_fit_file(activity_id):
    """Find FIT file for activity."""
    fit_path = FIT_DIR / f"{activity_id}_ACTIVITY.fit"
    return fit_path if fit_path.exists() else None


def parse_fit_file(fit_path):
    """Parse FIT file and extract all record data."""
    fit = FitFile(str(fit_path))
    
    records = []
    laps = []
    session = {}
    
    for record in fit.get_messages():
        if record.name == 'record':
            data = {}
            for field in record.fields:
                data[field.name] = field.value
            if data.get('heart_rate') or data.get('speed'):
                records.append(data)
        
        elif record.name == 'lap':
            lap_data = {}
            for field in record.fields:
                lap_data[field.name] = field.value
            laps.append(lap_data)
        
        elif record.name == 'session':
            for field in record.fields:
                session[field.name] = field.value
    
    return {'records': records, 'laps': laps, 'session': session}


def get_hr_zone_boundaries(lthr):
    """Calculate HR zone boundaries based on LTHR (Friel standard zones).
    
    Friel zones for running:
    - Z1: Recovery (<85% LTHR)
    - Z2: Aerobic (85-89% LTHR)
    - Z3: Tempo (90-94% LTHR)
    - Z4: SubThreshold (95-99% LTHR)
    - Z5: SuperThreshold (100%+ LTHR)
    """
    return {
        'z1_max': int(lthr * 0.85),   # Z1: <85%
        'z2_max': int(lthr * 0.89),   # Z2: 85-89%
        'z3_max': int(lthr * 0.94),   # Z3: 90-94%
        'z4_max': int(lthr * 0.99),   # Z4: 95-99%
        # Z5: >99%
    }


def compute_hr_zones(records, lthr):
    """Compute time in each HR zone from FIT records using LTHR-based zones.
    
    Returns dict with zone times in seconds.
    """
    if not lthr or not records:
        return None
    
    bounds = get_hr_zone_boundaries(lthr)
    zone_times = {'z1': 0, 'z2': 0, 'z3': 0, 'z4': 0, 'z5': 0}
    
    # Calculate time interval between records (typically 1 second)
    prev_timestamp = None
    prev_hr_timestamp = None
    
    for r in records:
        hr = r.get('heart_rate')
        timestamp = r.get('timestamp')
        
        # Calculate time delta from previous HR record
        delta = 1  # Default 1 second
        if hr and timestamp and prev_hr_timestamp:
            try:
                delta = (timestamp - prev_hr_timestamp).total_seconds()
                # Allow full time between records (pauses, etc. still count)
                # Only reject negative deltas
                delta = max(delta, 0)
            except:
                delta = 1
        
        if hr:
            # Classify HR into zone
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
            
            prev_hr_timestamp = timestamp
    
    return zone_times


def analyze_fit_data(fit_data, lthr=None):
    """Analyze parsed FIT data.
    
    Args:
        fit_data: Parsed FIT file data
        lthr: Lactate threshold heart rate for zone calculation
    """
    records = fit_data['records']
    if not records:
        return None
    
    # Extract arrays - try enhanced_speed first (more accurate), fallback to speed
    hrs = [r['heart_rate'] for r in records if r.get('heart_rate')]
    speeds = [r.get('enhanced_speed') or r.get('speed') for r in records 
              if (r.get('enhanced_speed') or r.get('speed')) and (r.get('enhanced_speed') or r.get('speed')) > 0.5]
    cadences = [r['cadence'] * 2 for r in records if r.get('cadence')]  # FIT stores half cadence
    
    # Running dynamics (raw values from FIT)
    gcts = [r['stance_time'] for r in records if r.get('stance_time')]
    vos = [r['vertical_oscillation'] for r in records if r.get('vertical_oscillation')]
    strides = [r['step_length'] for r in records if r.get('step_length')]
    gct_bal = [r['stance_time_balance'] for r in records if r.get('stance_time_balance')]
    powers = [r['power'] for r in records if r.get('power')]
    
    result = {}
    
    # HR analysis
    if hrs:
        result['hr'] = {
            'avg': round(statistics.mean(hrs)),
            'max': max(hrs),
            'min': min(hrs),
            'stdev': round(statistics.stdev(hrs), 1) if len(hrs) > 1 else 0
        }
    
    # Compute HR zones from actual data using LTHR
    if lthr:
        hr_zones = compute_hr_zones(records, lthr)
        if hr_zones:
            result['hr_zones_computed'] = hr_zones
    
    # Pace analysis (speed is in m/s in FIT files)
    if speeds:
        paces = [1000 / s for s in speeds]  # seconds per km
        result['pace'] = {
            'avg': round(statistics.mean(paces)),  # seconds per km
            'best': round(min(paces)),
            'worst': round(max(paces)),
            'stdev': round(statistics.stdev(paces)) if len(paces) > 1 else 0
        }
        result['avg_speed'] = statistics.mean(speeds)  # m/s
        
        # Pace buckets (in seconds per km)
        buckets = {'<4:00': 0, '4:00-4:30': 0, '4:30-5:00': 0, '5:00-5:30': 0,
                   '5:30-6:00': 0, '6:00-6:30': 0, '6:30-7:00': 0, '>7:00': 0}
        for p in paces:
            if p < 240: buckets['<4:00'] += 1
            elif p < 270: buckets['4:00-4:30'] += 1
            elif p < 300: buckets['4:30-5:00'] += 1
            elif p < 330: buckets['5:00-5:30'] += 1
            elif p < 360: buckets['5:30-6:00'] += 1
            elif p < 390: buckets['6:00-6:30'] += 1
            elif p < 420: buckets['6:30-7:00'] += 1
            else: buckets['>7:00'] += 1
        result['pace_dist'] = {k: round(v/len(paces)*100) for k, v in buckets.items() if v > 0}
    
    # Cadence
    if cadences:
        result['cadence'] = {
            'avg': round(statistics.mean(cadences)),
            'max': max(cadences),
            'min': min(cadences)
        }
    
    # Running dynamics - FIT units: gct=ms, vo=mm, stride=mm
    dynamics = {}
    if gcts:
        dynamics['gct'] = round(statistics.mean(gcts))  # already in ms
    if vos:
        dynamics['vo'] = round(statistics.mean(vos) / 10, 1)  # mm -> cm
    if strides:
        dynamics['stride'] = round(statistics.mean(strides) / 1000, 2)  # mm -> m
    if gct_bal:
        dynamics['balance'] = round(statistics.mean(gct_bal), 1)  # %
    if powers:
        dynamics['power'] = round(statistics.mean(powers))  # W
        dynamics['power_max'] = max(powers)
    if dynamics:
        result['dynamics'] = dynamics
    
    return result


def analyze_laps(laps):
    """Analyze lap data from FIT."""
    if not laps:
        return []
    
    result = []
    for i, lap in enumerate(laps):
        dist = lap.get('total_distance', 0)  # meters
        time = lap.get('total_elapsed_time', 0)  # seconds
        hr = lap.get('avg_heart_rate', 0)
        # Try different cadence field names (FIT files vary)
        cadence = lap.get('avg_running_cadence') or lap.get('avg_cadence', 0)
        
        if time > 0 and dist > 0:
            pace_sec = time / (dist / 1000)  # sec per km
            m, s = divmod(int(pace_sec), 60)
            pace = f"{m}:{s:02d}"
        else:
            pace = "-"
        
        result.append({
            'lap': i + 1,
            'dist': dist,
            'time': time,
            'pace': pace,
            'hr': int(hr) if hr else 0,
            'cadence': int(cadence * 2) if cadence else 0  # Convert to full cadence
        })
    
    return result


def get_runs_from_db(days=30):
    """Get running activities metadata from DB."""
    conn = db('garmin_activities.db')
    rows = conn.execute(f"""
        SELECT activity_id, start_time, name, distance, elapsed_time, 
               avg_hr, max_hr, calories, training_effect, ascent, descent,
               avg_cadence, anaerobic_training_effect,
               hrz_1_time, hrz_2_time, hrz_3_time, hrz_4_time, hrz_5_time
        FROM activities
        WHERE sport = 'running' AND start_time >= date('now', '-{days} days')
        ORDER BY start_time DESC
    """).fetchall()
    conn.close()
    return rows


def get_health(days=14):
    conn = db('garmin.db')
    sleep = conn.execute(f"SELECT day, total_sleep, deep_sleep, rem_sleep, score FROM sleep ORDER BY day DESC LIMIT {days}").fetchall()
    rhr = conn.execute(f"SELECT day, resting_heart_rate FROM resting_hr ORDER BY day DESC LIMIT {days}").fetchall()
    daily = conn.execute(f"SELECT day, rhr, stress_avg, bb_max, bb_min FROM daily_summary ORDER BY day DESC LIMIT {days}").fetchall()
    conn.close()
    return {'sleep': sleep, 'rhr': rhr, 'daily': daily}


def get_other(days=30):
    conn = db('garmin_activities.db')
    rows = conn.execute(f"""
        SELECT start_time, sport, distance, elapsed_time, avg_hr, training_effect
        FROM activities WHERE sport != 'running' AND start_time >= date('now', '-{days} days')
        ORDER BY start_time DESC
    """).fetchall()
    conn.close()
    return rows


def get_hrv_data(days=7):
    """Get HRV data from sleep JSON files."""
    import json
    sleep_dir = PROJECT_DIR / 'data' / 'Sleep'
    hrv_data = []
    
    for i in range(days):
        date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
        sleep_file = sleep_dir / f'sleep_{date}.json'
        if sleep_file.exists():
            try:
                data = json.loads(sleep_file.read_text(encoding='utf-8'))
                hrv_status = data.get('hrvStatus')
                hrv_avg = data.get('avgOvernightHrv')
                dto = data.get('dailySleepDTO', {})
                sleep_score = dto.get('sleepScores', {}).get('overall', {}).get('value')
                rhr = data.get('restingHeartRate')
                
                if hrv_avg or sleep_score:
                    hrv_data.append({
                        'date': date,
                        'hrv': hrv_avg,
                        'hrv_status': hrv_status,
                        'sleep_score': sleep_score,
                        'rhr': rhr
                    })
            except:
                pass
    
    return hrv_data


def parse_time(t):
    if not t:
        return 0
    p = str(t).split(':')
    if len(p) >= 3:
        return int(p[0]) * 3600 + int(p[1]) * 60 + int(float(p[2]))
    if len(p) == 2:
        return int(p[0]) * 60 + int(p[1])
    return 0


def generate():
    # Archive old briefing before generating new one
    archive_old_briefing()
    
    today = datetime.now().strftime('%d/%m/%Y')
    now = datetime.now().strftime('%d/%m/%Y %H:%M')
    
    # Get last sync time
    sync_time = get_last_sync_time()
    sync_str = sync_time.strftime('%d/%m/%Y %H:%M') if sync_time else 'Unknown'
    
    runs = get_runs_from_db(30)
    health = get_health(14)
    other = get_other(30)
    
    md = []
    md.append(f"# RUNNING DATA [{today}]")
    md.append(f"*Generated: {now} | Last Garmin sync: {sync_str}*")
    md.append("")
    
    # User profile from settings
    md.append("## PROFILE")
    lthr = None  # Will be set from user settings if available
    try:
        import json
        
        # Get latest weight from Weight folder
        weight_dir = PROJECT_DIR / 'data' / 'Weight'
        latest_weight = None
        weight_date = None
        if weight_dir.exists():
            weight_files = sorted(weight_dir.glob('weight_*.json'), reverse=True)
            for wf in weight_files:
                try:
                    w_data = json.loads(wf.read_text(encoding='utf-8'))
                    if w_data and 'dateWeightList' in w_data and w_data['dateWeightList']:
                        for entry in reversed(w_data['dateWeightList']):
                            if entry.get('weight'):
                                latest_weight = entry['weight'] / 1000  # grams to kg
                                weight_date = entry.get('date')
                                break
                    if latest_weight:
                        break
                except:
                    pass
        
        # Height from personal info JSON
        pi_file = PROJECT_DIR / 'data' / 'FitFiles' / 'personal-information.json'
        height_cm = 183  # fallback
        if pi_file.exists():
            try:
                pi_data = json.loads(pi_file.read_text(encoding='utf-8'))
                height_raw = pi_data.get('biometricProfile', {}).get('height')
                if height_raw:
                    height_cm = int(height_raw)
            except:
                pass
        
        # Format weight/height line
        weight_str = f"{latest_weight:.1f}kg" if latest_weight else "-"
        md.append(f"Weight: {weight_str} | Height: {height_cm}cm")
        
        settings = json.loads((PROJECT_DIR / 'data' / 'FitFiles' / 'user-settings.json').read_text())
        ud = settings.get('userData', {})
        lthr = ud.get('lactateThresholdHeartRate')
        vo2_run = ud.get('vo2MaxRunning')
        vo2_bike = ud.get('vo2MaxCycling')
        
        # Fallback to database for VO2max if not in user settings
        if not vo2_bike:
            try:
                conn = db('garmin_activities.db')
                row = conn.execute('SELECT vo2_max FROM cycle_activities WHERE vo2_max IS NOT NULL ORDER BY activity_id DESC LIMIT 1').fetchone()
                conn.close()
                if row:
                    vo2_bike = row[0]
            except:
                pass
        if not vo2_run:
            try:
                conn = db('garmin_activities.db')
                row = conn.execute('SELECT vo2_max FROM steps_activities WHERE vo2_max IS NOT NULL ORDER BY activity_id DESC LIMIT 1').fetchone()
                conn.close()
                if row:
                    vo2_run = row[0]
            except:
                pass
        
        vo2_run_str = f"{vo2_run:.1f}" if vo2_run else "-"
        vo2_bike_str = f"{vo2_bike:.1f}" if vo2_bike else "-"
        lthr_str = str(lthr) if lthr else "-"
        md.append(f"LTHR: {lthr_str} | VO2maxRUN: {vo2_run_str} | VO2maxBIKE: {vo2_bike_str}")
        
        # HR Zone explanation based on LTHR (Friel standard zones)
        if lthr:
            bounds = get_hr_zone_boundaries(lthr)
            md.append(f"HR Zones: Z1:<{bounds['z1_max']} | Z2:{bounds['z1_max']}-{bounds['z2_max']} | Z3:{bounds['z2_max']+1}-{bounds['z3_max']} | Z4:{bounds['z3_max']+1}-{bounds['z4_max']} | Z5:>{bounds['z4_max']}")
    except:
        pass
    md.append("")
    
    # Recovery signals: HRV | Sleep Score | RHR
    md.append("## RECOVERY (14d)")
    hrv_data = get_hrv_data(14)
    if hrv_data:
        # Daily breakdown (compact) - HRV/Sleep/RHR for each day
        def fmt_date(d):
            parts = d.split('-')
            return f"{parts[2]}/{parts[1]}"
        
        daily = []
        for d in hrv_data[:14]:
            hrv = f"{int(d['hrv'])}" if d.get('hrv') else "-"
            sleep = f"{d['sleep_score']}" if d.get('sleep_score') else "-"
            rhr = f"{d['rhr']}" if d.get('rhr') else "-"
            daily.append(f"{fmt_date(d['date'])}:{hrv}/{sleep}/{rhr}")
        md.append(f"HRV/Sleep/RHR: {' '.join(daily)}")
    else:
        md.append("No HRV data available")
    md.append("")
    
    # Status
    md.append("## CURRENT STATUS")
    # Read from JSON files for latest data (not database which may be stale)
    import json
    today_str = datetime.now().strftime('%Y-%m-%d')
    yesterday_str = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    # Try to get latest daily summary from JSON
    monitoring_dir = PROJECT_DIR / 'data' / 'FitFiles' / 'Monitoring'
    daily_json = None
    for date_str in [today_str, yesterday_str]:
        year = date_str[:4]
        summary_file = monitoring_dir / year / f'daily_summary_{date_str}.json'
        if summary_file.exists():
            daily_json = json.loads(summary_file.read_text(encoding='utf-8'))
            break
    
    # Try to get latest sleep from JSON
    sleep_dir = PROJECT_DIR / 'data' / 'Sleep'
    sleep_json = None
    for date_str in [today_str, yesterday_str]:
        sleep_file = sleep_dir / f'sleep_{date_str}.json'
        if sleep_file.exists():
            sleep_json = json.loads(sleep_file.read_text(encoding='utf-8'))
            break
    
    # RHR - from daily summary JSON or database fallback
    if daily_json:
        rhr_today = daily_json.get('restingHeartRate')
        rhr_7d = daily_json.get('lastSevenDaysAvgRestingHeartRate')
        if rhr_today:
            if rhr_7d:
                md.append(f"RHR: {rhr_today} (7d avg: {rhr_7d})")
            else:
                md.append(f"RHR: {rhr_today}")
    elif health['rhr'] and health['rhr'][0][1]:
        rhr_vals = [r[1] for r in health['rhr'] if r[1]]
        if len(rhr_vals) > 1:
            md.append(f"RHR: {rhr_vals[0]:.0f} (14d: {statistics.mean(rhr_vals):.0f}+/-{statistics.stdev(rhr_vals):.1f})")
        else:
            md.append(f"RHR: {rhr_vals[0]:.0f}")
    
    # Sleep - from sleep JSON
    if sleep_json:
        dto = sleep_json.get('dailySleepDTO', {})
        total_sec = dto.get('sleepTimeSeconds', 0)
        deep_sec = dto.get('deepSleepSeconds', 0)
        rem_sec = dto.get('remSleepSeconds', 0)
        score = dto.get('sleepScores', {}).get('overall', {}).get('value')
        md.append(f"Sleep: {fmt_dur(total_sec)} deep:{fmt_dur(deep_sec)} rem:{fmt_dur(rem_sec)} score:{score or '-'}")
    elif health['sleep'] and health['sleep'][0]:
        s = health['sleep'][0]
        md.append(f"Sleep: {fmt_dur(parse_time(s[1]))} deep:{fmt_dur(parse_time(s[2]))} rem:{fmt_dur(parse_time(s[3]))} score:{s[4]}")
    
    # Stress & Body Battery - from daily summary JSON
    if daily_json:
        stress = daily_json.get('averageStressLevel')
        bb_max = daily_json.get('bodyBatteryHighestValue')
        bb_min = daily_json.get('bodyBatteryLowestValue')
        stress_str = f"{stress:.0f}" if stress else "-"
        bb_str = f"{bb_max}/{bb_min}" if bb_max else "-"
        md.append(f"Stress: {stress_str} | BB: {bb_str}")
    elif health['daily'] and health['daily'][0]:
        d = health['daily'][0]
        md.append(f"Stress: {d[2]} | BB: {d[3]}/{d[4]}")
    md.append("")
    
    # Load summary
    md.append("## LOAD (30d)")
    acute = len([r for r in runs if str(r[1])[:10] >= (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')])
    total_dist = sum(r[3] or 0 for r in runs)
    total_time = sum(parse_time(r[4]) for r in runs)
    md.append(f"Runs: {len(runs)} | Distance: {total_dist:.1f}km | Time: {fmt_dur(total_time)}")
    md.append(f"7d: {acute} runs | 28d avg: {len(runs)/4:.1f}/week")
    md.append("")
    
    # Each run with FIT file analysis
    md.append("## RUNS")
    for r in runs:
        act_id, start, name, dist, elapsed, avg_hr, max_hr, cal, te, asc, desc, cad, ate, hrz1, hrz2, hrz3, hrz4, hrz5 = r
        
        # Convert date to DD/MM/YYYY
        start_str = str(start)[:10]
        if '-' in start_str:
            y, m, d = start_str.split('-')
            start_fmt = f"{d}/{m}/{y}"
        else:
            start_fmt = start_str
        md.append(f"### {start_fmt} {name}")
        
        # Try to get FIT file
        fit_path = get_activity_fit_file(act_id)
        
        if fit_path:
            try:
                fit_data = parse_fit_file(fit_path)
                analysis = analyze_fit_data(fit_data, lthr)
                
                # Basic info - prefer calculated from records
                sess = fit_data['session']
                total_dist_m = sess.get('total_distance', dist * 1000)
                total_time_s = sess.get('total_elapsed_time', parse_time(elapsed))
                
                # Get pace from analysis, session, or calculate from distance/time
                if analysis and 'avg_speed' in analysis:
                    pace_str = fmt_pace(analysis['avg_speed'])
                elif sess.get('avg_speed'):
                    pace_str = fmt_pace(sess['avg_speed'])
                elif sess.get('enhanced_avg_speed'):
                    pace_str = fmt_pace(sess['enhanced_avg_speed'])
                elif total_dist_m > 0 and total_time_s > 0:
                    # Calculate from distance/time
                    avg_speed_calc = total_dist_m / total_time_s  # m/s
                    pace_str = fmt_pace(avg_speed_calc)
                else:
                    pace_str = "-"
                
                md.append(f"dist:{total_dist_m/1000:.2f}km dur:{fmt_dur(total_time_s)} pace:{pace_str}/km")
                
                # HR and TE
                hr_avg = sess.get('avg_heart_rate') or avg_hr
                hr_max = sess.get('max_heart_rate') or max_hr
                te_str = f"te:{te:.1f}" if te else ""
                ate_str = f"/{ate:.1f}" if ate else ""
                md.append(f"HR: avg {hr_avg} | max {hr_max} | {te_str}{ate_str} cal:{cal}")
                
                if asc and asc > 20:
                    md.append(f"elev:+{asc:.0f}/-{desc:.0f}m")
                
                # Detailed analysis from records
                if analysis:
                    # Use computed HR zone times from FIT data (LTHR-based)
                    if 'hr_zones_computed' in analysis:
                        hz = analysis['hr_zones_computed']
                        md.append(f"HR Zones: Z1:{fmt_dur(hz['z1'])} | Z2:{fmt_dur(hz['z2'])} | Z3:{fmt_dur(hz['z3'])} | Z4:{fmt_dur(hz['z4'])} | Z5:{fmt_dur(hz['z5'])}")
                    
                    
                    
                    
                    
                    # Running dynamics
                    if 'dynamics' in analysis:
                        d = analysis['dynamics']
                        dyn_parts = []
                        if 'gct' in d: dyn_parts.append(f"gct:{d['gct']}ms")
                        if 'vo' in d: dyn_parts.append(f"vo:{d['vo']}cm")
                        if 'stride' in d: dyn_parts.append(f"stride:{d['stride']}m")
                        if 'balance' in d: dyn_parts.append(f"bal:{d['balance']}%")
                        if 'power' in d: dyn_parts.append(f"pwr:{d['power']}W")
                        if dyn_parts:
                            md.append(f"Dynamics: {' '.join(dyn_parts)}")
                    
                
                # Laps - #: dist pace HR:x cad:y | format
                laps = analyze_laps(fit_data['laps'])
                if laps and len(laps) > 1:
                    def fmt_lap(l):
                        dist = l['dist']
                        # Show in m or km depending on distance
                        dist_str = f"{int(dist)}m" if dist < 1000 else f"{dist/1000:.2f}km"
                        cad_str = f" cad:{l['cadence']}" if l.get('cadence') else ""
                        return f"{l['lap']}:{dist_str} {l['pace']} HR:{l['hr']}{cad_str}"
                    lap_strs = [fmt_lap(l) for l in laps]
                    md.append(f"Laps: {' | '.join(lap_strs)}")
                
            except Exception as e:
                # Fallback to DB data
                md.append(f"dist:{dist:.2f}km dur:{elapsed} hr:{avg_hr}/{max_hr} te:{te}")
                md.append(f"[FIT error: {e}]")
        else:
            # No FIT file, use DB data
            md.append(f"dist:{dist:.2f}km dur:{elapsed} hr:{avg_hr}/{max_hr} te:{te} cal:{cal}")
            if asc and asc > 20:
                md.append(f"elev:+{asc:.0f}/-{desc:.0f}m")
            md.append("[no FIT file]")
        
        md.append("")
    
    # Other activities
    if other:
        md.append("## OTHER")
        for o in other:
            o_date = str(o[0])[:10]
            if '-' in o_date:
                y, m, d = o_date.split('-')
                o_date = f"{d}/{m}/{y}"
            te_val = f"{o[5]:.1f}" if o[5] else "-"
            md.append(f"{o_date} {o[1]}: {o[2]:.1f}km {fmt_dur(parse_time(o[3]))} HR:{int(o[4]) if o[4] else '-'} TE:{te_val}")
        md.append("")
    
    # Write
    out = '\n'.join(md)
    (COACH_DIR / 'coach_briefing.md').write_text(out, encoding='utf-8')
    print(f"[OK] {COACH_DIR / 'coach_briefing.md'}")


if __name__ == "__main__":
    generate()
