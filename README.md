[![.github/workflows/trigger-legialerts.yml](https://github.com/alliraine/legialerts/actions/workflows/trigger-legialerts.yml/badge.svg)](https://github.com/alliraine/legialerts/actions/workflows/trigger-legialerts.yml)
# LegiAlerts
A Twitter/Bsky bot and automation platform for tracking anti-LGBTQ legislation. The bot updates the tracker at https://legialerts.org and posts alerts when new bills appear or when statuses change.

## How it works
- Pulls session master lists and bill details from the LegiScan API.
- Updates Google Sheets worksheets for anti/pro and rollover bills.
- Posts alerts to X (Twitter) and Bluesky, and sends HTML email reports.
- Caches session lists and sheet snapshots in `cache/` (or `/var/data` when `PRODUCTION=true`) to limit API calls.

## Requirements
- Python 3
- A LegiScan API key
- A Google service account for Sheets access
- Social accounts and SMTP credentials for notifications

Install dependencies:
```bash
pip install -r requirements.txt
```

## Configuration (environment variables)
The bot reads all secrets from environment variables (see `.env.example` for a template):
- `legiscan_key`: LegiScan API key.
- `gsuite_service_account` **or** `GSUITE_SERVICE_ACCOUNT_FILE`: Google service account credentials (JSON string or secure file path). Keep the JSON out of version control.
- `TRACKER_YEARS`: Comma-separated list of tracker years (defaults to `2026`). Each year needs a matching `gsheet_key_<year>` value.
- `gsheet_key_<year>`: Google Sheet key for each tracker year (e.g., `gsheet_key_2026`).
- `twitter_consumer_key`, `twitter_consumer_secret`, `twitter_access_token`, `twitter_access_token_secret`: X/Twitter API credentials.
- `bsky_user`, `bsky_pass`: Bluesky credentials.
- `GOOGLE_TOKEN`: Gmail SMTP app password used to send email reports.
- `API_AUTH_TOKEN`: Bearer token required for the Flask endpoints (set `API_ALLOW_ANONYMOUS=true` to intentionally disable auth).
- `LOG_LEVEL`: Logging verbosity (DEBUG, INFO, WARNING, ERROR, CRITICAL). Default is INFO.
- `LOG_FILE`: Optional log file path (defaults to `cache/legialerts.log`, or `/var/data/legialerts.log` in production).
- `LEGISCAN_MIN_INTERVAL`: Optional delay between LegiScan API calls in seconds.
- `REQUEST_TIMEOUT`: Request timeout in seconds for LegiScan calls (defaults to 30).
- `SEARCH_CACHE_TTL`: Optional cache TTL for search results in seconds (defaults to 3600).
- `SOCIAL_ENABLED`: Set to `false` to disable posting to X/Twitter and Bluesky.
- `PRODUCTION`: Set to `true` to store cache files under `/var/data` instead of `cache/`.

Security note: Do not commit real tokens, service accounts, or SMTP secrets. Use environment variables or a mounted secret file instead of tracking credentials in Git.

## Running
The bot runs continuously and sleeps ~15 minutes between cycles:
```bash
python main.py
```
It can also be run under a process manager (systemd, supervisor) or a cronjob that invokes the script repeatedly.

## Web endpoint (Flask)
You can trigger a single run via a lightweight Flask app:
```bash
flask --app app run --host 0.0.0.0 --port 8080
```
Endpoints:
- `GET /run`: triggers one update cycle; returns 409 if a run is already in progress.
- `GET /health`: basic health check.
- `GET /stats`: run metrics and worksheet summary stats from cached sheets.

### Authentication
Authentication is required by default; set `API_AUTH_TOKEN` and provide the same token in requests. To deliberately allow anonymous access, set `API_ALLOW_ANONYMOUS=true`. Example:
```bash
curl -H "Authorization: Bearer $API_AUTH_TOKEN" http://localhost:8080/health
```

## Sheets and cache expectations
- Worksheets expected: `Anti-LGBTQ Bills`, `Pro-LGBTQ Bills`, `Rollover Anti-LGBTQ Bills`, `Rollover Pro-LGBTQ Bills`.
- The header row is used as the schema; the bot fills in fields like `Status`, `Date`, `Change Hash`, `Sponsors`, `History`, and `PDF`.
- Cache files are written to `cache/` (or `/var/data` in production), including `sessions.csv`, per-state session lists, and `gsheet-<worksheet>-<year>.csv`.

## Notes
- The `years` list in `main.py` controls which tracker years are updated.
- Email templates live in `utils/email.html`.

## Attribution
LegiAlerts uses data from LegiScan. All data is licensed under Creative Commons Attribution 4.0; attribution to LegiScan is required.


# Credits
Created by Allison Chapman

Code Base Maintained By: Allison Chapman @AlliRaine22, Kim MC42, and others

Spreadsheet Maintained by Allison Chapman @AlliRaine22, Alejandra Caraballo @esqueer_, and Erin Reed @erininthemorn
