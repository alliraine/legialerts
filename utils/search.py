import json
import os.path
import pickle
from datetime import datetime

import gspread
import requests
import pandas as pd

from dotenv import load_dotenv

from us_state_abbrv import abbrev_to_us_state

load_dotenv()

legi_key = os.environ.get('legiscan_key')
u_input = ""

curr_path = os.path.dirname(__file__)


class color:
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    DARKCYAN = '\033[36m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'


def search(term, page):
    global ignore_list
    Search_URL = f"https://api.legiscan.com/?key={legi_key}&op=getSearch&state=ALL&page={page}&query="
    r = requests.get(Search_URL + str(term))
    content = r.json()["searchresult"]
    bills = []
    for e in content:
        if e != "summary":
            bill = content[e]  # {'relevance': 98, 'state': 'MI', 'bill_number': 'HJRE', 'bill_id': 1771836, 'change_hash': 'de6b4d0f455fe65d8c9f3f44fa911121', 'url': 'https://legiscan.com/MI/bill/HJRE/2023', 'text_url': 'https://legiscan.com/MI/text/HJRE/2023', 'research_url': 'https://legiscan.com/MI/research/HJRE/2023', 'last_action_date': '2023-06-15', 'last_action': 'Printed Joint Resolution Filed 06/14/2023', 'title': "Women: other; women's bill of rights; provide for. Amends the state constitution by adding sec. 29 to art. I."}

            lscan = prev_gsheet.loc[(prev_gsheet["Bill ID"] == bill["bill_id"]) | (
                        (prev_gsheet["State"] == abbrev_to_us_state[bill["state"]]) & (
                            prev_gsheet["Number"] == bill["bill_number"]) & (prev_gsheet["Summary"] == bill["title"]))]

            lscan2 = prev_gsheet2.loc[(prev_gsheet2["Bill ID"] == bill["bill_id"]) | (
                        (prev_gsheet2["State"] == abbrev_to_us_state[bill["state"]]) & (
                            prev_gsheet2["Number"] == bill["bill_number"]) & (
                                    prev_gsheet2["Summary"] == bill["title"]))]

            lscan3 = prev_gsheet3.loc[(prev_gsheet3["Bill ID"] == bill["bill_id"]) | (
                        (prev_gsheet3["State"] == abbrev_to_us_state[bill["state"]]) & (
                            prev_gsheet3["Number"] == bill["bill_number"]) & (
                                    prev_gsheet3["Summary"] == bill["title"]))]

            lscan4 = prev_gsheet4.loc[(prev_gsheet4["Bill ID"] == bill["bill_id"]) | (
                        (prev_gsheet4["State"] == abbrev_to_us_state[bill["state"]]) & (
                            prev_gsheet4["Number"] == bill["bill_number"]) & (
                                    prev_gsheet4["Summary"] == bill["title"]))]

            lscan5 = prev_gsheet5.loc[(prev_gsheet5["Bill ID"] == bill["bill_id"]) | (
                        (prev_gsheet5["State"] == abbrev_to_us_state[bill["state"]]) & (
                            prev_gsheet5["Number"] == bill["bill_number"]) & (
                                    prev_gsheet5["Summary"] == bill["title"]))]

            lscan6 = ignore_list.loc[(ignore_list["bill_id"] == bill["bill_id"])]

            if lscan.empty and lscan2.empty and lscan3.empty and lscan4.empty and lscan5.empty and lscan6.empty:
                bills.append(bill)

    if content["summary"]["page_total"] > page:
        bills.extend(search(term, page + 1))
    return bills


# open google sheets api account
gc = gspread.service_account_from_dict(json.loads(os.environ.get('gsuite_service_account')))

# open worksheet
wks = gc.open_by_key(os.environ.get('gsheet_key_2024')).worksheet("Anti-LGBTQ Bills")
expected_headers = wks.row_values(1)

# loads worksheet into dataframe
prev_gsheet = pd.DataFrame(wks.get_all_records(expected_headers=expected_headers))

# open worksheet
wks2 = gc.open_by_key(os.environ.get('gsheet_key_2025')).worksheet("Pro-LGBTQ Bills")
expected_headers2 = wks2.row_values(1)

