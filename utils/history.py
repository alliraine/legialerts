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

# open google sheets api account
gc = gspread.service_account(filename=f"{curr_path}/legialerts.json")

# open worksheet
wks = gc.open_by_key(os.environ.get('gsheet_key_2024')).sheet1
expected_headers = wks.row_values(1)
gsheet = pd.DataFrame(wks.get_all_records(expected_headers=expected_headers))

# open worksheet
wks2 = gc.open_by_key(os.environ.get('gsheet_key_2024')).worksheet("Pro-LGBTQ Bills")
expected_headers2 = wks2.row_values(1)
gsheet1 = pd.DataFrame(wks2.get_all_records(expected_headers=expected_headers2))

# open worksheet
wks5 = gc.open_by_key(os.environ.get('gsheet_key_2024')).worksheet("Rollover Anti-LGBTQ Bills")
expected_headers5 = wks5.row_values(1)
gsheet2 = pd.DataFrame(wks5.get_all_records(expected_headers=expected_headers5))

def check_history(index, row, df, date):
    state = row["State"].strip()
    bnum = row["Number"]
    history = row["History"]
    if history.find(date) > -1:
        u_status = input(f'{state} {bnum} has new history!\n\n.'
                         f'{history}\n\n'
                         f'{row["Bill Type"]}\n\n'
                         f'{row["URL"]}\n\n'
                         f'Current status is: {row["Manual Status"]}.'
                         f'\nPlease input new status or press enter to keep current status.\n')
        if u_status != "":
            df.at[index, 'Manual Status'] = u_status

    return df

print("Welcome to LegiAlerts History Search!\n\n ")
u_input = input('Please enter what you want to search:\n')

for index, row in gsheet.iterrows():
    old = gsheet
    gsheet = check_history(index, row, gsheet, u_input)
    print(f"{row['State'].strip()} {row['Number']} status is: {gsheet.at[index, 'Manual Status']}")

#updates the entire google sheet from data frame
wks.update([gsheet.columns.values.tolist()] + gsheet.values.tolist(), value_input_option='USER_ENTERED')

#formats google sheet
wks.format("A2:K400", {'textFormat': {"fontSize": 12, "fontFamily": "Lexend"}})
wks.format("G2:G400", {'textFormat': {"fontSize": 12, "fontFamily": "Lexend", }, "horizontalAlignment": "CENTER"})
wks.format("E2:E400", {'textFormat': {"fontSize": 12, "fontFamily": "Lexend", }, "numberFormat": {"type": "DATE"}, "horizontalAlignment": "CENTER"})

# for index, row in gsheet1.iterrows():
#     old1 = gsheet1
#     gsheet1 = check_history(index, row, gsheet1, u_input)
#     print(f"{row['State'].strip()} {row['Number']} status is: {gsheet1.at[index, 'Manual Status']}")
#
# #updates the entire google sheet from data frame
# wks2.update([gsheet1.columns.values.tolist()] + gsheet1.values.tolist(), value_input_option='USER_ENTERED')
#
# #formats google sheet
# wks2.format("A2:K400", {'textFormat': {"fontSize": 12, "fontFamily": "Lexend"}})
# wks2.format("G2:G400", {'textFormat': {"fontSize": 12, "fontFamily": "Lexend", }, "horizontalAlignment": "CENTER"})
# wks2.format("E2:E400", {'textFormat': {"fontSize": 12, "fontFamily": "Lexend", }, "numberFormat": {"type": "DATE"}, "horizontalAlignment": "CENTER"})

for index, row in gsheet2.iterrows():
    old2 = gsheet2
    gsheet2 = check_history(index, row, gsheet2, u_input)
    print(f"{row['State'].strip()} {row['Number']} status is: {gsheet2.at[index, 'Manual Status']}")

#updates the entire google sheet from data frame
wks5.update([gsheet2.columns.values.tolist()] + gsheet2.values.tolist(), value_input_option='USER_ENTERED')

#formats google sheet
wks5.format("A2:K400", {'textFormat': {"fontSize": 12, "fontFamily": "Lexend"}})
wks5.format("G2:G400", {'textFormat': {"fontSize": 12, "fontFamily": "Lexend", }, "horizontalAlignment": "CENTER"})
wks5.format("E2:E400", {'textFormat': {"fontSize": 12, "fontFamily": "Lexend", }, "numberFormat": {"type": "DATE"}, "horizontalAlignment": "CENTER"})