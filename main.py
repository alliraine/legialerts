import os.path
import requests
import gspread
import json
import hashlib

import pandas as pd
import time

from utils.get_sessions import get_sessions_dataframe
from utils.notify import notify_world, notify_dev_team, notify_legi_team, send_history_report, send_new_report, \
    notify_social
from utils.legiscan_helper import get_calendar, get_sponsors, get_history, get_texts

from dotenv import load_dotenv

load_dotenv()

#ordered list based on legiscan state id
STATES = ["Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado", "Connecticut", "Delaware", "Florida",
          "Georgia", "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky", "Louisiana",
          "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota", "Mississippi", "Missouri", "Montana",
          "Nebraska", "Nevada", "New Hampshire", "New Jersey", "New Mexico", "New York", "North Carolina",
          "North Dakota", "Ohio", "Oklahoma", "Oregon", "Pennsylvania", "Rhode Island", "South Carolina",
          "South Dakota", "Tennessee", "Texas", "Utah", "Vermont", "Virginia", "Washington", "West Virginia",
          "Wisconsin", "Wyoming", "DC", "US"]

curr_path = os.path.dirname(__file__)

legi_key = os.environ.get('legiscan_key')
Master_List_URL = f"https://api.legiscan.com/?key={legi_key}&op=getMasterListRaw&id="
Bill_URL = f"https://api.legiscan.com/?key={legi_key}&op=getBill&id="

years = [2025]

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
BILL_CACHE_DIR = os.path.join(curr_path, "cache", "bills")
LEGISCAN_MIN_INTERVAL = float(os.environ.get("LEGISCAN_MIN_INTERVAL", "0"))
_last_legiscan_call = 0.0

def legiscan_get(url, session):
    global _last_legiscan_call
    if LEGISCAN_MIN_INTERVAL > 0:
        now = time.monotonic()
        elapsed = now - _last_legiscan_call
        if elapsed < LEGISCAN_MIN_INTERVAL:
            time.sleep(LEGISCAN_MIN_INTERVAL - elapsed)
    response = session.get(url)
    _last_legiscan_call = time.monotonic()
    return response

def load_bill_cache(bill_id, expected_change_hash):
    cache_path = os.path.join(BILL_CACHE_DIR, f"{bill_id}.json")
    if not os.path.exists(cache_path):
        return None
    try:
        with open(cache_path, "r") as handle:
            cached = json.load(handle)
        if cached.get("change_hash") == expected_change_hash:
            return cached.get("bill")
    except Exception:
        return None
    return None

def save_bill_cache(bill_id, change_hash, bill):
    os.makedirs(BILL_CACHE_DIR, exist_ok=True)
    cache_path = os.path.join(BILL_CACHE_DIR, f"{bill_id}.json")
    with open(cache_path, "w") as handle:
        json.dump({"change_hash": change_hash, "bill": bill}, handle)

def get_bill_details(bill_id, change_hash, session):
    cached = load_bill_cache(bill_id, change_hash)
    if cached is not None:
        return cached
    r = legiscan_get(Bill_URL + str(bill_id), session)
    content = r.json()["bill"]
    save_bill_cache(bill_id, change_hash, content)
    return content

def row_missing_details(row):
    required_fields = ["Sponsors", "Calendar", "History", "PDF", "Bill ID"]
    for field in required_fields:
        value = row.get(field)
        if value is None:
            return True
        if isinstance(value, str) and value.strip() in ("", "Unknown"):
            return True
    return False

def sheet_has_missing_details(gsheet):
    for _, row in gsheet.iterrows():
        if row_missing_details(row):
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
    digest_path = os.path.join(curr_path, "cache", f"digest-{safe_name}-{year}.txt")
    if not os.path.exists(digest_path):
        return None
    try:
        with open(digest_path, "r") as handle:
            return handle.read().strip()
    except Exception:
        return None

