import discord
from discord.ext import commands
from cogs.utils import checks
from cogs.utils.chat_formatting import pagify, box
from cogs.utils.dataIO import dataIO
import os
import pygsheets
from googleapiclient.errors import HttpError

try:
    from tabulate import tabulate
except Exception as e:
    raise RuntimeError("You must run `pip3 install tabulate`.") from e

PRIVACIES = { # For sheet privacy settings
    "global",
    "server",
    "channel"
}

class GSheets:
    """Display data from Google Sheets in discord!
    
    Get ranges from any Google Sheet (which is shared with the bot), and display it as a table in discord."""

    def __init__(self, bot):
        self.bot = bot
        self.sheets = dataIO.load_json("data/gsheets/sheets.json")
        try:
            self.gc = pygsheets.authorize(outh_file="data/gsheets/client_secret.json", outh_nonlocal=True)
        except:
            bot.say("Something went wrong whilst authorizing.")

    @checks.mod_or_permissions(manage_messages=True)
    @commands.command(pass_context=True, no_pm=True)
    async def addsheet(self, ctx, name: str, url: str, privacy: str="server"):
        """Add a sheet so you can get ranges from it.
        Arguments:
         - <name> Whatever you'd like the name the sheet
         - <url> The URL to the sheet
         - <privacy> (optional) where this sheet can be accessed (global, server or channel)"""
        if privacy not in PRIVACIES:
            await self.bot.say("Invalid privacy option. Must be `global`, `server` or `channel`.")
            return
        try:
            s = self.gc.open_by_url(url)
        except pygsheets.NoValidUrlKeyFound:
            await self.bot.say("That doesn't look like a valid URL.")
            return
        except pygsheets.SpreadsheetNotFound:
            await self.bot.say("Couldn't find that spreadsheet.")
            return
        for p in self.sheets: # Check if name already exists, regardless of privacy
            if name in [s['name'] for s in self.sheets[p]]:
                await self.bot.say("There is already a sheet with that name.")
                return
        sheet = { # Only name and ID is stored, so ranges can be requested later via the name
            "name" : name,
            "id"   : s.id
        }
        if privacy == "global":
            if "global" not in self.sheets:
                self.sheets["global"] = []
            self.sheets["global"].append(sheet)
        else:
            if privacy == "server":
                server = ctx.message.server
                if server.id not in self.sheets:
                    self.sheets[server.id] = []
                self.sheets[server.id].append(sheet)
            elif privacy == "channel":
                channel = ctx.message.channel
                if channel.id not in self.sheets:
                    self.sheets[channel.id] = []
                self.sheets[channel.id].append(sheet)
        dataIO.save_json("data/gsheets/sheets.json", self.sheets)
        await self.bot.say("The sheet has been added.")

    @commands.command(pass_context=True, no_pm=True)
    async def removesheet(self, ctx, name: str):
        """Remove a sheet which has been added.
        Arguments:
         - <name> The name of the sheet to remove"""
        channel = ctx.message.channel
        scopes = ["global", channel.server.id, channel.id]
        sheet = None
        for scope in scopes: # Check if name exists
            if scope not in self.sheets: continue
            sheet = next((s for s in self.sheets[scope] if s["name"] == name), None)
            if sheet is not None:
                self.sheets[scope].remove(sheet)
                # Remove scope if empty
                if not self.sheets[scope]: self.sheets.pop(scope, None)
                dataIO.save_json("data/gsheets/sheets.json", self.sheets)
                await self.bot.say("The sheet has been removed.")
                return
        await self.bot.say("Couldn't find a sheet with that name in your scope.")

    @commands.command(pass_context=True, no_pm=True)
    async def gettable(self, ctx, sheet_name, *ranges: str):
        """Get a range from a sheet and display it as a table.
        The top row is displayed as headers.
        Arguments:
         - <sheet_name> The name of the sheet
         - <ranges> The range(s) to retrieve in A! format
         - <worksheet> (optional) The worksheet to retrieve the range from. Defaults to the first worksheet."""
        channel = ctx.message.channel
        sheet = self.get_sheet(channel, sheet_name)
        if sheet is not None: sheet = sheet["id"]
        else:
            await self.bot.say("Couldn't find a sheet with that name in your scope.")
            return
        table = []
        for range in ranges:
            try:
                if not table:
                    table = self.gc.get_range(sheet, range)
                else:
                    temp_table = self.gc.get_range(sheet, range)
                    i = 0
                    for row in temp_table:
                        if i == len(table):
                            # Make new row. Initialise new row as the length of the previous row before
                            # temp_table[i] was added (maintain correct alignment)
                            table.append([""]*(len(table[i-1]) - len(row)))
                        table[i] += row
                        i += 1
            except HttpError as e:
                await self.bot.say(e._get_reason())
                return
            except:
                await self.bot.say("Invalid range.")
                return
        # Strip table elements of leading/trailing whitespace
        for row in table:
            for cell in row:
                cell = cell.strip()
        headers = table.pop(0)
        msg = '\n%s\n' % tabulate(table, headers)
        msg = pagify(msg)
        for page in msg:
            await self.bot.say(box(page))

    def get_sheet(self, channel, name):
        scopes = ["global", channel.server.id, channel.id]
        sheet = None
        for scope in scopes: # Check if name exists
            if scope not in self.sheets: continue
            sheet = next((s for s in self.sheets[scope] if s["name"] == name), None)
            if sheet is not None: break
        return sheet

def check_folders():
    if not os.path.exists("data/gsheets"):
        print("Creating data/gsheets folder...")
        os.makedirs("data/gsheets")

def check_files():
    f = "data/gsheets/sheets.json"
    if not dataIO.is_valid_json(f):
        dataIO.save_json(f, {})

def setup(bot):
    check_folders()
    check_files()
    f = "data/gsheets/client_secret.json"
    if not dataIO.is_valid_json(f):
        bot.say("I need a client secret file to work.")
        print("I need a client secret file to work.")
    bot.add_cog(GSheets(bot))
