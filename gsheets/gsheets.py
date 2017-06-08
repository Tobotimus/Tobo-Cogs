import os
import re
import httplib2
import discord
from discord.ext import commands
from cogs.utils import checks
from cogs.utils.chat_formatting import pagify, box
from cogs.utils.dataIO import dataIO
from googleapiclient import discovery
from googleapiclient.errors import HttpError
from oauth2client import client, tools
from oauth2client.file import Storage
from argparse import ArgumentParser
try:
    from tabulate import tabulate
except Exception as e:
    raise RuntimeError("You must run `pip3 install tabulate`.") from e

FOLDER_PATH = "data/gsheets"
SHEETS_PATH = "{}/sheets.json".format(FOLDER_PATH)
CREDENTIAL_PATH = "{}/credentials.json".format(FOLDER_PATH)
FLOW_KWARGS = {
    "client_id": "681019046420-g62edq8nu52adniue2400g8eus64a9e7.apps.googleusercontent.com",
    "client_secret": "38xBpRxw44h7-eZcS9kHHZVn",
    "scope": 'https://www.googleapis.com/auth/spreadsheets',
    "redirect_uri": client.OOB_CALLBACK_URN,
    "user_agent": "DiscordBot",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://accounts.google.com/o/oauth2/token"
}
CHANNEL = "channel"
SERVER = "server"
GLOBAL = "global"

class InvalidSheetsURL(Exception):
    pass

