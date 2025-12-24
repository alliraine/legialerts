import hashlib
import json
import logging
import os
import time
import re
from datetime import datetime
from typing import Iterable, List

import gspread
import pandas as pd
import requests
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from utils.config import (
    CACHE_DIR,
    LEGISCAN_MIN_INTERVAL,
    REQUEST_TIMEOUT,
    SEARCH_CACHE_TTL,
    get_sheet_key,
    get_tracker_years,
    load_service_account_credentials,
)
from utils.us_state_abbrv import abbrev_to_us_state

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

legi_key = os.environ.get("legiscan_key")
Search_URL = f"https://api.legiscan.com/?key={legi_key}&op=getSearchRaw&state=ALL&page="
_last_legiscan_call = 0.0


class color:
    PURPLE = "\033[95m"
    CYAN = "\033[96m"
    DARKCYAN = "\033[36m"
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    END = "\033[0m"


def _extract_display_number(value):
    if not isinstance(value, str):
        return str(value)
    value = value.strip()
    hyperlink_match = re.match(r'=HYPERLINK\(".*?","(.*)"\)', value)
    if hyperlink_match:
        return hyperlink_match.group(1)
    return value


def _normalize_bill_number(value: str) -> str:
    if value is None:
        return ""
    display = _extract_display_number(value)
    cleaned = re.sub(r"[^A-Za-z0-9]", "", str(display)).upper()
    return cleaned


def _strip_session_prefix(normalized_number: str) -> str:
    if not normalized_number:
        return ""
    return re.sub("^X\\d+", "", normalized_number)


def create_session():
    session = requests.Session()
    retry = Retry(total=5, backoff_factor=0.5, status_forcelist=(429, 500, 502, 503, 504), allowed_methods=frozenset(["GET"]))
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def legiscan_fetch(url, session):
    global _last_legiscan_call
    if LEGISCAN_MIN_INTERVAL > 0:
        now = time.monotonic()
        elapsed = now - _last_legiscan_call
        if elapsed < LEGISCAN_MIN_INTERVAL:
            time.sleep(LEGISCAN_MIN_INTERVAL - elapsed)
    try:
        r = session.get(url, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
    except requests.RequestException as exc:
        logger.error("LegiScan fetch failed: %s", exc)
        return None
    _last_legiscan_call = time.monotonic()
    try:
        data = r.json()
    except Exception:
        logger.exception("Failed to parse LegiScan JSON")
        logger.error("Response text: %s", r.text)
        return None
    status = data.get("status")
    if status and status != "OK":
        logger.error("LegiScan error: %s", data.get("alert", {}).get("message", data))
        return None
    return data


def load_existing_sheets(gc, years: Iterable[int]) -> List[pd.DataFrame]:
    worksheets = ["Anti-LGBTQ Bills", "Pro-LGBTQ Bills", "Rollover Anti-LGBTQ Bills", "Rollover Pro-LGBTQ Bills"]
    frames = []
    for year in years:
        try:
            doc = gc.open_by_key(get_sheet_key(year))
        except Exception as exc:
            logger.warning("Unable to open sheet for year %s: %s", year, exc)
            continue
        for worksheet in worksheets:
            try:
                wks = doc.worksheet(worksheet)
            except Exception:
                continue
            expected_headers = wks.row_values(1)
            frames.append(pd.DataFrame(wks.get_all_records(expected_headers=expected_headers)))
    return frames


def load_ignore_list():
    path = os.path.join(CACHE_DIR, "ignore_list.json")
    if not os.path.exists(path):
        return pd.DataFrame(columns=["bill_id"])
    return pd.read_json(path)


def known_bill(bill, existing_frames, ignore_list):
    bill_number_norm = _normalize_bill_number(bill.get("bill_number"))
    bill_number_base = _strip_session_prefix(bill_number_norm)
    for df in existing_frames:
        if df.empty:
            continue
        df_numbers = df.get("Number")
        normalized_numbers = set()
        if df_numbers is not None:
            normalized_numbers = set(
                _normalize_bill_number(n) for n in df_numbers if isinstance(n, str) or not pd.isna(n)
            )
        matches = df.loc[
            (df["Bill ID"] == bill["bill_id"])
            | (
                (df["State"] == abbrev_to_us_state.get(bill["state"], "")) &
                (bill_number_norm in normalized_numbers or bill_number_base in normalized_numbers) &
                (df["Summary"] == bill["title"])
            )
        ]
        if not matches.empty:
            return True
    if not ignore_list.empty and not ignore_list.loc[ignore_list["bill_id"] == bill["bill_id"]].empty:
        return True
    return False


def search(term, page, session, existing_frames, ignore_list):
    cache_key = hashlib.sha256(f"{term}|{page}".encode("utf-8")).hexdigest()
    cache_dir = os.path.join(CACHE_DIR, "search")
    os.makedirs(cache_dir, exist_ok=True)
    cache_path = os.path.join(cache_dir, f"{cache_key}.json")

    if os.path.exists(cache_path) and (time.time() - os.path.getmtime(cache_path)) < SEARCH_CACHE_TTL:
        with open(cache_path, "r") as handle:
            data = json.load(handle)
    else:
        data = legiscan_fetch(Search_URL + str(page) + "&query=" + str(term), session)
        if data is None:
            return []
        with open(cache_path, "w") as handle:
            json.dump(data, handle)

    content = data.get("searchresult")
    if content is None:
        logger.error("LegiScan search missing searchresult for term=%s page=%s", term, page)
        return []
    bills = []
    for e in content:
        if e != "summary":
            bill = content[e]
            if not known_bill(bill, existing_frames, ignore_list):
                bills.append(bill)

    if content["summary"]["page_total"] > page:
        bills.extend(search(term, page + 1, session, existing_frames, ignore_list))
    return bills


def default_search_terms():
    return [
        '"drag" NOT "race" NOT "racing"',
        '"biological sex"',
        '"gender affirming"',
        '"pronouns"',
        '"female impersonator"',
        '"gender reassignment"',
        '"sex reassignment"',
        '"cross sex"',
        '"obscene"',
        '"groom"',
        '"polyamory"',
        '"multiple partners"',
        '"Biological sex" or "puberty" or "hormone" or "bathroom" or "restroom" or "gender marker" or "sex marker" or "sex designation" or "gender affirming" Or "drag" OR "gender change" or "transgender"',
    ]


def render_results(bills):
    bills_seen = []
    for bill in bills:
        if bill["bill_id"] in bills_seen:
            continue
        bills_seen.append(bill["bill_id"])
        date_str = bill.get("last_action_date")
        color_code = ""
        if date_str:
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                if dt == datetime(2025, 1, 17):
                    color_code = color.RED
                elif dt > datetime(2025, 1, 16):
                    color_code = color.YELLOW
            except ValueError:
                pass
        output = f"{bill.get('last_action_date')} {abbrev_to_us_state.get(bill['state'], bill['state'])} {bill['bill_number']} {bill['title']} {bill['text_url']}"
        if color_code:
            print(color_code, output, color.END)
        else:
            print(output)
    print(f"completed at {datetime.now()}")


def main(search_terms: List[str] = None, years: Iterable[int] = None):
    terms = search_terms or default_search_terms()
    target_years = list(years) if years is not None else get_tracker_years((2026,))
    gc = gspread.service_account_from_dict(load_service_account_credentials())
    existing_frames = load_existing_sheets(gc, target_years)
    ignore_list = load_ignore_list()
    session = create_session()
    bills = []
    for term in terms:
        bills.extend(search(term, 1, session, existing_frames, ignore_list))
    render_results(bills)


if __name__ == "__main__":
    main()
