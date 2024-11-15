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


def search(term, page, interactive):
    global ignore_list
    Search_URL = f"https://api.legiscan.com/?key={legi_key}&op=getSearch&state=ALL&page={page}&query="
    r = requests.get(Search_URL + str(term))
    content = r.json()["searchresult"]
    for e in content:
        if e != "summary":
            bill = content[
                e]  # {'relevance': 98, 'state': 'MI', 'bill_number': 'HJRE', 'bill_id': 1771836, 'change_hash': 'de6b4d0f455fe65d8c9f3f44fa911121', 'url': 'https://legiscan.com/MI/bill/HJRE/2023', 'text_url': 'https://legiscan.com/MI/text/HJRE/2023', 'research_url': 'https://legiscan.com/MI/research/HJRE/2023', 'last_action_date': '2023-06-15', 'last_action': 'Printed Joint Resolution Filed 06/14/2023', 'title': "Women: other; women's bill of rights; provide for. Amends the state constitution by adding sec. 29 to art. I."}
            # lscan = prev_gsheet.loc[(prev_gsheet["State"] == abbrev_to_us_state[bill["state"]]) & (prev_gsheet["Number"] == bill["bill_number"]) & (prev_gsheet["Summary"] == bill["title"])]
            #
            # lscan2 = prev_gsheet2.loc[(prev_gsheet2["State"] == abbrev_to_us_state[bill["state"]]) & (prev_gsheet2["Number"] == bill["bill_number"]) & (prev_gsheet2["Summary"] == bill["title"])]
            #
            # lscan3 = prev_gsheet3.loc[(prev_gsheet3["State"] == abbrev_to_us_state[bill["state"]]) & (prev_gsheet3["Number"] == bill["bill_number"]) & (prev_gsheet3["Summary"] == bill["title"])]
            #
            # lscan4 = prev_gsheet4.loc[(prev_gsheet4["State"] == abbrev_to_us_state[bill["state"]]) & (prev_gsheet4["Number"] == bill["bill_number"]) & (prev_gsheet4["Summary"] == bill["title"])]
            #
            # lscan5 = prev_gsheet5.loc[(prev_gsheet5["State"] == abbrev_to_us_state[bill["state"]]) & (prev_gsheet5["Number"] == bill["bill_number"]) & (prev_gsheet5["Summary"] == bill["title"])]

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
                if bill["last_action_date"] is not None:
                    if datetime.strptime(bill["last_action_date"], '%Y-%m-%d') == datetime(2024, 11, 15):
                        print(color.RED, bill["last_action_date"], abbrev_to_us_state[bill["state"]], bill["bill_number"],
                          bill["title"], bill["text_url"], color.END)
                    elif datetime.strptime(bill["last_action_date"], '%Y-%m-%d') > datetime(2024, 11, 15):
                        print(color.YELLOW, bill["last_action_date"], abbrev_to_us_state[bill["state"]], bill["bill_number"],
                              bill["title"], bill["text_url"], color.END)
                    elif datetime.strptime(bill["last_action_date"], '%Y-%m-%d') > datetime(2024, 11, 13):
                        print(bill["last_action_date"], abbrev_to_us_state[bill["state"]], bill["bill_number"],
                              bill["title"], bill["text_url"])
                else:
                    print(bill["last_action_date"], abbrev_to_us_state[bill["state"]], bill["bill_number"],
                      bill["title"], bill["text_url"])
                if interactive:
                    u_input = input('Do you want to add this bill?\n')
                    while u_input.lower() not in ('y', 'n', 's'):
                        print(u_input.lower() + "  is not a valid answer\n")
                        print(abbrev_to_us_state[bill["state"]], bill["bill_number"], bill["title"], bill["text_url"])
                        u_input = input('Do you want to add this bill?\n')
                    if u_input.lower() == "n":
                        df2 = pd.DataFrame([[bill["bill_id"], bill["state"], bill["bill_number"],
                                             datetime.strptime(bill["last_action_date"], '%Y-%m-%d').strftime(
                                                 "%-d/%-m/%Y")]],
                                           columns=["bill_id", "state", "bill_number", "last_action_date"])
                        ignore_list = pd.concat([ignore_list, df2], ignore_index=True)
                    if u_input.lower() == "s":
                        ignore_list.to_json("../cache/ignore_list.json")

    if content["summary"]["page_total"] > page:
        search(term, page + 1, interactive)


