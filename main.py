import os.path
from textwrap import wrap

import requests
import gspread

import pandas as pd
import tweepy
import time

from sessions import SESSIONS
from risk import RISK

from dotenv import load_dotenv

#ordered list based on legiscan state id
STATES = ["Alaska", "Alabama", "Arizona", "Arkansas", "California", "Colorado", "Connecticut", "Delaware", "Florida",
          "Georgia", "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky", "Louisiana",
          "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota", "Mississippi", "Missouri", "Montana",
          "Nebraska", "Nevada", "New Hampshire", "New Jersey", "New Mexico", "New York", "North Carolina",
          "North Dakota", "Ohio", "Oklahoma", "Oregon", "Pennsylvania", "Rhode Island", "South Carolina",
          "South Dakota", "Tennessee", "Texas", "Utah", "Vermont", "Virginia", "Washington", "West Virginia",
          "Wisconsin", "Wyoming", "DC", "US"]

all_lists = {}
curr_path = os.path.dirname(__file__)

load_dotenv()

def get_main_lists():
    legi_key = os.environ.get('legiscan_key')
    Master_List_URL = f"https://api.legiscan.com/?key={legi_key}&op=getMasterList&id="
    for idx, s in enumerate(SESSIONS):

        # set helpful vars
        s_id = s.get("session_id")
        s_name = STATES[idx]
        s_file = f"{curr_path}/cache/" + s_name + ".csv"

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


def send_tweet(text, twitter):
    # lets start by splitting by new line
    lines = text.splitlines()

    # now split those lines up if they are too long
    for i, line in enumerate(lines):
        b_line = wrap(line, 280)
        lines.pop(i)
        for idx, l in enumerate(b_line):
            lines.insert(i + idx, l)

    # now combine the lines where possible
    lines = setup_tweets(0, lines)

    # send tweets. thread where needed
    try:
        t_id = None
        for l in lines:
            print(l)
            if t_id is not None:
                print(l)
                r = twitter.create_tweet(text=l, in_reply_to_tweet_id=t_id)
            else:
                print(l)
                r = twitter.create_tweet(text=l)
            t_id = r.data.get("id")
    except:
        print("error sending tweet")

# recursive function for spliting up tweets
def setup_tweets(i, lines):
    if i < len(lines) - 1:
        if len(lines[i]) + len(lines[i + 1]) < 280:
            lines[i] = (lines[i] + "\n" + lines[i + 1])
            lines.pop(i + 1)
            lines = setup_tweets(i, lines)
        else:
            lines = setup_tweets(i + 1, lines)
    return lines


def main():
    print("starting...")
    get_main_lists()
    twitter = tweepy.Client(
        consumer_key=os.environ.get('twitter_consumer_key'),
        consumer_secret=os.environ.get('twitter_consumer_secret'),
        access_token=os.environ.get('twitter_access_token'),
        access_token_secret=os.environ.get('twitter_access_token_secret')
    )

    #open google sheets api account
    gc = gspread.service_account(filename=f"{curr_path}/legialerts.json")

    #open worksheet
    wks = gc.open_by_key(os.environ.get('gsheet_key')).sheet1
    expected_headers = wks.row_values(1)

    #loads worksheet into dataframe
    gsheet = pd.DataFrame(wks.get_all_records(expected_headers=expected_headers))

    #gets previous sheet from file
    if os.path.exists(f"{curr_path}/cache/gsheet.csv"):
        prev_gsheet = pd.read_csv(f"{curr_path}/cache/gsheet.csv")
    else:
        prev_gsheet = gsheet

    for index, row in gsheet.iterrows():
        r_state = row["State"].strip()
        r_bnum = row["Number"]
        if not all_lists[r_state].empty:
            lscan = all_lists[r_state].loc[all_lists[r_state]["number"] == r_bnum.strip()]
            if not lscan.empty:
                r_la = lscan.iloc[0]["last_action"]
                r_title = lscan.iloc[0]["title"]
                r_link = lscan.iloc[0]["url"]
                prev = prev_gsheet.loc[(prev_gsheet["State"] == row["State"]) & (prev_gsheet["Number"] == row["Number"])]

                #checks if the bill is recently added. If not then alert new bill
                if prev.empty or gsheet.at[index, 'Change Hash'] == "":
                    print("New Bill Found")
                    t = f"🚨ALERT NEW BILL 🚨\n------------------------\n📜Bill: {r_state} {r_bnum.strip()} \n📑Title: {r_title} \n🚦Erin Reed's State Risk: {RISK[r_state]} \n🏛Status: {r_la} \n🔗Bill Text:{r_link} "
                    send_tweet(t, twitter)
                #if not new check change hash to see if the bill has changed. If it has trigger an alert
                elif lscan.iloc[0]["change_hash"] != row["Change Hash"]:
                    print("Bill Change Found")
                    t = f"🏛 Status Change 🏛\n📜Bill: {r_state} {r_bnum.strip()} \n📑Title: {r_title} \n🚦Erin Reed's State Risk: {RISK[r_state]} \n🏛Status: {r_la} \n🔗Bill Text:{r_link}"
                    send_tweet(t, twitter)

                r_b = f"=HYPERLINK(\"{r_link}\",\"{r_bnum}\")"
                gsheet.at[index, 'Number'] = r_b
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
    gsheet = pd.DataFrame(wks.get_all_records())
    gsheet.to_csv(f"{curr_path}/cache/gsheet.csv")

if __name__ == "__main__":
    main()
