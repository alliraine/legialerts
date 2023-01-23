import os.path

import requests
import pandas as pd

from main import curr_path

from dotenv import load_dotenv

from us_state_abbrv import abbrev_to_us_state

load_dotenv()

legi_key = os.environ.get('legiscan_key')
u_input = ""
prev_gsheet = pd.read_csv(f"{curr_path}/cache/gsheet.csv")

def search(term, page):
    Search_URL = f"https://api.legiscan.com/?key={legi_key}&op=getSearch&state=ALL&page={page}&query="
    r = requests.get(Search_URL + str(u_input))
    content = r.json()["searchresult"]
    for e in content:
        if e != "summary":
            bill = content[e]
            lscan = prev_gsheet.loc[(prev_gsheet["Number"] == bill["bill_number"]) & (
                        prev_gsheet["State"] == abbrev_to_us_state[bill["state"]])]
            if lscan.empty:
                print(abbrev_to_us_state[bill["state"]], bill["bill_number"], bill["title"], bill["text_url"])
    if content["summary"]["page_total"] > page:
        search(term, page + 1)

print("Welcome to LegiAlerts Search!\n\n ")
u_input = input('Please enter your search terms:\n')

search(u_input, 1)