# open google sheets api account
gc = gspread.service_account_from_dict(json.loads(os.environ.get('gsuite_service_account')))

# open worksheet
wks = gc.open_by_key(os.environ.get('gsheet_key_2024')).sheet1
expected_headers = wks.row_values(1)

# loads worksheet into dataframe
prev_gsheet = pd.DataFrame(wks.get_all_records(expected_headers=expected_headers))

# open worksheet
wks2 = gc.open_by_key(os.environ.get('gsheet_key_2025')).worksheet("Pro-LGBTQ Bills")
expected_headers2 = wks2.row_values(1)

# loads worksheet into dataframe
prev_gsheet2 = pd.DataFrame(wks2.get_all_records(expected_headers=expected_headers2))

# open worksheet
wks3 = gc.open_by_key(os.environ.get('gsheet_key_2025')).sheet1
expected_headers3 = wks3.row_values(1)

# loads worksheet into dataframe
prev_gsheet3 = pd.DataFrame(wks3.get_all_records(expected_headers=expected_headers3))

# open worksheet
wks4 = gc.open_by_key(os.environ.get('gsheet_key_2025')).worksheet("Pro-LGBTQ Bills")
expected_headers4 = wks4.row_values(1)

# loads worksheet into dataframe
prev_gsheet4 = pd.DataFrame(wks4.get_all_records(expected_headers=expected_headers4))

# open worksheet
wks5 = gc.open_by_key(os.environ.get('gsheet_key_2024')).worksheet("Rollover Anti-LGBTQ Bills")
expected_headers5 = wks5.row_values(1)

# loads worksheet into dataframe
prev_gsheet5 = pd.DataFrame(wks5.get_all_records(expected_headers=expected_headers5))


ignore_list = pd.read_json("../cache/ignore_list.json")

print("Welcome to LegiAlerts Search!\n\n ")
u_input = input('Please enter your search terms:\n')

if u_input == "bill pass":
    print("\nDrag Bills:\n")
    search("\"drag\" NOT \"race\" NOT \"racing\"", 1, False)
    print("\nBiological Sex Bills:\n")
    search("\"biological sex\"", 1, False)
    print("\nGender Affirming Bills:\n")
    search("\"gender affirming\"", 1, False)
    print("\nPronouns Bills:\n")
    search("\"pronouns\"", 1, False)
    print("\nFemale impersonator Bills:\n")
    search("\"female impersonator\"", 1, False)
    print("\nGender Reassignment Bills:\n")
    search("\"gender reassignment\"", 1, False)
    print("\nSex Reassignment Bills:\n")
    search("\"sex reassignment\"", 1, False)
    print("\nCross Sex Bills:\n")
    search("\"cross sex\"", 1, False)
    print("\nObscene Bills:\n")
    search("\"obscene\"", 1, False)
    print("\nGroom Bills:\n")
    search("\"groom\"", 1, False)

    print("\nGeneral Polyamory terms:\n")
    search("\"polyamory\"", 1, False)
    search("\"multiple partners\"", 1, False)

    print("\nErin's Search Terms")
    search("\"Biological sex\" or \"puberty\" or \"hormone\" or \"bathroom\" or \"restroom\" or \"gender marker\" or "
           "\"sex marker\" or \"sex designation\" or \"gender affirming\" Or \"drag\" OR \"gender change\" or "
           "\"transgender\"", 1, False)

else:
    search(u_input, 1, False)

ignore_list.to_json("../cache/ignore_list.json")