def save_worksheet_digest(worksheet, year, digest):
    safe_name = worksheet.replace(" ", "_").replace("/", "_")
    digest_path = os.path.join(curr_path, "cache", f"digest-{safe_name}-{year}.txt")
    os.makedirs(os.path.dirname(digest_path), exist_ok=True)
    with open(digest_path, "w") as handle:
        handle.write(digest)

def get_main_lists(year, session):
    session_list_file = f"{curr_path}/cache/sessions.csv"

    all_lists = {}

    # pull new session list every 24 hours
    if (not os.path.exists(session_list_file)) or (os.path.getmtime(session_list_file)) <= time.time() - 1 * 60 * 60 * 24:
        df = get_sessions_dataframe(session=session, request_fn=lambda url: legiscan_get(url, session))
    else:
        print("Loading sessions_list from Cache")
        df = pd.read_csv(session_list_file)

    SESSIONS = df.loc[((df['year_start'] == year) | (df['year_end'] == year)) & (df['special'] == 0)]

    for idx, s in SESSIONS.iterrows():
        # set helpful vars
        s_id = s.get("session_id")
        state_id = s.get("state_id")
        s_name = STATES[state_id - 1]
        s_year = str(s.get("year_start"))
        s_files = [f"{curr_path}/cache/" + s_name + "-" + s_year + ".csv"]

        # if this session extends more than one year we want to make sure we use it for both years
        if s.get("year_start") != s.get("year_end"):
            s_files.append(f"{curr_path}/cache/" + s_name + "-" + str(s.get("year_end")) + ".csv")

        for s_file in s_files:
            # checks cache if stale or doesn't exist pull (we can pull new data every hour)
            if (not os.path.exists(s_file)) or (os.path.getmtime(s_file)) <= time.time() - 3 * 60 * 60:
                print("Cache doesn't exist or is stale. Pulling from Legiscan")
                # Pull session master list from Legiscan
                r = legiscan_get(Master_List_URL + str(s_id), session)
                print(Master_List_URL + str(s_id))
                content = r.json()["masterlist"]
                temp_list = []
                for attribute, value in content.items():
                    if attribute != "session":
                        temp_list.append(value)
                all_lists[s_name] = pd.DataFrame(temp_list)

                # save to csv
                all_lists[s_name].to_csv(s_file)
            else:
                print("Loading from Cache")
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

def queue_update(row_updates, row, column, value):
    current = row.get(column)
    if pd.isna(current):
        current = ""
    if current != value:
        row_updates[column] = value

def should_format_sheet(worksheet, year, headers):
    safe_name = worksheet.replace(" ", "_").replace("/", "_")
    flag_path = os.path.join(curr_path, "cache", f"format-{safe_name}-{year}.txt")
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
    flag_path = os.path.join(curr_path, "cache", f"format-{safe_name}-{year}.txt")
    header_signature = "|".join(headers)
    os.makedirs(os.path.dirname(flag_path), exist_ok=True)
    with open(flag_path, "w") as handle:
        handle.write(header_signature)

