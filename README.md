# AiCoach

Pull your own Garmin Connect data (activities, sleep, RHR, weight, daily monitoring +
raw FIT files) into a local SQLite DB for analysis. Wraps
[GarminDB](https://github.com/tcgoetz/GarminDB). Runs locally with your own account —
credentials and data never leave your machine and are never committed.

## Requirements

- Python ≥ 3.10
- A Garmin Connect account

## Setup

```powershell
git clone https://github.com/Qq1b3/AiCoach.git
cd AiCoach

python -m venv venv
.\venv\Scripts\Activate.ps1            # POSIX: source venv/bin/activate
pip install -r requirements.txt

python scripts/setup_config.py         # enter your Garmin email/password
python scripts/test_connection.py      # verify auth (handles 2FA prompt)
python scripts/run_sync.py --initial   # full history download
```

## Sync commands

| Command | Action |
| --- | --- |
| `python scripts/run_sync.py --initial` | Full historical download |
| `python scripts/run_sync.py --latest`  | Incremental update (daily) |
| `python scripts/run_sync.py --all`     | Re-download everything (overwrite) |
| `python scripts/run_sync.py --stats`   | Show what's in the local DB |

Add `--profile` / `--briefing` to also generate the coach outputs in `coach/`.

## Where things live

- **Password** → OS credential manager (`keyring`, service `GarminConnect`)
- **Email + config** → `~/.GarminDb/GarminConnectConfig.json`
- **Data + FIT files** → `data/` (git-ignored)

Each user runs `setup_config.py` with their own credentials. The `.gitignore` keeps all
data and credentials out of the repo.

## Automated sync (Windows, optional)

```powershell
# Admin PowerShell
python scripts/setup_scheduler.py --create --time 07:00   # --status / --run / --delete
```

## Notes

- `garmindb` is pinned to `3.6.7` (see `requirements.txt`).
- If auth fails: check credentials, complete 2FA, or sign in once via the Garmin website
  and retry. Garmin rate-limits repeated logins.
