import json
import logging
import os
import time

import discord
import gspread
import pandas as pd
from discord.ext import commands
import requests

from us_state_abbrv import abbrev_to_us_state


class Search(commands.Cog): # create a class for our cog that inherits from commands.Cog
    # this class is used to create a cog, which is a module that can be added to the bot

    def find(self, term, page, prev_gsheet, prev_gsheet2, prev_gsheet3):
        legi_key = os.environ.get('legiscan_key')
        curr_path = os.path.dirname(__file__)

        s_file = f"{curr_path}/cache/" + term + str(page) + ".json"

        # checks cache if stale or doesn't exist pull (we can pull new data every hour)
        if (not os.path.exists(s_file)) or (os.path.getmtime(s_file)) <= time.time() - 1 * 60 * 60:
            print("Cache doesn't exist or is stale. Pulling from Legiscan")
            # Pull session master list from Legiscan
            Search_URL = f"https://api.legiscan.com/?key={legi_key}&op=getSearch&state=ALL&page={page}&query="
            logging.info(Search_URL + str(term))
            r = requests.get(Search_URL + str(term))
            content = r.json()["searchresult"]

            # save to csv
            with open(s_file, 'w') as file:
                file.write(json.dumps(content))
        else:
            print("Loading from Cache")
            with open(s_file, 'r') as file:
                content = json.loads(file.read())

        bill_list = ""

        for e in content:
            if e != "summary":
                bill = content[e]
                lscan = prev_gsheet.loc[(prev_gsheet["Number"] == bill["bill_number"]) & (
                        prev_gsheet["State"] == abbrev_to_us_state[bill["state"]])]

                lscan2 = prev_gsheet2.loc[(prev_gsheet2["Number"] == bill["bill_number"]) & (
                        prev_gsheet2["State"] == abbrev_to_us_state[bill["state"]])]

                lscan3 = prev_gsheet3.loc[(prev_gsheet3["Number"] == bill["bill_number"]) & (
                        prev_gsheet3["State"] == abbrev_to_us_state[bill["state"]])]

                if lscan.empty and lscan2.empty and lscan3.empty:
                    bill_list = bill_list + f'{abbrev_to_us_state[bill["state"]]} {bill["bill_number"]} {bill["title"]} {bill["text_url"]}\n'
        if content["summary"]["page_total"] > page:
            return bill_list + self.find(term, page + 1, prev_gsheet, prev_gsheet2, prev_gsheet3)
        else:
            return bill_list

    def __init__(self, bot): # this is a special method that is called when the cog is loaded
        self.bot = bot

    @discord.slash_command() # we can also add application commands
    async def search(self, ctx, input: str):
        await ctx.defer()
        curr_path = os.path.dirname(__file__)

        # open google sheets api account
        gc = gspread.service_account(filename=f"{curr_path}/legialerts.json")
        sheets = gc.open_by_key(os.environ.get('gsheet_key'))

        # open worksheet
        wks = sheets.sheet1
        expected_headers = wks.row_values(1)

        # loads worksheet into dataframe
        prev_gsheet = pd.DataFrame(wks.get_all_records(expected_headers=expected_headers))

        # open worksheet
        wks2 = sheets.worksheet("Pro-LGBTQ Bills")
        expected_headers2 = wks2.row_values(1)

        # loads worksheet into dataframe
        prev_gsheet2 = pd.DataFrame(wks2.get_all_records(expected_headers=expected_headers2))

        # open worksheet
        wks3 = sheets.worksheet("Search Ignore")
        expected_headers3 = wks3.row_values(1)

        # loads worksheet into dataframe
        prev_gsheet3 = pd.DataFrame(wks3.get_all_records(expected_headers=expected_headers3))

        r = f"Filtered Search Results for: **{input}** \n\n{self.find(input, 1, prev_gsheet, prev_gsheet2, prev_gsheet3)}"
        if len(r) > 2000:
            split_list = [r[i:i + 2000] for i in range(0, len(r), 2000)]
            await ctx.followup.send("Sending results...")
            for x in split_list:
                await ctx.send(x)

def setup(bot): # this is called by Pycord to setup the cog
    bot.add_cog(Search(bot)) # add the cog to the bot