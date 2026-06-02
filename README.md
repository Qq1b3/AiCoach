# AiCoach

Download your own [Garmin Connect](https://connect.garmin.com) health and activity
data to a local SQLite database (and raw FIT files) for analysis. Built on top of
[GarminDB](https://github.com/tcgoetz/GarminDB).

Everything runs **locally on your machine** with **your own** Garmin account. Your
credentials and health data never leave your computer and are never committed to git.

---

## What you get

- A local copy of your Garmin data: activities, sleep, resting HR, weight, daily
  monitoring, and per-activity FIT files (heart-rate streams, laps, etc.).
- Simple sync commands for first-time download and daily updates.
- Optional Windows scheduled tasks to keep the data fresh automatically.
- Optional coaching scripts that turn the data into a training profile/briefing.

---

## Prerequisites

- **Python 3.10 or newer** — check with `python --version`.
- **Git** — to clone this repo.
- A **Garmin Connect** account (email + password).

---

## Setup (Windows / PowerShell)

From the folder where you want the project to live:

```powershell
# 1. Get the code
git clone <REPO_URL> AiCoach
cd AiCoach

# 2. Create and activate a virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1
#   If activation is blocked by execution policy, run this first (current session only):
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# 3. Install dependencies (this pulls in GarminDB from PyPI)
pip install -r requirements.txt

# 4. Enter YOUR Garmin credentials (stored locally, see "Where your data lives")
python scripts/setup_config.py

# 5. Verify the connection works
python scripts/test_connection.py

# 6. First-time full download (this can take a while)
python scripts/run_sync.py --initial
```

> **macOS / Linux:** the steps are identical except activate with
> `source venv/bin/activate` instead of step 2's activate command.

---

## Daily use

| Command | What it does |
| --- | --- |
| `python scripts/run_sync.py --initial` | First-time full download of all history. |
| `python scripts/run_sync.py --latest`  | Incremental update — fetch the newest data (use this daily). |
| `python scripts/run_sync.py --all`     | Re-download **everything** with overwrite (rarely needed). |
| `python scripts/run_sync.py --stats`   | Show what's currently in your local database. |

Run these from the project root with the venv activated.

---

## Where your data lives

| What | Location | In git? |
| --- | --- | --- |
| Garmin email + config | `~/.GarminDb/GarminConnectConfig.json` | No (outside the repo) |
| Garmin password | OS credential manager (via `keyring`) | No |
| Health data & FIT files | `data/` inside this project | **No — git-ignored** |
| Sync logs | `logs/` | **No — git-ignored** |

The `.gitignore` is configured so that **no personal data or credentials are ever
committed**. Only code, templates, and docs are shared.

---

## Automatic syncing (optional, Windows)

To run `--latest` automatically on a schedule, create a Windows scheduled task:

```powershell
# Run from an Administrator PowerShell
python scripts/setup_scheduler.py --create --time 07:00
```

Useful management commands:

```powershell
python scripts/setup_scheduler.py --status   # show the task
python scripts/setup_scheduler.py --run      # run it now
python scripts/setup_scheduler.py --delete   # remove it
```

(`setup_scheduler.ps1` is an alternative that creates three daily syncs; run it from
an Administrator PowerShell.)

---

## Optional: coaching outputs

After syncing, you can generate training summaries from your data:

```powershell
python scripts/generate_athlete_profile.py   # writes coach/athlete_profile.md
python scripts/generate_briefing.py          # writes coach/coach_briefing.md
```

Or generate them as part of a sync: `python scripts/run_sync.py --latest --profile --briefing`.

The `coach/` folder ships with template files (`ai_coach_prompt.md`, `method.md`,
`goals.md`) you can adapt. Generated outputs are personal and stay out of git.

---

## Troubleshooting

- **`can't open file '...run_sync.py'`** — the script lives in `scripts/`. Run it as
  `python scripts/run_sync.py ...` from the project root (not `python run_sync.py`).
- **`ModuleNotFoundError`** — your virtual environment isn't active, or dependencies
  aren't installed. Re-run `.\venv\Scripts\Activate.ps1` then
  `pip install -r requirements.txt`.
- **Authentication failed** — double-check email/password. If your account uses
  two-factor authentication, you'll be prompted for the code during
  `test_connection.py`. If it keeps failing, sign in once via the Garmin website,
  then retry.
- **Account locked / too many attempts** — wait a bit and try again; Garmin
  rate-limits repeated logins.

---

## Privacy note

This project is designed to be shared as code only. Before pushing your own changes,
confirm `git status` shows **no** files under `data/`, `logs/`, or your personal
`coach/` outputs. The included `.gitignore` already handles this.
