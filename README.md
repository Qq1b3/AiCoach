# AiCoach

Pull your own Garmin Connect data (activities, sleep, RHR, weight, daily monitoring, plus raw FIT files) into a local SQLite DB for analysis. It's a wrapper around [GarminDB](https://github.com/tcgoetz/GarminDB). Everything runs locally with your own account, and your credentials and data never leave your machine or get committed.

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

## Where things live

- Password: OS credential manager (`keyring`, service `GarminConnect`), encrypted.
- Session token: `~/.GarminDb/garmin_tokens.json`.
- Email and config: `~/.GarminDb/GarminConnectConfig.json`.
- Data and FIT files: `data/` (git-ignored).

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