class GSheets:
    """Display data from Google Sheets in discord!
    
    Get ranges from any Google Sheet (which is shared with the bot), and display it as a table in discord."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.sheets = dataIO.load_json(SHEETS_PATH)
        self.spreadsheets = None
        self.gc = None
        credentials = self.get_credentials()
        if credentials and not credentials.invalid:
            self.gc = GSheetsClient(credentials)

    @checks.mod_or_permissions(manage_messages=True)
    @commands.command(pass_context=True, no_pm=True)
    async def addsheet(self, ctx: commands.Context, name: str, url: str, privacy: str=SERVER):
        """Add a sheet so you can get ranges from it.
        Arguments:
         - <name> Whatever you'd like the name the sheet
         - <url> The URL to the sheet
         - <privacy> (optional) where this sheet can be accessed (global, server or channel)

        NOTE: Sheets can have conflicting names if they are in different scopes. When getting 
        data from those sheets, it will use the sheet with the most local scope. Also, sheets 
        which are added in a server's default channel cannot have 'channel' privacy.
        """
        if self.gc is None:
            await self.bot.say("You must authorize the cog first. See `[p]authsheets`.")
            return
        channel = ctx.message.channel
        if channel.is_private:
            server_id = None
        else:
            server_id = channel.server.id
        scope = self.get_scope(privacy, channel.id, server_id)
        if scope is None:
            await self.bot.say("Invalid privacy option. Must be `global`, `server` or `channel`.")
            return
        if self.name_in_scope(name, scope):
            await self.bot.say("There is already a sheet with that name in your scope.")
            return
        try:
            s_id = self.gc.check_url(url)
        except InvalidSheetsURL:
            await self.bot.say("That doesn't look like a valid URL.")
            return
        except HttpError as e:
            await self.bot.say(e._get_reason())
            return
        if scope not in self.sheets:
            self.sheets[scope] = {}
        self.sheets[scope][name] = s_id
        dataIO.save_json(SHEETS_PATH, self.sheets)
        await self.bot.say("The sheet has been added.")

    @commands.command(pass_context=True, no_pm=True)
    async def removesheet(self, ctx: commands.Context, name: str):
        """Remove a sheet which has been added.
        Arguments:
         - <name> The name of the sheet to remove"""
        scopes = (ctx.message.channel.id,
                  ctx.message.server.id,
                  GLOBAL)
        for scope in scopes:
            try:
                self.sheets[scope].pop(name)
            except:
                pass
            else:
                dataIO.save_json(SHEETS_PATH, self.sheets)
                await self.bot.say("The sheet has been removed.")
                return
        await self.bot.say("Couldn't find a sheet with that name in your scope.")

    @commands.command(pass_context=True, no_pm=True)
    async def gettable(self, ctx: commands.Context, sheet_name: str, *ranges: str):
        """Get a range from a sheet and display it as a table.
        The top row is displayed as headers.
        Arguments:
         - <sheet_name> The name of the sheet
         - <ranges> The range(s) to retrieve in A! format
         - <worksheet> (optional) The worksheet to retrieve the range from. Defaults to the first worksheet."""
        if self.gc is None:
            await self.bot.say("You must authorize the cog first. See `[p]authsheets`.")
            return
        channel = ctx.message.channel
        sheet_id = self.get_sheet_id(channel, sheet_name)
        if sheet_id is None:
            await self.bot.say("Couldn't find a sheet with that name in your scope.")
            return
        table = []
        for range in ranges:
            try:
                if not table:
                    table = self.gc.get_range(sheet_id, range)
                else:
                    temp_table = self.gc.get_range(sheet_id, range)
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
        if not table:
            await self.bot.say("That range is empty.")
            return
        headers = table.pop(0)
        msg = '\n%s\n' % tabulate(table, headers)
        msg = pagify(msg)
        for page in msg:
            await self.bot.say(box(page))

    @commands.command(pass_context=True)
    @checks.is_owner()
    async def authsheets(self, ctx):
        """Authorize GSheets to use the Google Sheets API."""
        flow = client.OAuth2WebServerFlow(**FLOW_KWARGS)
        authorize_url = flow.step1_get_authorize_url()
        info_message = ("Use the link below to authorize the cog to communicate with Google Sheets, "
                        "then copy the code you recieve and paste it here.")
        warn_message = ("**NOTE**: It is not recommended to authorize the cog using "
                        "your personal Google Account; it is best to create a new Google Account, "
                        "and share any Sheets you would like to access with that google account.")
        embed = discord.Embed(title="Authorize GSheets", url=authorize_url, description=warn_message)
        try:
            await self.bot.say(info_message, embed=embed)
        except discord.errors.Forbidden:
            await self.bot.say("\n\n".join(info_message, authorize_url, warn_message))
        resp = await self.bot.wait_for_message(author=ctx.message.author)
        credentials = None
        if resp:
            try:
                code = resp.content
                credentials = flow.step2_exchange(code)
            except client.FlowExchangeError as e:
                await self.bot.say("Authentication has failed: {}".format(e.args[0]))
                return
        self.gc = GSheetsClient(credentials)
        store = Storage(CREDENTIAL_PATH)
        store.put(credentials)
        credentials.set_store(store)
        await self.bot.say("Authentication successful.")

    def name_in_scope(self, name, scope_id):
        """Returns True if there is already a sheet with the given name in 
        the given scope."""
        return scope_id in self.sheets and name in self.sheets[scope_id]

    def get_sheet_id(self, channel: discord.Channel, name: str):
        """Return the sheet with the given name and context. Returns None 
        if the sheet does not exist."""
        if channel.is_private:
            scopes = (channel.id, GLOBAL)
        else:
            scopes = (channel.id, channel.server.id, GLOBAL)
        for scope in scopes:
            try:
                sheet = self.sheets[scope][name]
            except:
                pass
            else:
                return sheet

    def get_scope(self, privacy, channel_id: str, server_id: str):
        """Get a scope given a sheet's privacy and context. Returns None if 
        privacy option is invalid."""
        return {
            CHANNEL: channel_id,
            SERVER: server_id,
            GLOBAL: GLOBAL
        }.get(privacy, None)

    def get_credentials(self):
        """Gets user credentials from storage.
        
        Returns None if nothing has been stored.
        
        Returns:
            Credentials, the obtained credential.
        """
        try:
            store = Storage(CREDENTIAL_PATH)
            credentials = store.get()
        except:
            return None
        return credentials

class GSheetsClient:

    def __init__(self, credentials):
        http = credentials.authorize(httplib2.Http())
        discoveryUrl = ('https://sheets.googleapis.com/$discovery/rest?'
                        'version=v4')
        self.service = discovery.build('sheets', 'v4', http=http, 
                                       discoveryServiceUrl=discoveryUrl)

    def check_url(self, url):
        """Checks if a URL points to a valid spreadsheet, 
        which can be accessed by the client. 

        Raises InvalidSheetsURL if the spreadsheet's ID could not 
        be found in the URL.
        Raises HttpError if the client could not find or 
        access the spreadsheet.
        
        Returns:
            The spreadsheet's ID.
        """
        _url_key_re_v1 = re.compile(r'key=([^&#]+)')
        _url_key_re_v2 = re.compile(r"/spreadsheets/d/([a-zA-Z0-9-_]+)")
        key = _url_key_re_v1.search(url)
        if key:
            return self.check_key(key.group(1))
        key = _url_key_re_v2.search(url)
        if key:
            return self.check_key(key.group(1))
        raise InvalidSheetsURL()

    def check_key(self, key):
        """Checks if the client can access the sheet with the given 
        key. 

        Raises HttpError if the client could not find or 
        access the spreadsheet.
        
        Returns:
            The spreadsheet's ID.
        """
        self.service.spreadsheets().get(
            spreadsheetId=key).execute()
        return key

    def get_range(self, id: str, range: str):
        result = self.service.spreadsheets().values().get(
            spreadsheetId=id, range=range).execute()
        return result.get('values', [])

def check_folders():
    if not os.path.exists(FOLDER_PATH):
        print("Creating data/gsheets folder...")
        os.makedirs(FOLDER_PATH)

def check_files():
    if not dataIO.is_valid_json(SHEETS_PATH):
        dataIO.save_json(SHEETS_PATH, {})

def setup(bot: commands.Bot):
    check_folders()
    check_files()
    bot.add_cog(GSheets(bot))