def update_worksheet(year, worksheet, new_title, change_title, session, all_lists, rollover = False, rollover_lists = None):
    global world_report, history_report, dev_report, new_report, new_report_updates, history_report_updates, dev_report_updates
    print(f"starting {year} {worksheet}")
    if rollover and rollover_lists is not None:
        all_lists = rollover_lists
    if rollover:
        all_lists = rollover_lists or get_main_lists(year-1, session)
    master_index = build_master_index(all_lists)

    #open google sheets api account
    gc = gspread.service_account_from_dict(json.loads(os.environ.get('gsuite_service_account')))

    #open worksheet
    wks = gc.open_by_key(os.environ.get('gsheet_key_' + str(year))).worksheet(worksheet)
    expected_headers = wks.row_values(1)

    #loads worksheet into dataframe
    print(expected_headers)
    gsheet = pd.DataFrame(wks.get_all_records(expected_headers=expected_headers))
    gsheet = gsheet.fillna('')

    #gets previous sheet from file
    if os.path.exists(f"{curr_path}/cache/gsheet-{worksheet}-{year}.csv"):
        prev_gsheet = pd.read_csv(f"{curr_path}/cache/gsheet-{worksheet}-{year}.csv")
    else:
        prev_gsheet = gsheet

    digest = worksheet_legiscan_digest(gsheet, master_index)
    previous_digest = load_worksheet_digest(worksheet, year)
    if digest and previous_digest == digest and not sheet_has_missing_details(gsheet):
        print("No LegiScan changes detected; skipping worksheet update")
        return

    sheet_changed = False
    for index, row in gsheet.iterrows():
        try:
            row_updates = {}
            r_state = row["State"].strip()
            r_bnum = row["Number"]
            r_btype = row["Bill Type"]
            queue_update(row_updates, row, 'Youth State Risk', f"=VLOOKUP(A{index+2},'Risk Levels'!$A$4:$E$55,2)")
            queue_update(row_updates, row, 'Adult State Risk', f"=VLOOKUP(A{index+2},'Risk Levels'!$A$4:$E$55,3)")
            if not all_lists[r_state].empty:
                lscan_row = master_index.get(r_state, {}).get(r_bnum.strip())
                if lscan_row is not None:
                    r_la = lscan_row["last_action"]
                    r_title = lscan_row["title"]
                    r_link = lscan_row["url"]
                    bill_id = lscan_row["bill_id"]
                    change_hash = lscan_row["change_hash"]
                    prev = prev_gsheet.loc[(prev_gsheet["State"] == row["State"]) & (prev_gsheet["Number"] == row["Number"])]

                    #checks if the bill is recently added. If not then alert new bill
                    if prev.empty or gsheet.at[index, 'Change Hash'] == "":
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
                        print("Bill Change Found")
                        t = f"{change_title}\n📜Bill: {r_state} {r_bnum.strip()} \n📑Title: {r_title}\n🏷️Bill Type: {r_btype}\n🏛Status: {r_la} \n🔗Bill Text: {r_link}"
                        notify_social(t)
                        content = get_bill_details(bill_id, change_hash, session)

                        sponsors_value = get_sponsors(content["sponsors"])
                        calendar_value = get_calendar(content["calendar"])
                        history_value = get_history(content["history"])
                        texts_value = get_texts(content["texts"])
                        queue_update(row_updates, row, 'Sponsors', sponsors_value)
                        queue_update(row_updates, row, 'Calendar', calendar_value)
                        if history_value != gsheet.at[index, 'History']:
                            history_report_updates += 1
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
                        content = get_bill_details(bill_id, change_hash, session)
                        sponsors_value = get_sponsors(content["sponsors"])
                        calendar_value = get_calendar(content["calendar"])
                        history_value = get_history(content["history"])
                        texts_value = get_texts(content["texts"])
                        queue_update(row_updates, row, 'Sponsors', sponsors_value)
                        queue_update(row_updates, row, 'Calendar', calendar_value)
                        queue_update(row_updates, row, 'History', history_value)
                        queue_update(row_updates, row, 'Bill ID', str(bill_id))
                        queue_update(row_updates, row, 'PDF', texts_value)

                    hyperlink = f"=HYPERLINK(\"{r_link}\",\"{r_bnum}\")"
                    queue_update(row_updates, row, 'Number', hyperlink)
                    queue_update(row_updates, row, 'Status', lscan_row["last_action"])
                    if lscan_row["last_action_date"] != None and lscan_row["last_action_date"] != '':
                        queue_update(row_updates, row, 'Date', lscan_row["last_action_date"])
                    else:
                        queue_update(row_updates, row, 'Date', "Unknown")
                    queue_update(row_updates, row, 'Summary', lscan_row["title"])
                    queue_update(row_updates, row, 'Change Hash', lscan_row["change_hash"])
                    queue_update(row_updates, row, 'URL', f"=HYPERLINK(\"{r_link}\",\"{r_link}\")")
                else:
                    queue_update(row_updates, row, 'Date', "Unknown")
            else:
                queue_update(row_updates, row, 'Date', "Unknown")

        except Exception as e:
            print("Ran into error", e)
            dev_report_updates += 1
            dev_report = dev_report + "\n" + str(e.args[0])
        if row_updates:
            gsheet.loc[index, list(row_updates.keys())] = list(row_updates.values())
            sheet_changed = True
    gsheet = gsheet.fillna('Unknown')

    #updates the entire google sheet from data frame
    if sheet_changed:
        wks.update([gsheet.columns.values.tolist()] + gsheet.values.tolist(), value_input_option='USER_ENTERED')
    if digest:
        save_worksheet_digest(worksheet, year, digest)

    #formats google sheet when headers change or first run
    if should_format_sheet(worksheet, year, expected_headers):
        wks.format("A2:K400", {'textFormat': {"fontSize": 12, "fontFamily": "Lexend"}})
        wks.format("G2:G400", {'textFormat': {"fontSize": 12, "fontFamily": "Lexend", }, "horizontalAlignment": "CENTER"})
        wks.format("E2:E400", {'textFormat': {"fontSize": 12, "fontFamily": "Lexend", }, "numberFormat": {"type": "DATE"}, "horizontalAlignment": "CENTER"})
        wks.format("B2:E400", {'textFormat': {"fontSize": 12, "fontFamily": "Lexend", }, "numberFormat": {"type": "TEXT"}, "horizontalAlignment": "CENTER"})
        wks.format("J2:E400", {'textFormat': {"fontSize": 12, "fontFamily": "Lexend", }, "numberFormat": {"type": "TEXT"}, "horizontalAlignment": "CENTER"})
        wks.format("Q2:E400", {'textFormat': {"fontSize": 12, "fontFamily": "Lexend", }, "numberFormat": {"type": "TEXT"}, "horizontalAlignment": "CENTER"})
        mark_sheet_formatted(worksheet, year, expected_headers)


    #does one more pull of the updated sheet then saves it as the previous sheet for next run
    expected_headers = wks.row_values(1)
    gsheet = pd.DataFrame(wks.get_all_records(expected_headers=expected_headers))
    gsheet.to_csv(f"{curr_path}/cache/gsheet-{worksheet}-{year}.csv")

