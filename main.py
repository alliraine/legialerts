import os.path
import requests
import gspread
import json
import hashlib
import logging
import threading
import math

import pandas as pd
import time

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from gspread.utils import rowcol_to_a1

from utils.get_sessions import get_sessions_dataframe
from utils.notify import notify_world, notify_dev_team, notify_legi_team, send_history_report, send_new_report, \
    notify_social
from utils.legiscan_helper import get_calendar, get_sponsors, get_history, get_texts
from utils.config import (
    PRODUCTION,
    CACHE_DIR,
    LOG_FILE,
    LOG_LEVEL,
    LEGISCAN_MIN_INTERVAL,
    REQUEST_TIMEOUT,
    get_sheet_key,
    get_tracker_years,
    load_service_account_credentials,
)

from dotenv import load_dotenv

load_dotenv()
curr_path = os.path.dirname(__file__)

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_FILE),
    ],
)
logger = logging.getLogger(__name__)

#ordered list based on legiscan state id
STATES = ["Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado", "Connecticut", "Delaware", "Florida",
          "Georgia", "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky", "Louisiana",
          "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota", "Mississippi", "Missouri", "Montana",
          "Nebraska", "Nevada", "New Hampshire", "New Jersey", "New Mexico", "New York", "North Carolina",
          "North Dakota", "Ohio", "Oklahoma", "Oregon", "Pennsylvania", "Rhode Island", "South Carolina",
          "South Dakota", "Tennessee", "Texas", "Utah", "Vermont", "Virginia", "Washington", "West Virginia",
          "Wisconsin", "Wyoming", "DC", "US"]

legi_key = os.environ.get('legiscan_key')
Master_List_URL = f"https://api.legiscan.com/?key={legi_key}&op=getMasterList&id="
Bill_URL = f"https://api.legiscan.com/?key={legi_key}&op=getBill&id="

years = get_tracker_years((2026,))

world_report = ""
dev_report = ""
history_report = """
<tr>
    <th>State</th>
    <th>Bill</th>
    <th>New History</th>
</tr>
"""
new_report = """
<tr>
    <th>State</th>
    <th>Bill</th>
    <th>Title</th>
    <th>Type</th>
</tr>
"""

dev_report_updates, new_report_updates, history_report_updates = 0, 0, 0
BILL_CACHE_DIR = os.path.join(CACHE_DIR, "bills")
LEGISCAN_MIN_INTERVAL = float(os.environ.get("LEGISCAN_MIN_INTERVAL", "0"))
SESSION_LIST_REFRESH_SECONDS = 24 * 60 * 60
MASTER_LIST_REFRESH_SECONDS = 60 * 60
_last_legiscan_call = 0.0
STATS = {
    "last_run_started": None,
    "last_run_finished": None,
    "last_run_duration_seconds": None,
    "last_run_status": None,
    "legiscan_calls": 0,
    "bill_cache_hits": 0,
    "bill_cache_misses": 0,
    "new_bills": 0,
    "changed_bills": 0,
    "history_updates": 0,
}
_stats_lock = threading.Lock()

