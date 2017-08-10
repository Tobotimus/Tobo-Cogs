"""Module for GSheets cog and API client."""
import re
import httplib2
import discord
from discord.ext.commands import command, guild_only, Context
from core import checks, Config
from core.bot import Red
from core.utils.chat_formatting import pagify, box
from oauth2client import client
from oauth2client.file import Storage
from aiohttp import ClientSession
from tabulate import tabulate

UNIQUE_ID = 0x6e6c4930
FOLDER_PATH = "data/gsheets"
CREDENTIAL_PATH = "{}/credentials.json".format(FOLDER_PATH)
FLOW_KWARGS = {
    "client_id": "681019046420-g62edq8nu52adniue2400g8eus64a9e7.apps.googleusercontent.com",
    "client_secret": "38xBpRxw44h7-eZcS9kHHZVn",
    "scope": 'https://www.googleapis.com/auth/spreadsheets.readonly',
    "redirect_uri": client.OOB_CALLBACK_URN,
    "user_agent": "DiscordBot",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://accounts.google.com/o/oauth2/token"
}
_CHANNEL = "channel"
_GUILD = "server guild"
_GLOBAL = "global"
_PRIVACIES = (_CHANNEL, _GUILD, _GLOBAL)

class GSheetsError(Exception):
    """Base exception for this cog."""
    pass

class InvalidSheetsURL(GSheetsError):
    """URL does not point to a google sheet"""
    pass

class HttpError(GSheetsError):
    """HTTP data was invalid or unexpected"""
    def __init__(self, resp, content):
        super().__init__()
        self.resp = resp
        if not isinstance(content, dict):
            raise TypeError("HTTP content should be dict")
        self.content = content

    def get_reason(self):
        """Calculate the reason for the error from the response content."""
        reason = self.resp.reason
        try:
            reason = self.content['error']['message']
        except (ValueError, KeyError, TypeError):
            pass
        return reason

    def __repr__(self):
        return '<HttpError %s "%s">' % (self.resp.status, self.get_reason())

    __str__ = __repr__

class GSheets:
    """Display data from Google Sheets in discord!

    Get ranges from any Google Sheet (which is shared with the bot),
     and display it as a table in discord.
    """

    def __init__(self, bot: Red):
        self.bot = bot
        self.conf = Config.get_conf(self, unique_identifier=UNIQUE_ID,
                                    force_registration=True)
        self.conf.register_global(
            sheets={}
        )
        self.conf.register_guild(
            sheets={}
        )
        self.conf.register_channel(
            sheets={}
        )

        self.sheets_client = None
        credentials = _get_credentials()
        if credentials and not credentials.invalid:
            self.sheets_client = GSheetsClient(credentials)

    @command()
    @guild_only()
    @checks.mod_or_permissions(manage_messages=True)
    async def addsheet(self, ctx: Context, name: str, url: str,
                       privacy: str = _GUILD):
        """Add a sheet so you can get ranges from it.
        Arguments:
         - <name> Whatever you'd like the name the sheet
         - <url> The URL to the sheet
         - <privacy> (optional) where this sheet can be accessed (global, server or channel)

        NOTE: Sheets can have conflicting names if they are in different scopes. When getting
         data from those sheets, it will use the sheet with the most local scope. Also, sheets
         which are added in a server's default channel cannot have 'channel' privacy.
        """
        reply = ''
        if self.sheets_client is None:
            reply = "You must authorize the cog first. See `[p]authsheets`."
        else:
            try:
                s_id = await self.sheets_client.check_url(url)
            except InvalidSheetsURL:
                reply = "That doesn't look like a valid URL."
            except HttpError as err:
                reply = err.get_reason()
            else:
                config = self._get_config(ctx, privacy=privacy)
                sheets = config.sheets()
                if name in sheets:
                    await ctx.send('This will overwrite the current sheet with the same name.'
                                   ' Are you sure you want to do this? (Y/N)')
                    response = await self.bot.wait_for('message', check=_reply_msg_pred(ctx))
                    if response is None or response.content.lower() not in ('y', 'yes'):
                        reply = 'Adding the sheet has been cancelled.'
                if 'cancelled' not in reply:
                    sheets[name] = s_id
                    await config.set('sheets', sheets)
                    reply = "The sheet has been added."
        await ctx.send(reply)

    @command()
    @guild_only()
    async def removesheet(self, ctx: Context, name: str):
        """Remove a sheet which has been added.
        Arguments:
         - <name> The name of the sheet to remove
        """
        reply = ''
        config = self._get_config(ctx, name=name)
        if not config:
            reply = "Couldn't find a sheet with that name in your scope."
        else:
            sheets = config.sheets()
            del sheets[name]
            await config.set('sheets', sheets)
            reply = "Sheet successfully removed."
        await ctx.send(reply)

    @command()
    @guild_only()
    async def gettable(self, ctx: Context, sheet_name: str, *ranges: str):
        """Get a range from a sheet and display it as a table.
        The top row is displayed as headers.
        Arguments:
         - <sheet_name> The name of the sheet
         - <ranges> The range(s) to retrieve in A! format
         - <worksheet> (optional) The worksheet to retrieve the range from. Defaults
         to the first worksheet.
        """
        if self.sheets_client is None:
            await ctx.send("You must authorize the cog first. See `[p]authsheets`.")
            return
        sheet_id = self._get_sheet_id(ctx, sheet_name)
        if sheet_id is None:
            await ctx.send("Couldn't find a sheet with that name in your scope.")
            return
        table = []
        for _range in ranges:
            try:
                if not table:
                    table = await self.sheets_client.get_range(sheet_id, _range)
                else:
                    temp_table = await self.sheets_client.get_range(sheet_id, _range)
                    i = 0
                    for row in temp_table:
                        if i == len(table):
                            table.append([""]*(len(table[i-1]) - len(row)))
                        table[i] += row
                        i += 1
            except HttpError as err:
                await ctx.send(err.get_reason())
                return
        if not table:
            await ctx.send('That range is empty.')
            return
        headers = table.pop(0)
        msg = '\n%s\n' % tabulate(table, headers)
        msg = pagify(msg)
        for page in msg:
            await ctx.send(box(page))

    @command()
    @checks.is_owner()
    async def authsheets(self, ctx: Context):
        """Authorize GSheets to use the Google Sheets API."""
        flow = client.OAuth2WebServerFlow(**FLOW_KWARGS)
        authorize_url = flow.step1_get_authorize_url()
        info_message = ("Use the link below to authorize the cog to communicate with "
                        "Google Sheets, then copy the code you recieve and paste it here.")
        warn_message = ("**NOTE**: It is not recommended to authorize the cog using "
                        "your personal Google Account; it is best to create a new Google Account, "
                        "and share any Sheets you would like to access with that google account.")
        embed = discord.Embed(title="Authorize GSheets",
                              url=authorize_url, description=warn_message)
        try:
            await ctx.send(info_message, embed=embed)
        except discord.errors.Forbidden:
            await ctx.send("\n\n".join((info_message, authorize_url, warn_message)))
        resp = await self.bot.wait_for('message', check=_reply_msg_pred(ctx))
        credentials = None
        if resp:
            try:
                code = resp.content
                http = httplib2.Http()
                credentials = flow.step2_exchange(code, http=http)
            except client.FlowExchangeError as err:
                await ctx.send("Authentication has failed: {}".format(err.args[0]))
                return
        self.sheets_client = GSheetsClient(credentials)
        store = Storage(CREDENTIAL_PATH)
        store.put(credentials)
        credentials.set_store(store)
        await ctx.send("Authentication successful.")

    def _get_config(self, ctx: Context, *,
                    privacy: str = None,
                    name: str = None):
        if privacy:
            if privacy in _CHANNEL:
                return self.conf.channel(ctx.channel)
            if privacy in _GUILD:
                return self.conf.guild(ctx.guild)
            if privacy in _GLOBAL:
                return self.conf
        elif name:
            return next((self._get_config(ctx, privacy=privacy) for privacy in _PRIVACIES
                         if name in self._get_config(ctx, privacy=privacy).sheets()),
                        None)

    def _get_sheet_id(self, ctx: Context, name: str):
        config = self._get_config(ctx, name=name)
        if config:
            return config.sheets()[name]

