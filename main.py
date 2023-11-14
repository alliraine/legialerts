import json
import os.path
import requests
import gspread

import pandas as pd
import tweepy
import time

from utils.get_sessions import get_sessions_dataframe
from utils.risk import RISK
from utils.twitter_helper import send_tweet
from utils.legiscan_helper import get_calendar, get_sponsors, get_history

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
Master_List_URL = f"https://api.legiscan.com/?key={legi_key}&op=getMasterList&id="
Bill_URL = f"https://api.legiscan.com/?key={legi_key}&op=getBill&id="

years = [2023, 2024]

def get_main_lists(year):
    session_list_file = f"{curr_path}/cache/sessions.csv"

    all_lists = {}

    # pull new session list every 24 hours
    if (not os.path.exists(session_list_file)) or (os.path.getmtime(session_list_file)) <= time.time() - 1 * 60 * 60 * 24:
        df = get_sessions_dataframe()
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
        s_file = f"{curr_path}/cache/" + s_name + "-" + s_year + ".csv"

        # checks cache if stale or doesn't exist pull (we can pull new data every hour)
        if (not os.path.exists(s_file)) or (os.path.getmtime(s_file)) <= time.time() - 1 * 60 * 60:
            print("Cache doesn't exist or is stale. Pulling from Legiscan")
            # Pull session master list from Legiscan
            r = requests.get(Master_List_URL + str(s_id))
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

def bad_bills(year):
    print("starting bad bills..")
    all_lists = get_main_lists(year)
    twitter = tweepy.Client(
        consumer_key=os.environ.get('twitter_consumer_key'),
        consumer_secret=os.environ.get('twitter_consumer_secret'),
        access_token=os.environ.get('twitter_access_token'),
        access_token_secret=os.environ.get('twitter_access_token_secret')
    )

    #open google sheets api account
    gc = gspread.service_account(filename=f"{curr_path}/legialerts.json")

    #open worksheet
    wks = gc.open_by_key(os.environ.get('gsheet_key_' + str(year))).sheet1
    expected_headers = wks.row_values(1)

    #loads worksheet into dataframe
    gsheet = pd.DataFrame(wks.get_all_records(expected_headers=expected_headers))

    #gets previous sheet from file
    if os.path.exists(f"{curr_path}/cache/gsheet-{year}.csv"):
        prev_gsheet = pd.read_csv(f"{curr_path}/cache/gsheet-{year}.csv")
    else:
        prev_gsheet = gsheet

    for index, row in gsheet.iterrows():
        r_state = row["State"].strip()
        r_bnum = row["Number"]
        r_btype = row["Bill Type"]
        if not all_lists[r_state].empty:
            lscan = all_lists[r_state].loc[all_lists[r_state]["number"] == r_bnum.strip()]
            if not lscan.empty:
                r_la = lscan.iloc[0]["last_action"]
                r_title = lscan.iloc[0]["title"]
                r_link = lscan.iloc[0]["url"]
                bill_id = lscan.iloc[0]["bill_id"]
                prev = prev_gsheet.loc[(prev_gsheet["State"] == row["State"]) & (prev_gsheet["Number"] == row["Number"])]

                #checks if the bill is recently added. If not then alert new bill
                if prev.empty or gsheet.at[index, 'Change Hash'] == "":
                    print("New Bill Found")
                    t = f"🚨ALERT NEW BILL 🚨\n------------------------\n📜Bill: {r_state} {r_bnum.strip()} \n📑Title: {r_title}\n🏷️Bill Type: {r_btype}\n🚦Erin Reed's State Risk: {RISK[r_state]} \n🏛Status: {r_la} \n🔗Bill Text:{r_link} "
                    send_tweet(t, twitter)
                    r = requests.get(Bill_URL + str(bill_id))
                    content = r.json()["bill"]

                    gsheet.at[index, 'Sponsors'] = get_sponsors(content["sponsors"])
                    gsheet.at[index, 'Calendar'] = get_calendar(content["calendar"])
                    gsheet.at[index, 'History'] = get_history(content["history"])


                #if not new check change hash to see if the bill has changed. If it has trigger an alert
                elif lscan.iloc[0]["change_hash"] != row["Change Hash"] and (lscan.iloc[0]["last_action"] != row["Status"] or lscan.iloc[0]["last_action_date"] != row["Date"]):
                    print("Bill Change Found")
                    t = f"🏛 Status Change 🏛\n📜Bill: {r_state} {r_bnum.strip()} \n📑Title: {r_title}\n🏷️Bill Type: {r_btype}\n🚦Erin Reed's State Risk: {RISK[r_state]} \n🏛Status: {r_la} \n🔗Bill Text:{r_link}"
                    send_tweet(t, twitter)

                    r = requests.get(Bill_URL + str(bill_id))
                    content = r.json()["bill"]

                    gsheet.at[index, 'Sponsors'] = get_sponsors(content["sponsors"])
                    gsheet.at[index, 'Calendar'] = get_calendar(content["calendar"])
                    gsheet.at[index, 'History'] = get_history(content["history"])

                hyperlink = f"=HYPERLINK(\"{r_link}\",\"{r_bnum}\")"
                gsheet.at[index, 'Number'] = hyperlink
                gsheet.at[index, 'Status'] = lscan.iloc[0]["last_action"]
                if lscan.iloc[0]["last_action_date"] != None and lscan.iloc[0]["last_action_date"] != '':
                    gsheet.at[index, 'Date'] = lscan.iloc[0]["last_action_date"]
                else:
                    gsheet.at[index, 'Date'] = "Unknown"
                gsheet.at[index, 'Summary'] = lscan.iloc[0]["title"]
                gsheet.at[index, 'Change Hash'] = lscan.iloc[0]["change_hash"]
                gsheet.at[index, 'URL'] = f"=HYPERLINK(\"{r_link}\",\"{r_link}\")"


            else:
                gsheet.at[index, 'Date'] = "Unknown"
            gsheet.at[index, 'Erin Reed\'s State Risk'] = RISK[r_state]
        else:
            gsheet.at[index, 'Date'] = "Unknown"
            gsheet.at[index, 'Erin Reed\'s State Risk'] = RISK[r_state]
    gsheet = gsheet.fillna('Unknown')

    #updates the entire google sheet from data frame
    wks.update([gsheet.columns.values.tolist()] + gsheet.values.tolist(), value_input_option='USER_ENTERED')

    #formats google sheet
    wks.format("A2:K400", {'textFormat': {"fontSize": 12, "fontFamily": "Lexend"}})
    wks.format("G2:G400", {'textFormat': {"fontSize": 12, "fontFamily": "Lexend", }, "horizontalAlignment": "CENTER"})
    wks.format("E2:E400", {'textFormat': {"fontSize": 12, "fontFamily": "Lexend", }, "numberFormat": {"type": "DATE"}, "horizontalAlignment": "CENTER"})

    #does one more pull of the updated sheet then saves it as the previous sheet for next run
    expected_headers = wks.row_values(1)
    gsheet = pd.DataFrame(wks.get_all_records(expected_headers=expected_headers))
    gsheet.to_csv(f"{curr_path}/cache/gsheet-{year}.csv")

