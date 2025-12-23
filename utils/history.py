import os
from datetime import datetime

import gspread
import pandas as pd
from dotenv import load_dotenv

from utils.config import get_sheet_key, get_tracker_years, load_service_account_credentials

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))


def check_history(index, row, df, needle):
    state = row["State"].strip()
    bnum = row["Number"]
    history = row.get("History", "")
    if history and needle and needle in history:
        u_status = input(
            f'{state} {bnum} has new history!\n\n'
            f'{history}\n\n'
            f'{row.get("Bill Type")}\n\n'
            f'{row.get("URL")}\n\n'
            f'Current status is: {row.get("Manual Status")}.\n'
            f'Please input new status or press enter to keep current status.\n'
        )
        if u_status.strip():
            df.at[index, "Manual Status"] = u_status.strip()
    return df


def update_sheet(wks, df):
    wks.update([df.columns.values.tolist()] + df.values.tolist(), value_input_option="USER_ENTERED")
    wks.format("A2:K400", {"textFormat": {"fontSize": 12, "fontFamily": "Lexend"}})
    wks.format("G2:G400", {"textFormat": {"fontSize": 12, "fontFamily": "Lexend"}, "horizontalAlignment": "CENTER"})
    wks.format(
        "E2:E400",
        {"textFormat": {"fontSize": 12, "fontFamily": "Lexend"}, "numberFormat": {"type": "DATE"}, "horizontalAlignment": "CENTER"},
    )


def process_worksheet(gc, year, worksheet_name, needle):
    try:
        doc = gc.open_by_key(get_sheet_key(year))
        wks = doc.worksheet(worksheet_name)
    except Exception as exc:
        print(f"Unable to open worksheet {worksheet_name} for {year}: {exc}")
        return
    expected_headers = wks.row_values(1)
    gsheet = pd.DataFrame(wks.get_all_records(expected_headers=expected_headers))
    for index, row in gsheet.iterrows():
        gsheet = check_history(index, row, gsheet, needle)
        print(f"{row['State'].strip()} {row['Number']} status is: {gsheet.at[index, 'Manual Status']}")
    update_sheet(wks, gsheet)


def main(needle=None, years=None):
    needle = needle or input("Please enter what you want to search:\n").strip()
    if not needle:
        print("No search term provided. Exiting.")
        return
    target_years = years or get_tracker_years((2026,))
    gc = gspread.service_account_from_dict(load_service_account_credentials())
    for year in target_years:
        for worksheet in ("Anti-LGBTQ Bills", "Pro-LGBTQ Bills", "Rollover Anti-LGBTQ Bills"):
            process_worksheet(gc, year, worksheet, needle)


if __name__ == "__main__":
    print("Welcome to LegiAlerts History Search!\n")
    main()
