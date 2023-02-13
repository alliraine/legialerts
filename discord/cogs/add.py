import os

import discord
import gspread
from discord.ext import commands


def next_available_row(worksheet):
    str_list = list(filter(None, worksheet.col_values(1)))
    return str(len(str_list) + 1)


class Add(commands.Cog): # create a class for our cog that inherits from commands.Cog
    # this class is used to create a cog, which is a module that can be added to the bot

    def __init__(self, bot): # this is a special method that is called when the cog is loaded
        self.bot = bot

    @discord.slash_command() # we can also add application commands
    async def add(self, ctx, state: str, bill: str, type: str, sort: str):
        curr_path = os.path.dirname(__file__)

        if sort not in ["good", "bad", "ignore"]:
            return "list is not good or bad or ignore"
        # open google sheets api account
        gc = gspread.service_account(filename=f"{curr_path}/legialerts.json")

        if sort == "bad":
            # open worksheet
            wks = gc.open_by_key(os.environ.get('gsheet_key')).sheet1
        elif sort == "good":
            # open worksheet
            wks = gc.open_by_key(os.environ.get('gsheet_key')).worksheet("Pro-LGBTQ Bills")
        else:
            wks = gc.open_by_key(os.environ.get('gsheet_key')).worksheet("Search Ignore")
        next_row = next_available_row(wks)
        wks.update_acell("A{}".format(next_row), state)
        wks.update_acell("B{}".format(next_row), bill)
        wks.update_acell("D{}".format(next_row), type)

        await ctx.respond(f'Added {state} {bill} as {type} to {sort}')

def setup(bot): # this is called by Pycord to setup the cog
    bot.add_cog(Add(bot)) # add the cog to the bot