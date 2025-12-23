import json
import os
import re
from pathlib import Path
from typing import Dict, Iterable, List

def _as_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


BASE_PATH = Path(__file__).resolve().parent.parent
PRODUCTION = _as_bool(os.environ.get("PRODUCTION"))
CACHE_DIR = Path("/var/data") if PRODUCTION else BASE_PATH / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
LOG_FILE = os.environ.get("LOG_FILE", str(CACHE_DIR / "legialerts.log"))
Path(LOG_FILE).parent.mkdir(parents=True, exist_ok=True)

LEGISCAN_MIN_INTERVAL = float(os.environ.get("LEGISCAN_MIN_INTERVAL", "0"))
REQUEST_TIMEOUT = float(os.environ.get("REQUEST_TIMEOUT", "30"))
SEARCH_CACHE_TTL = int(os.environ.get("SEARCH_CACHE_TTL", "3600"))
SOCIAL_ENABLED = _as_bool(os.environ.get("SOCIAL_ENABLED"), default=True)
ALLOW_ANONYMOUS_API = _as_bool(os.environ.get("API_ALLOW_ANONYMOUS"), default=False)


def load_service_account_credentials() -> Dict:
    """Return service account credentials from env JSON or a file path."""
    env_json = os.environ.get("gsuite_service_account")
    if env_json:
        return json.loads(env_json)
    file_path = os.environ.get("GSUITE_SERVICE_ACCOUNT_FILE")
    if file_path and Path(file_path).exists():
        with open(file_path, "r") as handle:
            return json.load(handle)
    raise RuntimeError("Google service account credentials not configured. Set 'gsuite_service_account' or 'GSUITE_SERVICE_ACCOUNT_FILE'.")


def get_sheet_key(year: int) -> str:
    key = os.environ.get(f"gsheet_key_{year}")
    if not key:
        raise RuntimeError(f"Missing Google Sheet key for year {year} (set gsheet_key_{year}).")
    return key


def _parse_years(value: str) -> Iterable[int]:
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            yield int(part)
        except ValueError:
            continue


def get_tracker_years(default: Iterable[int] = (2026,)) -> List[int]:
    explicit = os.environ.get("TRACKER_YEARS")
    if explicit:
        years = list(_parse_years(explicit))
        if years:
            return sorted(set(years))
    pattern = re.compile(r"^gsheet_key_(\d{4})$")
    discovered = []
    for key in os.environ.keys():
        match = pattern.match(key)
        if match:
            discovered.append(int(match.group(1)))
    if discovered:
        return sorted(set(discovered))
    return sorted(set(int(y) for y in default))