def _reply_msg_pred(ctx: Context):
    def _pred(msg: discord.Message):
        return msg.author == ctx.author and msg.channel == ctx.channel
    return _pred

def _get_credentials():
    """Gets user credentials from storage.

    Returns None if nothing has been stored.

    Returns:
        Credentials, the obtained credential.
    """
    try:
        store = Storage(CREDENTIAL_PATH)
        credentials = store.get()
    except client.Error:
        return None
    return credentials

class GSheetsClient:
    """Interface to get data from google sheets.

    This module should be thread-safe. Currently, all
     requests are done using the aiohttp library except for
     refreshing access tokens, which is done using a new
     instance of httplib2.Http for every request. (getting
     the initial access token isn't done in this class).
    """

    def __init__(self, credentials: client.OAuth2Credentials):
        self.credentials = credentials
        self.session = ClientSession()

    async def check_url(self, url):
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
            return await self.check_key(key.group(1))
        key = _url_key_re_v2.search(url)
        if key:
            return await self.check_key(key.group(1))
        raise InvalidSheetsURL()

    async def check_key(self, key):
        """Checks if the client can access the sheet with the given
         key.

        Raises HttpError if the client could not find or
         access the spreadsheet.

        Returns:
            The spreadsheet's ID.
        """
        url = "https://sheets.googleapis.com/v4/spreadsheets/{spreadsheetId}"
        resp = await self.get(url.format(spreadsheetId=key))
        if resp.status == 200:
            return key
        else:
            raise HttpError(resp=resp, content=await resp.json())

    async def get_range(self, sheet_id: str, sheet_range: str):
        """Gets a range from a google sheet given its ID, and returns
         the range as a list of lists with the major dimension being
         rows.
        """
        url = ("https://sheets.googleapis.com/v4/spreadsheets/"
               "{spreadsheetId}/values/{range}?majorDimension=ROWS")
        resp = await self.get(url.format(spreadsheetId=sheet_id, sheet_range=sheet_range))
        if resp.status == 200:
            body = await resp.json()
            return body.get('values', [])
        else:
            raise HttpError(resp=resp, content=await resp.json())

    async def request(self, method, url: str):
        """Perform an authorized http request. Applies
         access token from credentials to headers and refreshes
         access token if needed.

        Token refresh is done using a httplib2.Http() instance.
         This is still thread-safe because a new instance is being
         passed in for a single optional request.
        """
        headers = {}
        access_token = self.credentials.get_access_token(httplib2.Http()).access_token
        headers['Authorization'] = 'Bearer ' + access_token
        return await self.session.request(method, url, headers=headers)

    async def get(self, url: str):
        """Perform an authorized http GET request."""
        return await self.request('GET', url)
