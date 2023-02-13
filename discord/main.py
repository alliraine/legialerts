import logging
import os
from dotenv import load_dotenv

import discord
from discord.ext import commands

# load enviroment vars
load_dotenv()

# setup logging
logging.basicConfig(level=logging.INFO)

# create bot
bot = discord.Bot()

#load cogs
cogs_list = [
    'greetings',
    'search',
    'add',
]

for cog in cogs_list:
    bot.load_extension(f'cogs.{cog}')

# run bot
bot.run(os.getenv('TOKEN'))
