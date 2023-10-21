import os.path

import gspread
import requests
import pandas as pd

from main import curr_path

from dotenv import load_dotenv

from us_state_abbrv import abbrev_to_us_state

load_dotenv()

legi_key = os.environ.get('legiscan_key')
u_input = ""

def search(term, page):
    Search_URL = f"https://api.legiscan.com/?key={legi_key}&op=getSearch&state=ALL&page={page}&query="
    r = requests.get(Search_URL + str(term))
    content = r.json()["searchresult"]
    for e in content:
        if e != "summary":
            bill = content[e]
            lscan = prev_gsheet.loc[(prev_gsheet["Number"] == bill["bill_number"]) & (
                        prev_gsheet["State"] == abbrev_to_us_state[bill["state"]])]

            lscan2 = prev_gsheet2.loc[(prev_gsheet2["Number"] == bill["bill_number"]) & (
                    prev_gsheet2["State"] == abbrev_to_us_state[bill["state"]])]

            if lscan.empty and lscan2.empty:
                print(abbrev_to_us_state[bill["state"]], bill["bill_number"], bill["title"], bill["text_url"])
    if content["summary"]["page_total"] > page:
        search(term, page + 1)

 #open google sheets api account
gc = gspread.service_account(filename=f"{curr_path}/legialerts.json")

#open worksheet
wks = gc.open_by_key(os.environ.get('gsheet_key')).sheet1
expected_headers = wks.row_values(1)

#loads worksheet into dataframe
prev_gsheet = pd.DataFrame(wks.get_all_records(expected_headers=expected_headers))

#open worksheet
wks2 = gc.open_by_key(os.environ.get('gsheet_key')).worksheet("Pro-LGBTQ Bills")
expected_headers2 = wks2.row_values(1)

#loads worksheet into dataframe
prev_gsheet2 = pd.DataFrame(wks2.get_all_records(expected_headers=expected_headers2))


print("Welcome to LegiAlerts Search!\n\n ")
u_input = input('Please enter your search terms:\n')

if u_input == "bill pass":
    print("\nDrag Bills:\n")
    search("\"drag\" NOT \"race\" NOT \"racing\"", 1)
    print("\nBiological Sex Bills:\n")
    search("\"biological sex\"", 1)
    print("\nGender Affirming Bills:\n")
    search("\"gender affirming\"", 1)

else:
    search(u_input, 1)