def create_legiscan_session():
    session = create_legiscan_session()
    retry = Retry(
        total=5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET"]),
        backoff_factor=0.5,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

def _set_stat(key, value):
    with _stats_lock:
        STATS[key] = value

def _inc_stat(key, delta=1):
    with _stats_lock:
        STATS[key] = STATS.get(key, 0) + delta

def get_stats():
    with _stats_lock:
        return dict(STATS)

def _success_flag_path(worksheet, year):
    safe_name = worksheet.replace(" ", "_").replace("/", "_")
    return os.path.join(CACHE_DIR, f"success-{safe_name}-{year}.txt")

def mark_run_failed(worksheet, year):
    try:
        os.remove(_success_flag_path(worksheet, year))
    except FileNotFoundError:
        return
    except Exception:
        logger.warning("Unable to clear success flag for %s %s", worksheet, year)

def mark_run_success(worksheet, year):
    try:
        with open(_success_flag_path(worksheet, year), "w") as handle:
            handle.write(str(time.time()))
    except Exception:
        logger.warning("Unable to write success flag for %s %s", worksheet, year)

def was_last_run_successful(worksheet, year):
    return os.path.exists(_success_flag_path(worksheet, year))

def legiscan_get(url, session):
    global _last_legiscan_call
    if LEGISCAN_MIN_INTERVAL > 0:
        now = time.monotonic()
        elapsed = now - _last_legiscan_call
        if elapsed < LEGISCAN_MIN_INTERVAL:
            logger.debug("Throttling LegiScan call for %.3fs", LEGISCAN_MIN_INTERVAL - elapsed)
            time.sleep(LEGISCAN_MIN_INTERVAL - elapsed)
    logger.debug("LegiScan request: %s", url)
    try:
        response = session.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
    except requests.RequestException as exc:
        _set_stat("last_run_status", "error")
        logger.error("LegiScan request failed: %s", exc)
        raise
    _last_legiscan_call = time.monotonic()
    _inc_stat("legiscan_calls")
    logger.debug("LegiScan response: %s %s", response.status_code, url)
    return response

def parse_legiscan_json(response, context):
    try:
        data = response.json()
    except Exception:
        logger.exception("Failed to parse LegiScan JSON for %s", context)
        logger.error("LegiScan response text: %s", response.text)
        return None
    status = data.get("status")
    if status and status != "OK":
        alert = data.get("alert", {})
        logger.error("LegiScan error for %s: %s", context, alert.get("message", data))
        return None
    return data

def load_bill_cache(bill_id, expected_change_hash):
    cache_path = os.path.join(BILL_CACHE_DIR, f"{bill_id}.json")
    if not os.path.exists(cache_path):
        logger.debug("Bill cache miss: %s", bill_id)
        _inc_stat("bill_cache_misses")
        return None
    try:
        with open(cache_path, "r") as handle:
            cached = json.load(handle)
        if cached.get("change_hash") == expected_change_hash:
            logger.debug("Bill cache hit: %s", bill_id)
            _inc_stat("bill_cache_hits")
            return cached.get("bill")
        logger.debug("Bill cache stale: %s", bill_id)
        _inc_stat("bill_cache_misses")
    except Exception:
        logger.exception("Bill cache read failed: %s", bill_id)
        return None
    return None

def save_bill_cache(bill_id, change_hash, bill):
    os.makedirs(BILL_CACHE_DIR, exist_ok=True)
    cache_path = os.path.join(BILL_CACHE_DIR, f"{bill_id}.json")
    with open(cache_path, "w") as handle:
        json.dump({"change_hash": change_hash, "bill": bill}, handle)
    logger.debug("Bill cache updated: %s", bill_id)

def get_bill_details(bill_id, change_hash, session):
    cached = load_bill_cache(bill_id, change_hash)
    if cached is not None:
        return cached
    logger.info("Fetching bill details: %s", bill_id)
    r = legiscan_get(Bill_URL + str(bill_id), session)
    data = parse_legiscan_json(r, f"getBill bill_id={bill_id}")
    if not data or "bill" not in data:
        logger.error("Missing bill payload for bill_id=%s", bill_id)
        return None
    content = data["bill"]
    save_bill_cache(bill_id, change_hash, content)
    return content

def row_missing_details(row):
    required_fields = ["Sponsors", "Calendar", "History", "PDF", "Bill ID"]
    for field in required_fields:
        value = row.get(field)
        try:
            if pd.isna(value):
                return True
        except TypeError:
            pass
        if value is None:
            return True
        if isinstance(value, str) and value.strip() in ("", "Unknown"):
            return True
    return False

def sheet_has_missing_details(gsheet):
    for _, row in gsheet.iterrows():
        if row_missing_details(row):
            logger.debug("Missing details detected in sheet")
            return True
    return False

def worksheet_legiscan_digest(gsheet, master_index):
    rows = []
    for _, row in gsheet.iterrows():
        state = str(row.get("State", "")).strip()
        number = str(row.get("Number", "")).strip()
        if not state or not number:
            continue
        lscan_row = master_index.get(state, {}).get(number)
        change_hash = ""
        if lscan_row is not None:
            change_hash = str(lscan_row.get("change_hash", "")).strip()
        rows.append((state, number, change_hash))
    rows.sort()
    digest = hashlib.sha256(repr(rows).encode("utf-8")).hexdigest()
    return digest

def load_worksheet_digest(worksheet, year):
    safe_name = worksheet.replace(" ", "_").replace("/", "_")
    digest_path = os.path.join(CACHE_DIR, f"digest-{safe_name}-{year}.txt")
    if not os.path.exists(digest_path):
        return None
    try:
        with open(digest_path, "r") as handle:
            return handle.read().strip()
    except Exception:
        return None

def save_worksheet_digest(worksheet, year, digest):
    safe_name = worksheet.replace(" ", "_").replace("/", "_")
    digest_path = os.path.join(CACHE_DIR, f"digest-{safe_name}-{year}.txt")
    os.makedirs(os.path.dirname(digest_path), exist_ok=True)
    with open(digest_path, "w") as handle:
        handle.write(digest)

def get_main_lists(year, session):
    session_list_file = os.path.join(CACHE_DIR, "sessions.csv")

    all_lists = {}
    logger.info("Loading session lists for year %s", year)

    # pull new session list every 24 hours
    if (not os.path.exists(session_list_file)) or (os.path.getmtime(session_list_file)) <= time.time() - SESSION_LIST_REFRESH_SECONDS:
        logger.info("Session list cache stale or missing; fetching from LegiScan")
        df = get_sessions_dataframe(session=session, request_fn=lambda url: legiscan_get(url, session))
    else:
        logger.info("Loading sessions_list from cache")
        df = pd.read_csv(session_list_file)

    if df.empty or not all(col in df.columns for col in ["year_start", "year_end", "special", "session_id", "state_id"]):
        logger.error("Session list is empty or missing required columns; skipping master list load")
        return {}

    SESSIONS = df.loc[((df['year_start'] == year) | (df['year_end'] == year)) & (df['special'] == 0)]

    for idx, s in SESSIONS.iterrows():
        # set helpful vars
        s_id = s.get("session_id")
        state_id = s.get("state_id")
        s_name = STATES[state_id - 1]
        s_year = str(s.get("year_start"))
        s_files = [os.path.join(CACHE_DIR, f"{s_name}-{s_year}.csv")]

        # if this session extends more than one year we want to make sure we use it for both years
        if s.get("year_start") != s.get("year_end"):
            s_files.append(os.path.join(CACHE_DIR, f"{s_name}-{str(s.get('year_end'))}.csv"))

        for s_file in s_files:
            # checks cache if stale or doesn't exist pull (we can pull new data every hour)
            if (not os.path.exists(s_file)) or (os.path.getmtime(s_file)) <= time.time() - MASTER_LIST_REFRESH_SECONDS:
                logger.info("Session master list cache stale; fetching %s %s", s_name, s_year)
                # Pull session master list from Legiscan
                r = legiscan_get(Master_List_URL + str(s_id), session)
                logger.debug("Master list url: %s", Master_List_URL + str(s_id))
                data = parse_legiscan_json(r, f"getMasterList session_id={s_id}")
                if not data or "masterlist" not in data:
                    logger.error("Missing master list for session_id=%s", s_id)
                    all_lists[s_name] = pd.DataFrame()
                    continue
                content = data["masterlist"]
                temp_list = []
                for attribute, value in content.items():
                    if attribute != "session":
                        temp_list.append(value)
                all_lists[s_name] = pd.DataFrame(temp_list)

                # save to csv
                all_lists[s_name].to_csv(s_file)
            else:
                logger.info("Loading master list from cache: %s", s_file)
                all_lists[s_name] = pd.read_csv(s_file)

    return all_lists

def build_master_index(all_lists):
    fields = ["change_hash", "last_action", "last_action_date", "title", "url", "bill_id"]
    master_index = {}
    for state_name, df in all_lists.items():
        if df.empty:
            master_index[state_name] = {}
            continue
        if "number" not in df.columns:
            master_index[state_name] = {}
            continue
        state_index = {}
        for _, row in df.iterrows():
            number = str(row.get("number", "")).strip()
            if number:
                state_index[number] = {field: row.get(field) for field in fields}
        master_index[state_name] = state_index
    return master_index

def clean_cell_value(value):
    try:
        if pd.isna(value):
            return ""
    except TypeError:
        # pd.isna can raise on unhashable types; leave value as-is in that case
        pass
    if isinstance(value, float) and not math.isfinite(value):
        return ""
    if hasattr(value, "item"):
        try:
            value = value.item()
        except Exception:
            pass
    return value

def queue_update(row_updates, row, column, value):
    value = clean_cell_value(value)
    current = row.get(column)
    if pd.isna(current):
        current = ""
    if isinstance(current, str) and current.strip().lower() == "unknown":
        current = ""
    if current != value:
        row_updates[column] = value

def should_format_sheet(worksheet, year, headers):
    safe_name = worksheet.replace(" ", "_").replace("/", "_")
    flag_path = os.path.join(CACHE_DIR, f"format-{safe_name}-{year}.txt")
    header_signature = "|".join(headers)
    if not os.path.exists(flag_path):
        return True
    try:
        with open(flag_path, "r") as handle:
            previous = handle.read()
    except Exception:
        return True
    return previous != header_signature

def mark_sheet_formatted(worksheet, year, headers):
    safe_name = worksheet.replace(" ", "_").replace("/", "_")
    flag_path = os.path.join(CACHE_DIR, f"format-{safe_name}-{year}.txt")
    header_signature = "|".join(headers)
    os.makedirs(os.path.dirname(flag_path), exist_ok=True)
    with open(flag_path, "w") as handle:
        handle.write(header_signature)

def update_worksheet(year, worksheet, new_title, change_title, session, all_lists, rollover = False, rollover_lists = None):
    global world_report, history_report, dev_report, new_report, new_report_updates, history_report_updates, dev_report_updates
    logger.info("Starting worksheet update: %s %s", year, worksheet)
    mark_run_failed(worksheet, year)
    if rollover and rollover_lists is not None:
        all_lists = rollover_lists
    if rollover:
        all_lists = rollover_lists or get_main_lists(year-1, session)
    master_index = build_master_index(all_lists)

    #open google sheets api account
    gc = gspread.service_account_from_dict(load_service_account_credentials())

    #open worksheet
    wks = gc.open_by_key(get_sheet_key(year)).worksheet(worksheet)
    expected_headers = wks.row_values(1)
    header_to_col = {name: idx + 1 for idx, name in enumerate(expected_headers)}

    #loads worksheet into dataframe
    logger.debug("Worksheet headers: %s", expected_headers)
    gsheet = pd.DataFrame(wks.get_all_records(expected_headers=expected_headers)).astype(object)
    gsheet = gsheet.fillna('')

    #gets previous sheet from file
    if os.path.exists(os.path.join(CACHE_DIR, f"gsheet-{worksheet}-{year}.csv")):
        prev_gsheet = pd.read_csv(
            os.path.join(CACHE_DIR, f"gsheet-{worksheet}-{year}.csv"),
            dtype=object,
            keep_default_na=False,
        ).astype(object)
        prev_gsheet = prev_gsheet.fillna('')
    else:
        prev_gsheet = gsheet.copy()

    digest = worksheet_legiscan_digest(gsheet, master_index)
    previous_digest = load_worksheet_digest(worksheet, year)
    previous_success = was_last_run_successful(worksheet, year)
    if digest and previous_success and previous_digest == digest and not sheet_has_missing_details(gsheet):
        logger.info("No LegiScan changes detected; skipping worksheet update")
        mark_run_success(worksheet, year)
        return

    sheet_changed = False
    missing_states = set()
    cell_updates = []
    for index, row in gsheet.iterrows():
        try:
            row_updates = {}
            r_state = row["State"].strip()
            r_bnum = row["Number"]
            r_btype = row["Bill Type"]
            queue_update(row_updates, row, 'Youth State Risk', f"=VLOOKUP(A{index+2},'Risk Levels'!$A$4:$E$55,2)")
            queue_update(row_updates, row, 'Adult State Risk', f"=VLOOKUP(A{index+2},'Risk Levels'!$A$4:$E$55,3)")
            state_list = all_lists.get(r_state)
            if state_list is None:
                missing_states.add(r_state)
                continue
            if not state_list.empty:
                lscan_row = master_index.get(r_state, {}).get(r_bnum.strip())
                if lscan_row is not None:
                    r_la = lscan_row["last_action"]
                    r_title = lscan_row["title"]
                    r_link = lscan_row["url"]
                    bill_id = lscan_row["bill_id"]
                    change_hash = lscan_row["change_hash"]
                    last_action_date = lscan_row["last_action_date"]
                    prev = prev_gsheet.loc[(prev_gsheet["State"] == row["State"]) & (prev_gsheet["Number"] == row["Number"])]
                    bill_details = None

                    #checks if the bill is recently added. If not then alert new bill
                    if prev.empty or gsheet.at[index, 'Change Hash'] == "":
                        logger.info("New bill detected: %s %s", r_state, r_bnum.strip())
                        _inc_stat("new_bills")
                        t = f"{new_title}\n------------------------\n📜Bill: {r_state} {r_bnum.strip()} \n📑Title: {r_title}\n🏷️Bill Type: {r_btype}\n🏛Status: {r_la} \n🔗Bill Text: {r_link} "
                        notify_social(t)
                        new_report_updates += 1
                        new_report = new_report + f"""
                                                    <tr>
                                                        <th>{r_state}</th>
                                                        <th>{r_bnum.strip()}</th>
                                                        <th>{r_title}</th>
                                                        <th>{r_btype}</th>
                                                    </tr>
                                                    """

                        content = get_bill_details(bill_id, change_hash, session)
                        if content is None:
                            continue
                        bill_details = content

                        sponsors_value = get_sponsors(content["sponsors"])
                        calendar_value = get_calendar(content["calendar"])
                        history_value = get_history(content["history"])
                        texts_value = get_texts(content["texts"])
                        queue_update(row_updates, row, 'Sponsors', sponsors_value)
                        queue_update(row_updates, row, 'Calendar', calendar_value)
                        queue_update(row_updates, row, 'History', history_value)
                        queue_update(row_updates, row, 'Bill ID', str(bill_id))
                        queue_update(row_updates, row, 'PDF', texts_value)


                    #if not new check change hash to see if the bill has changed. If it has trigger an alert
                    elif lscan_row["change_hash"] != row["Change Hash"] and (lscan_row["last_action"] != row["Status"] or lscan_row["last_action_date"] != row["Date"]):
                        logger.info("Bill change found: %s %s", r_state, r_bnum.strip())
                        _inc_stat("changed_bills")
                        t = f"{change_title}\n📜Bill: {r_state} {r_bnum.strip()} \n📑Title: {r_title}\n🏷️Bill Type: {r_btype}\n🏛Status: {r_la} \n🔗Bill Text: {r_link}"
                        notify_social(t)
                        content = get_bill_details(bill_id, change_hash, session)
                        if content is None:
                            continue
                        bill_details = content

                        sponsors_value = get_sponsors(content["sponsors"])
                        calendar_value = get_calendar(content["calendar"])
                        history_value = get_history(content["history"])
                        texts_value = get_texts(content["texts"])
                        queue_update(row_updates, row, 'Sponsors', sponsors_value)
                        queue_update(row_updates, row, 'Calendar', calendar_value)
                        if history_value != gsheet.at[index, 'History']:
                            history_report_updates += 1
                            _inc_stat("history_updates")
                            history_report = history_report + f"""
                            <tr>
                                <th>{r_state}</th>
                                <th>{r_bnum.strip()}</th>
                                <th>{history_value.replace(gsheet.at[index, 'History'], "")}</th>
                            </tr>
                            """
                        queue_update(row_updates, row, 'History', history_value)
                        queue_update(row_updates, row, 'Bill ID', str(bill_id))
                        queue_update(row_updates, row, 'PDF', texts_value)
                    elif row_missing_details(row):
                        logger.debug("Backfilling missing details for %s %s", r_state, r_bnum.strip())
                        content = get_bill_details(bill_id, change_hash, session)
                        if content is None:
                            continue
                        bill_details = content
                        sponsors_value = get_sponsors(content["sponsors"])
                        calendar_value = get_calendar(content["calendar"])
                        history_value = get_history(content["history"])
                        texts_value = get_texts(content["texts"])
                        queue_update(row_updates, row, 'Sponsors', sponsors_value)
                        queue_update(row_updates, row, 'Calendar', calendar_value)
                        queue_update(row_updates, row, 'History', history_value)
                        queue_update(row_updates, row, 'Bill ID', str(bill_id))
                        queue_update(row_updates, row, 'PDF', texts_value)

                    if (not r_title) or (not r_la) or (not last_action_date) or (not r_link):
                        if bill_details is None:
                            bill_details = get_bill_details(bill_id, change_hash, session)
                        if bill_details is None:
                            logger.error("Bill details unavailable for %s %s", r_state, r_bnum.strip())
                            continue
                        if not r_title:
                            r_title = bill_details.get("title") or r_title
                        if not r_la:
                            r_la = bill_details.get("last_action") or r_la
                        if not last_action_date:
                            last_action_date = bill_details.get("last_action_date") or bill_details.get("status_date")
                        if not r_link:
                            r_link = bill_details.get("url") or r_link

                    hyperlink = f"=HYPERLINK(\"{r_link}\",\"{r_bnum}\")"
                    queue_update(row_updates, row, 'Number', hyperlink)
                    queue_update(row_updates, row, 'Status', r_la)
                    if last_action_date != None and last_action_date != '':
                        queue_update(row_updates, row, 'Date', last_action_date)
                    else:
                        queue_update(row_updates, row, 'Date', "Unknown")
                    queue_update(row_updates, row, 'Summary', r_title)
                    queue_update(row_updates, row, 'Change Hash', lscan_row["change_hash"])
                    if r_link:
                        queue_update(row_updates, row, 'URL', f"=HYPERLINK(\"{r_link}\",\"{r_link}\")")
                    else:
                        queue_update(row_updates, row, 'URL', "Unknown")
                else:
                    queue_update(row_updates, row, 'Date', "Unknown")
            else:
                queue_update(row_updates, row, 'Date', "Unknown")

        except Exception as e:
            logger.exception("Row processing error: %s", e)
            dev_report_updates += 1
            dev_report = dev_report + "\n" + str(e.args[0])
        if row_updates:
            gsheet.loc[index, list(row_updates.keys())] = list(row_updates.values())
            sheet_changed = True
            for col_name, value in row_updates.items():
                cell_updates.append((index + 2, col_name, value))
    if missing_states:
        logger.warning("Missing state sessions for: %s", ", ".join(sorted(missing_states)))
    gsheet = gsheet.fillna('Unknown')

    #updates the entire google sheet from data frame
    if sheet_changed:
        logger.info("Updating worksheet data for %s %s (%d cells)", year, worksheet, len(cell_updates))
        batch_data = []
        for row_num, col_name, value in cell_updates:
            col_idx = header_to_col.get(col_name)
            if col_idx is None:
                continue
            cell_ref = rowcol_to_a1(row_num, col_idx)
            safe_value = clean_cell_value(value)
            batch_data.append({"range": cell_ref, "values": [[safe_value]]})
        if batch_data:
            wks.batch_update(batch_data, value_input_option='USER_ENTERED')
    if digest:
        save_worksheet_digest(worksheet, year, digest)

    #formats google sheet when headers change or first run
    if should_format_sheet(worksheet, year, expected_headers):
        logger.info("Formatting worksheet: %s", worksheet)
        wks.format("A2:K400", {'textFormat': {"fontSize": 12, "fontFamily": "Lexend"}})
        wks.format("G2:G400", {'textFormat': {"fontSize": 12, "fontFamily": "Lexend", }, "horizontalAlignment": "CENTER"})
        wks.format("E2:E400", {'textFormat': {"fontSize": 12, "fontFamily": "Lexend", }, "numberFormat": {"type": "DATE"}, "horizontalAlignment": "CENTER"})
        wks.format("B2:E400", {'textFormat': {"fontSize": 12, "fontFamily": "Lexend", }, "numberFormat": {"type": "TEXT"}, "horizontalAlignment": "CENTER"})
        wks.format("J2:E400", {'textFormat': {"fontSize": 12, "fontFamily": "Lexend", }, "numberFormat": {"type": "TEXT"}, "horizontalAlignment": "CENTER"})
        wks.format("Q2:E400", {'textFormat': {"fontSize": 12, "fontFamily": "Lexend", }, "numberFormat": {"type": "TEXT"}, "horizontalAlignment": "CENTER"})
        mark_sheet_formatted(worksheet, year, expected_headers)


    #does one more pull of the updated sheet then saves it as the previous sheet for next run
    expected_headers = wks.row_values(1)
    gsheet = pd.DataFrame(wks.get_all_records(expected_headers=expected_headers)).astype(object)
    gsheet = gsheet.fillna('')
    gsheet.to_csv(os.path.join(CACHE_DIR, f"gsheet-{worksheet}-{year}.csv"))
    mark_run_success(worksheet, year)

def main():
    _set_stat("last_run_started", time.time())
    _set_stat("last_run_status", "running")
    for key in ["legiscan_calls", "bill_cache_hits", "bill_cache_misses", "new_bills", "changed_bills", "history_updates"]:
        _set_stat(key, 0)
    start_time = time.monotonic()
    session = requests.Session()
    try:
        for year in years:
            all_lists = get_main_lists(year, session)
            rollover_lists = get_main_lists(year - 1, session)
            update_worksheet(year, "Anti-LGBTQ Bills", "🚨ALERT NEW BILL 🚨", "🏛 Status Change 🏛", session, all_lists)
            update_worksheet(year, "Pro-LGBTQ Bills", "🌈NEW GOOD BILL 🏳️‍", "🌈Status Change 🏛", session, all_lists)
            update_worksheet(year, "Rollover Anti-LGBTQ Bills", "🚨ALERT ROLLOVER BILL 🚨", "🏛 Status Change 🏛", session, all_lists, rollover=True, rollover_lists=rollover_lists)
            update_worksheet(year, "Rollover Pro-LGBTQ Bills", "🌈ROLLOVER GOOD BILL 🏳️", "🏛 Status Change 🏛", session, all_lists, rollover=True, rollover_lists=rollover_lists)
    except Exception:
        logger.exception("Run failed")
        _set_stat("last_run_status", "error")
        raise

    # if dev_report_updates > 0:
    #     notify_dev_team("Error occured with latest bot run!", dev_report)
    # # notify_world("Latest Changes", world_report)
    # if history_report_updates > 0:
    #     send_history_report(history_report)
    # if new_report_updates > 0:
    #     send_new_report(new_report)
    _set_stat("last_run_finished", time.time())
    _set_stat("last_run_duration_seconds", round(time.monotonic() - start_time, 3))
    if get_stats().get("last_run_status") != "error":
        _set_stat("last_run_status", "ok")

if __name__ == "__main__":
        main()
