# LegiAlerts
A Twitter/Bsky bot and automation platform for tracking anti-LGBTQ legislation. The bot updates the tracker at https://legialerts.org and posts alerts when new bills appear or when statuses change.

## How it works
- Pulls session master lists and bill details from the LegiScan API.
- Updates Google Sheets worksheets for anti/pro and rollover bills.
- Posts alerts to X (Twitter) and Bluesky, and sends HTML email reports.
- Caches session lists and sheet snapshots in `cache/` to limit API calls.

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
The bot reads all secrets from environment variables:
- `legiscan_key`: LegiScan API key.
- `gsuite_service_account`: JSON string for the Google service account credentials.
- `gsheet_key_2025`: Google Sheet key for the 2025 tracker (add more keys for additional years).
- `twitter_consumer_key`, `twitter_consumer_secret`, `twitter_access_token`, `twitter_access_token_secret`: X/Twitter API credentials.
- `bsky_user`, `bsky_pass`: Bluesky credentials.
- `GOOGLE_TOKEN`: Gmail SMTP app password used to send email reports.

Note: `legialerts.json` contains a service account example; keep real credentials out of version control.

## Running
The bot runs continuously and sleeps ~15 minutes between cycles:
```bash
python main.py
```
It can also be run under a process manager (systemd, supervisor) or a cronjob that invokes the script repeatedly.

## Sheets and cache expectations
- Worksheets expected: `Anti-LGBTQ Bills`, `Pro-LGBTQ Bills`, `Rollover Anti-LGBTQ Bills`, `Rollover Pro-LGBTQ Bills`.
- The header row is used as the schema; the bot fills in fields like `Status`, `Date`, `Change Hash`, `Sponsors`, `History`, and `PDF`.
- Cache files are written to `cache/`, including `sessions.csv`, per-state session lists, and `gsheet-<worksheet>-<year>.csv`.

## Notes
- The `years` list in `main.py` controls which tracker years are updated.
- Email templates live in `utils/email.html`.


# Credits
Created by Allison Chapman

Code Base Maintained By: Allison Chapman @AlliRaine22, Kim MC42, and others

Spreadsheet Maintained by Allison Chapman @AlliRaine22, Alejandra Caraballo @esqueer_, and Erin Reed @erininthemorn
