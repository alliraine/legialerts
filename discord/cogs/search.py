import json
import logging
import os
import time

import discord
import gspread
import pandas as pd
from discord.ext import commands
import requests

from utils.risk import RISK, COLOR
from utils.us_state_abbrv import abbrev_to_us_state

curr_path = os.path.dirname(__file__)

# open google sheets api account
gc = gspread.service_account(filename=f"{curr_path}/legialerts.json")
sheets = gc.open_by_key(os.environ.get('gsheet_key'))

# open worksheet
wks = sheets.sheet1
wks2 = sheets.worksheet("Pro-LGBTQ Bills")
wks3 = sheets.worksheet("Search Ignore")

def next_available_row(worksheet):
    str_list = list(filter(None, worksheet.col_values(1)))
    return str(len(str_list) + 1)

class Bill:
    def __init__(self, state, number, title, link ):
        self.state = state
        self.number = number
        self.title = title
        self.link = link
        self.risk = RISK[abbrev_to_us_state[self.state]]
        self.color = COLOR[self.risk]

class ProBillType(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    @discord.ui.select( # the decorator that lets you specify the properties of the select menu
        placeholder = "Choose a Bill Type!", # the placeholder text that will be displayed if nothing is selected
        min_values = 1, # the minimum number of values that must be selected by the users
        max_values = 1, # the maximum number of values that can be selected by the users
        options = [ # the list of options from which users can choose, a required field
            discord.SelectOption(
                label="Birth Certificate Or Identification",
            ),
            discord.SelectOption(
                label="Broad Nondiscrimination",
            ),
            discord.SelectOption(
                label="Commissions, Task Forces, and Studies",
            ),
            discord.SelectOption(
                label="Conversion Therapy Ban",
            ),
            discord.SelectOption(
                label="Employment Nondiscrimination",
            ),
            discord.SelectOption(
                label="Gender Affirming Care Protections",
            ),
            discord.SelectOption(
                label="Hate Crimes/Aggravating Circumstances",
            ),
            discord.SelectOption(
                label="Health Care Equity",
            ),
            discord.SelectOption(
                label="Housing Nondiscrimination",
            ),
            discord.SelectOption(
                label="Inclusive Bathrooms",
            ),
            discord.SelectOption(
                label="Insurance Nondiscrimination",
            ),
            discord.SelectOption(
                label="Job Nondiscrimination",
            ),
            discord.SelectOption(
                label="Language Bill",
            ),
            discord.SelectOption(
                label="LGBTQ+ Inclusive Curriculum",
            ),
            discord.SelectOption(
                label="Marriage Equality",
            ),
            discord.SelectOption(
                label="Nondiscrimination In Long-Term Care",
            ),
            discord.SelectOption(
                label="Panic Legal Defense Abolition",
            ),
            discord.SelectOption(
                label="Prison Nondiscrimination",
            ),
            discord.SelectOption(
                label="Provider Protections",
            ),
            discord.SelectOption(
                label="Repeal of Anti-Trans Law",
            ),
            discord.SelectOption(
                label="Safe State Bill",
            ),
        ]
    )
    async def select_callback(self, select, interaction): # the function called when the user is done selecting options
        split_msg = self.message.content.split('|')
        state = split_msg[0]
        num = split_msg[1]
        b_type = select.values[0]

        wks = gc.open_by_key(os.environ.get('gsheet_key')).worksheet("Pro-LGBTQ Bills")
        next_row = next_available_row(wks)
        wks.update_acell("A{}".format(next_row), state)
        wks.update_acell("B{}".format(next_row), num)
        wks.update_acell("D{}".format(next_row), b_type)

        for child in self.children:  # loop through all the children of the view
            child.disabled = True  # set the button to disabled

        await interaction.response.edit_message(content=f"Added {state} {num} under type {b_type} to Pro-LGBTQ List!", view=self)
class AntiBillType(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    @discord.ui.select( # the decorator that lets you specify the properties of the select menu
        placeholder = "Choose a Bill Type!", # the placeholder text that will be displayed if nothing is selected
        min_values = 1, # the minimum number of values that must be selected by the users
        max_values = 1, # the maximum number of values that can be selected by the users
        options = [ # the list of options from which users can choose, a required field
            discord.SelectOption(
                label="Allows Parents to change schools based on LGBTQ Curriculum",
            ),
            discord.SelectOption(
                label="Anti-Boycotts Act",
            ),
            discord.SelectOption(
                label="Ban on Public Investment in ESG Funds",
            ),
            discord.SelectOption(
                label="Bans trans people from working at shelters",
            ),
            discord.SelectOption(
                label="Birth Certificate Change Ban",
            ),
            discord.SelectOption(
                label="Book Ban",
            ),
            discord.SelectOption(
                label="Conversion Therapy Legalization",
            ),
            discord.SelectOption(
                label="Defining Trans People Out of the Law",
            ),
            discord.SelectOption(
                label="DEI Prohibitation",
            ),
            discord.SelectOption(
                label="Denial of GAC can't be considered Child Abuse",
            ),
            discord.SelectOption(
                label="Don't Say Gay/Forced Outing",
            ),
            discord.SelectOption(
                label="Drag Ban",
            ),
            discord.SelectOption(
                label="Eliminates Human Rights Enforcement",
            ),
            discord.SelectOption(
                label="Ends tax deductions for Gender Affirming Care",
            ),
            discord.SelectOption(
                label="Forced Misgendering",
            ),
            discord.SelectOption(
                label="Gender Affirming Care Ban",
            ),
            discord.SelectOption(
                label="Legal Discrimination In Education",
            ),
            discord.SelectOption(
                label="Legal Discrimination in Healthcare",
            ),
            discord.SelectOption(
                label="Medicaid Ban",
            ),
            discord.SelectOption(
                label="Prison Placement",
            ),
            discord.SelectOption(
                label="Prohibits Gender Identity Instruction",
            ),
            discord.SelectOption(
                label="Anti-LGBTQ Resolution",
            ),
            discord.SelectOption(
                label="Same-Sex Marriage Discrimination",
            ),
            discord.SelectOption(
                label="Trans Bathroom Ban",
            ),
            discord.SelectOption(
                label="Trans Sports Ban",
            ),
        ]
    )
    async def select_callback(self, select, interaction): # the function called when the user is done selecting options
        print(await interaction.original_response())
        split_msg = self.message.content.split('|')
        state = split_msg[0]
        num = split_msg[1]
        b_type = select.values[0]

        wks = gc.open_by_key(os.environ.get('gsheet_key')).worksheet("Anti-LGBTQ Bills")
        next_row = next_available_row(wks)
        wks.update_acell("A{}".format(next_row), state)
        wks.update_acell("B{}".format(next_row), num)
        wks.update_acell("D{}".format(next_row), b_type)

        for child in self.children:  # loop through all the children of the view
            child.disabled = True  # set the button to disabled

        await interaction.response.edit_message(content=f"Added {state} {num} under type {b_type} to Anti-LGBTQ List!", view=self)
class SearchButtonView(discord.ui.View): # Create a class called MyView that subclasses discord.ui.View
    def __init__(self):
        super().__init__(timeout=None)
    @discord.ui.button(label="Anti-LGBTQ", row=0, style=discord.ButtonStyle.danger, emoji="🚨") # Create a button with the label "😎 Click me!" with color Blurple
    async def anti_button_callback(self, button, interaction):
        split_msg = self.message.content.split('|')
        state = split_msg[0]
        num = split_msg[1]

        await interaction.response.edit_message(content=self.message.content+"|",  view=AntiBillType()) # Send a message when the button is clicked

    @discord.ui.button(label="Pro-LGBTQ", row=0, style=discord.ButtonStyle.primary,
                       emoji="🌈")  # Create a button with the label "😎 Click me!" with color Blurple
    async def pro_button_callback(self, button, interaction):
        split_msg = self.message.content.split('|')
        state = split_msg[0]
        num = split_msg[1]
        await interaction.response.edit_message(content=self.message.content, view=ProBillType())  # Send a message when the button is clicked

    @discord.ui.button(label="Ignore", row=0, style=discord.ButtonStyle.secondary,
                       emoji="🤫")  # Create a button with the label "😎 Click me!" with color Blurple
    async def ignore_button_callback(self, button, interaction):
        split_msg = self.message.content.split('|')
        state = split_msg[0]
        num = split_msg[1]

        wks = gc.open_by_key(os.environ.get('gsheet_key')).worksheet("Search Ignore")
        next_row = next_available_row(wks)
        wks.update_acell("A{}".format(next_row), state)
        wks.update_acell("B{}".format(next_row), num)

        for child in self.children:  # loop through all the children of the view
            child.disabled = True  # set the button to disabled

        await interaction.response.edit_message(
            content=f"Added {state} {num} to Ignore List", view=self)  # Send a message when the button is clicked

class Search(commands.Cog): # create a class for our cog that inherits from commands.Cog
    # this class is used to create a cog, which is a module that can be added to the bot

    def find(self, term, page, prev_gsheet, prev_gsheet2, prev_gsheet3):
        legi_key = os.environ.get('legiscan_key')

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

        bill_list = []

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
                    bill_list.append(Bill(bill["state"], bill["bill_number"], bill["title"], bill["text_url"]))
        if content["summary"]["page_total"] > page:
            return bill_list + self.find(term, page + 1, prev_gsheet, prev_gsheet2, prev_gsheet3)
        else:
            return bill_list

    def __init__(self, bot): # this is a special method that is called when the cog is loaded
        self.bot = bot

    @discord.slash_command() # we can also add application commands
    async def search(self, ctx, input: str):
        await ctx.defer()
        # loads worksheet into dataframe
        expected_headers = wks.row_values(1)
        prev_gsheet = pd.DataFrame(wks.get_all_records(expected_headers=expected_headers))

        expected_headers2 = wks2.row_values(1)
        prev_gsheet2 = pd.DataFrame(wks2.get_all_records(expected_headers=expected_headers2))

        expected_headers3 = wks3.row_values(1)
        prev_gsheet3 = pd.DataFrame(wks3.get_all_records(expected_headers=expected_headers3))

        all_bills = self.find(input, 1, prev_gsheet, prev_gsheet2, prev_gsheet3)
        await ctx.followup.send(f"Filtered Search Results for: **{input}** \n\n")
        print(all_bills, type(all_bills))
        if len(all_bills) > 0:
            for bill in all_bills:
                embed = discord.Embed(title=f"{bill.state} {bill.number}", url=f"{bill.link}",
                                      description=f"{bill.title}",
                                      color=bill.color)
                embed.add_field(name="State Risk",
                                value=f"{bill.risk}", inline=False)
                embed.set_thumbnail(url="https://pbs.twimg.com/profile_images/1612291939142868995/EkXB9DX9_400x400.jpg")

                await ctx.send(f"{abbrev_to_us_state[bill.state]}|{bill.number}|({all_bills.index(bill)+1}/{len(all_bills)})", embed=embed, view=SearchButtonView())
        else:
            await ctx.send("No New Bills Found")

def setup(bot): # this is called by Pycord to setup the cog
    bot.add_cog(Search(bot)) # add the cog to the bot