# loads worksheet into dataframe
prev_gsheet2 = pd.DataFrame(wks2.get_all_records(expected_headers=expected_headers2))

# open worksheet
wks3 = gc.open_by_key(os.environ.get('gsheet_key_2025')).worksheet("Anti-LGBTQ Bills")
expected_headers3 = wks3.row_values(1)

# loads worksheet into dataframe
prev_gsheet3 = pd.DataFrame(wks3.get_all_records(expected_headers=expected_headers3))

# open worksheet
wks4 = gc.open_by_key(os.environ.get('gsheet_key_2024')).worksheet("Pro-LGBTQ Bills")
expected_headers4 = wks4.row_values(1)

# loads worksheet into dataframe
prev_gsheet4 = pd.DataFrame(wks4.get_all_records(expected_headers=expected_headers4))

# open worksheet
wks5 = gc.open_by_key(os.environ.get('gsheet_key_2024')).worksheet("Rollover Anti-LGBTQ Bills")
expected_headers5 = wks5.row_values(1)

# loads worksheet into dataframe
prev_gsheet5 = pd.DataFrame(wks5.get_all_records(expected_headers=expected_headers5))


ignore_list = pd.read_json("../cache/ignore_list.json")

bills = []

print("Welcome to LegiAlerts Search!\n\n ")
# u_input = input('Please enter your search terms:\n')

# print("\nDrag Bills:\n")
bills.extend(search("\"drag\" NOT \"race\" NOT \"racing\"", 1))
# print("\nBiological Sex Bills:\n")
bills.extend(search("\"biological sex\"", 1))
# print("\nGender Affirming Bills:\n")
bills.extend(search("\"gender affirming\"", 1))
# print("\nPronouns Bills:\n")
bills.extend(search("\"pronouns\"", 1))
# print("\nFemale impersonator Bills:\n")
bills.extend(search("\"female impersonator\"", 1))
# print("\nGender Reassignment Bills:\n")
bills.extend(search("\"gender reassignment\"", 1))
# print("\nSex Reassignment Bills:\n")
bills.extend(search("\"sex reassignment\"", 1))
# print("\nCross Sex Bills:\n")
bills.extend(search("\"cross sex\"", 1))
# print("\nObscene Bills:\n")
bills.extend(search("\"obscene\"", 1))
# print("\nGroom Bills:\n")
bills.extend(search("\"groom\"", 1))
#
# print("\nGeneral Polyamory terms:\n")
bills.extend(search("\"polyamory\"", 1))
bills.extend(search("\"multiple partners\"", 1))
#
# print("\nErin's Search Terms")
bills.extend(search("\"Biological sex\" or \"puberty\" or \"hormone\" or \"bathroom\" or \"restroom\" or \"gender marker\" or "
        "\"sex marker\" or \"sex designation\" or \"gender affirming\" Or \"drag\" OR \"gender change\" or "
        "\"transgender\"", 1))

bills_seen = []
for bill in bills:
    if bill["bill_id"] not in bills_seen:
        bills_seen.append(bill["bill_id"])
        if bill["last_action_date"] is not None:
            if datetime.strptime(bill["last_action_date"], '%Y-%m-%d') == datetime(2025, 1, 17):
                print(color.RED, bill["last_action_date"], abbrev_to_us_state[bill["state"]], bill["bill_number"],
                      bill["title"], bill["text_url"], color.END)
            elif datetime.strptime(bill["last_action_date"], '%Y-%m-%d') > datetime(2025, 1, 16):
                print(color.YELLOW, bill["last_action_date"], abbrev_to_us_state[bill["state"]], bill["bill_number"],
                      bill["title"], bill["text_url"], color.END)
            elif datetime.strptime(bill["last_action_date"], '%Y-%m-%d') > datetime(2025, 1, 15):
                print(bill["last_action_date"], abbrev_to_us_state[bill["state"]], bill["bill_number"],
                      bill["title"], bill["text_url"])
        else:
            print(bill["last_action_date"], abbrev_to_us_state[bill["state"]], bill["bill_number"],
                  bill["title"], bill["text_url"])

print (f"completed at {datetime.now()}")