def good_bills(year):
    print("starting good bills...")
    all_lists = get_main_lists(year)
    twitter = tweepy.Client(
        consumer_key=os.environ.get('twitter_consumer_key'),
        consumer_secret=os.environ.get('twitter_consumer_secret'),
        access_token=os.environ.get('twitter_access_token'),
        access_token_secret=os.environ.get('twitter_access_token_secret')
    )

    #open google sheets api account
    gc = gspread.service_account(filename=f"{curr_path}/legialerts.json")

    #open worksheet
    wks = gc.open_by_key(os.environ.get('gsheet_key_' + str(year))).worksheet("Pro-LGBTQ Bills")
    expected_headers = wks.row_values(1)

    #loads worksheet into dataframe
    gsheet = pd.DataFrame(wks.get_all_records(expected_headers=expected_headers))

    #gets previous sheet from file
    if os.path.exists(f"{curr_path}/cache/gsheet_good-{year}.csv"):
        prev_gsheet = pd.read_csv(f"{curr_path}/cache/gsheet_good-{year}.csv")
    else:
        prev_gsheet = gsheet

    for index, row in gsheet.iterrows():
        r_state = row["State"].strip()
        r_bnum = row["Number"]
        r_btype = row["Bill Type"]
        if not all_lists[r_state].empty:
            lscan = all_lists[r_state].loc[all_lists[r_state]["number"] == r_bnum.strip()]
            if not lscan.empty:
                r_la = lscan.iloc[0]["last_action"]
                r_title = lscan.iloc[0]["title"]
                r_link = lscan.iloc[0]["url"]
                bill_id = lscan.iloc[0]["bill_id"]
                prev = prev_gsheet.loc[(prev_gsheet["State"] == row["State"]) & (prev_gsheet["Number"] == row["Number"])]

                #checks if the bill is recently added. If not then alert new bill
                if prev.empty or gsheet.at[index, 'Change Hash'] == "":
                    print("New Bill Found")
                    t = f"🌈NEW GOOD BILL 🏳️‍⚧️\n------------------------\n📜Bill: {r_state} {r_bnum.strip()} \n📑Title: {r_title}\n🏷️Bill Type: {r_btype}\n🚦Erin Reed's State Risk: {RISK[r_state]} \n🏛Status: {r_la} \n🔗Bill Text:{r_link} "
                    send_tweet(t, twitter)
                    r = requests.get(Bill_URL + str(bill_id))
                    content = r.json()["bill"]

                    gsheet.at[index, 'Sponsors'] = get_sponsors(content["sponsors"])
                    gsheet.at[index, 'Calendar'] = get_calendar(content["calendar"])

                #if not new check change hash to see if the bill has changed. If it has trigger an alert
                elif lscan.iloc[0]["change_hash"] != row["Change Hash"] and (lscan.iloc[0]["last_action"] != row["Status"] or lscan.iloc[0]["last_action_date"] != row["Date"]):
                    print("Bill Change Found")
                    t = f"🌈Status Change 🏛\n📜Bill: {r_state} {r_bnum.strip()} \n📑Title: {r_title}\n🏷️Bill Type: {r_btype}\n🚦Erin Reed's State Risk: {RISK[r_state]} \n🏛Status: {r_la} \n🔗Bill Text:{r_link}"
                    send_tweet(t, twitter)

                    r = requests.get(Bill_URL + str(bill_id))
                    content = r.json()["bill"]

                    gsheet.at[index, 'Sponsors'] = get_sponsors(content["sponsors"])
                    gsheet.at[index, 'Calendar'] = get_calendar(content["calendar"])

                hyperlink = f"=HYPERLINK(\"{r_link}\",\"{r_bnum}\")"
                gsheet.at[index, 'Number'] = hyperlink
                gsheet.at[index, 'Status'] = lscan.iloc[0]["last_action"]
                if lscan.iloc[0]["last_action_date"] != None and lscan.iloc[0]["last_action_date"] != '':
                    gsheet.at[index, 'Date'] = lscan.iloc[0]["last_action_date"]
                else:
                    gsheet.at[index, 'Date'] = "Unknown"
                gsheet.at[index, 'Summary'] = lscan.iloc[0]["title"]
                gsheet.at[index, 'Change Hash'] = lscan.iloc[0]["change_hash"]
                gsheet.at[index, 'URL'] = f"=HYPERLINK(\"{r_link}\",\"{r_link}\")"


            else:
                gsheet.at[index, 'Date'] = "Unknown"
            gsheet.at[index, 'Erin Reed\'s State Risk'] = RISK[r_state]
        else:
            gsheet.at[index, 'Date'] = "Unknown"
            gsheet.at[index, 'Erin Reed\'s State Risk'] = RISK[r_state]
    gsheet = gsheet.fillna('Unknown')

    #updates the entire google sheet from data frame
    wks.update([gsheet.columns.values.tolist()] + gsheet.values.tolist(), value_input_option='USER_ENTERED')

    #formats google sheet
    wks.format("A2:K400", {'textFormat': {"fontSize": 12, "fontFamily": "Lexend"}})
    wks.format("G2:G400", {'textFormat': {"fontSize": 12, "fontFamily": "Lexend", }, "horizontalAlignment": "CENTER"})
    wks.format("E2:E400", {'textFormat': {"fontSize": 12, "fontFamily": "Lexend", }, "numberFormat": {"type": "DATE"}, "horizontalAlignment": "CENTER"})

    #does one more pull of the updated sheet then saves it as the previous sheet for next run
    expected_headers = wks.row_values(1)
    gsheet = pd.DataFrame(wks.get_all_records(expected_headers=expected_headers))
    gsheet.to_csv(f"{curr_path}/cache/gsheet_good-{year}.csv")

def main():
    for year in years:
        bad_bills(year)
        good_bills(year)

if __name__ == "__main__":
    main()
