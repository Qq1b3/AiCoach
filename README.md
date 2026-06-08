# AiCoach

Pull your own Garmin Connect data (activities, sleep, RHR, weight, daily monitoring, plus raw FIT files) into a local SQLite DB for analysis, and push structured workouts back the other way — design a session from the weekly plan and upload it straight to your Garmin calendar. The data side is a wrapper around [GarminDB](https://github.com/tcgoetz/GarminDB); the upload side talks to Garmin Connect directly. Everything runs locally with your own account, and your credentials and data never leave your machine or get committed.

## Requirements

- Python 3.12 or newer (garmindb 3.8.0 needs it). Check with `python --version`.
- A Garmin Connect account.

## Setup

```powershell
git clone https://github.com/Qq1b3/AiCoach.git
cd AiCoach

python -m venv venv
.\venv\Scripts\Activate.ps1            # POSIX: source venv/bin/activate
pip install -r requirements.txt

python scripts/setup_config.py         # enter your Garmin email/password, logs in once (asks for a 2FA code if you use one)
python scripts/test_connection.py      # verify / refresh the cached login token
python scripts/run_sync.py --initial   # full history download
```

Login goes through the `garminconnect` (curl_cffi) backend. After the first login your session token is cached in `~/.GarminDb/garmin_tokens.json` and refreshed automatically, so day-to-day syncs don't need your password or another 2FA code.

## Sync commands

| Command | Action |
| --- | --- |
| `python scripts/run_sync.py --initial` | Full historical download |
| `python scripts/run_sync.py --latest`  | Incremental update (daily) |
| `python scripts/run_sync.py --all`     | Re-download everything (overwrite) |
| `python scripts/run_sync.py --stats`   | Show what's in the local DB |

Add `--profile` or `--briefing` to also generate the coach outputs in `coach/`.

## Design and upload workouts

The other direction: build a structured workout from the weekly plan, upload it to Garmin Connect, and have it land on your calendar ready to sync to your watch. It reuses the same cached-token login as the sync, so there's no extra setup.

Targets follow the coach's hybrid rule — **HR caps on easy/recovery effort, pace windows on quality reps**. Every HR and pace number comes from `coach/thresholds.json` (the machine-readable mirror of `coach/lab_tests.md`), so thresholds live in exactly one place. Workout dates are computed from the ISO week number, never hardcoded.

```powershell
python scripts/upload_workout.py                                # dry-run: render the current week, nothing sent
python scripts/upload_workout.py --week 24                      # render a specific ISO week
python scripts/upload_workout.py --verify                       # round-trip test the encoding, then self-clean
python scripts/upload_workout.py --week 24 --upload             # upload to the Connect library (no calendar)
python scripts/upload_workout.py --week 24 --upload --schedule  # upload AND place on the calendar
```

After scheduling, sync your watch (or hit **Send to Device** in the app) to pull the workouts down.

| Script | Role |
| --- | --- |
| `scripts/upload_workout.py` | Build a week's sessions and upload/schedule them |
| `scripts/garmin_workouts.py` | Workout builder engine (steps, repeats, pace/HR targets) |
| `scripts/dump_workout.py` | Read existing Connect workouts to JSON (schema reference) |
| `scripts/thresholds.py` | Loader for `coach/thresholds.json` |

The workout JSON was reverse-engineered from real workouts already in the account (run `dump_workout.py` to see them), so generated sessions render on the watch exactly like hand-built ones. Uploads are name-prefixed (`CW24 Tue - Easy`, etc.) so they coexist with anything a human coach adds — the tool never edits or deletes workouts it didn't create.

> Note: like the data sync, the upload uses Garmin's private web API (not the partner-only Training API). It works well for personal use but is unofficial and could change if Garmin alters their endpoints.

## Where things live

- Password: OS credential manager (`keyring`, service `GarminConnect`), encrypted.
- Session token: `~/.GarminDb/garmin_tokens.json`.
- Email and config: `~/.GarminDb/GarminConnectConfig.json`.
- Data and FIT files: `data/` (git-ignored).
- Training thresholds (HR/pace): `coach/thresholds.json`, the machine-readable mirror of `coach/lab_tests.md`.

Each person runs `setup_config.py` with their own credentials. None of that lives in the repo; the `.gitignore` keeps all data and credentials out of git.

## Automated sync (Windows, optional)

```powershell
# Admin PowerShell
python scripts/setup_scheduler.py --create --time 07:00   # also: --status / --run / --delete
```

## Notes

- `garmindb` is pinned to `3.8.0` in `requirements.txt`. Older versions shipped `garth 0.5.19`, which Garmin's current login flow rejects with a `401`.
- If a sync fails with an auth error, the cached token probably expired. Re-run `python scripts/test_connection.py` to refresh it.
- If login still fails, double-check your credentials, complete the 2FA step, or sign in once on the Garmin website and try again. Garmin rate-limits repeated logins.