def main():
    session = requests.Session()
    for year in years:
        all_lists = get_main_lists(year, session)
        rollover_lists = get_main_lists(year - 1, session)
        update_worksheet(year, "Anti-LGBTQ Bills", "🚨ALERT NEW BILL 🚨", "🏛 Status Change 🏛", session, all_lists)
        update_worksheet(year, "Pro-LGBTQ Bills", "🌈NEW GOOD BILL 🏳️‍", "🌈Status Change 🏛", session, all_lists)
        update_worksheet(year, "Rollover Anti-LGBTQ Bills", "🚨ALERT ROLLOVER BILL 🚨", "🏛 Status Change 🏛", session, all_lists, rollover=True, rollover_lists=rollover_lists)
        update_worksheet(year, "Rollover Pro-LGBTQ Bills", "🌈ROLLOVER GOOD BILL 🏳️", "🏛 Status Change 🏛", session, all_lists, rollover=True, rollover_lists=rollover_lists)

    if dev_report_updates > 0:
        notify_dev_team("Error occured with latest bot run!", dev_report)
    # notify_world("Latest Changes", world_report)
    if history_report_updates > 0:
        send_history_report(history_report)
    if new_report_updates > 0:
        send_new_report(new_report)

if __name__ == "__main__":
    while True:
        print("running")
        main()
        print("sleeping")
        time.sleep(899)
