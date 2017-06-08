import discord
from discord.ext import commands
import asyncio
import logging
from cogs.utils import checks
from cogs.utils.dataIO import dataIO
from cogs.utils.chat_formatting import box
import os
import copy

log = logging.getLogger('red.register')
FOLDER_PATH = "data/register"
SETTINGS_PATH = "{}/settings.json"
DEFAULT_SETTINGS = {
    "roles": [],
    "delete_after": None
}
REMOVE = "removed from"
ADD = "assigned to"


class Register:
    """Allows users to register for certain roles."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.settings = dataIO.load_json(SETTINGS_PATH)

    @commands.command(pass_context=True, no_pm=True)
    async def register(self, ctx: commands.Context, *, role_name: str=''):
        """Gives the user a role

        Valid roles can be added using !regedit
        Example usage: !register PC"""
        server = ctx.message.server
        user = ctx.message.author
        task = None # Whether we are removing or adding a role, or doing nothing
        delete_after = None # set if the 'quiet' option is on
        msg = ''
        if server.id not in self.settings:
            return
        if role_name:
            role = next((r for r in server.roles if r.name == role_name and 
                         r.id in self.settings[server.id]["roles"]), None)
            if role is None:
                msg = "You can't register for that role.".format(role_name)
            else:
                try:
                    if role not in user.roles:
                        task = ADD
                        await self.bot.add_roles(user, role)
                    else:
                        task = REMOVE
                        await self.bot.remove_roles(user, role)
                    msg = "The {} role has been {} {}.".format(role_name, task, user.display_name)
                except discord.errors.Forbidden:
                    if not server.me.manage_roles:
                        msg = "I don't have the `Manage Roles` permission."
                    elif role > server.me.top_role:
                        msg = "I cannot manage roles higher than my top role's position."
                    else:
                        msg = "I don't have permission to do that."
        else:
            # --- SEND VALID ROLES ---
            if server.id in self.settings and self.settings[server.id]["roles"]:
                valid_roles = [r.name for r in server.roles if r.id in self.settings[server.id]["roles"]]
                msg = box("Valid register roles in {}:\n"
                        "{}"
                        "".format(server.name, ", ".join(sorted(valid_roles)))
                        )
            else:
                msg = "Register isn't enabled in this server."
        delete_after = self.settings[server.id]["delete_after"]
        await self.bot.say(msg, delete_after=delete_after)
        if delete_after is not None:
            await asyncio.sleep(delete_after)
            await self.bot.delete_message(ctx.message)

    @commands.group(pass_context=True, no_pm=True)
    @checks.admin_or_permissions(administrator=True)
    async def regedit(self, ctx: commands.Context):
        """Manages valid register roles."""
        if ctx.invoked_subcommand is None:
            # Send server's current settings
            server = ctx.message.server
            await self.bot.send_cmd_help(ctx)
            if server.id not in self.settings:
                msg = box("Register is not enabled in this server. "
                          "Use [p]regedit addrole to enable it.")
            else:
                valid_roles = [r.name for r in server.roles if r.id in self.settings[server.id]["roles"]]
                delete_after = self.settings[server.id]["delete_after"]
                quiet_status = None
                if delete_after is None:
                    quiet_status = "Quiet mode is disabled."
                else:
                    quiet_status = "Register commands are cleaned up after {} seconds".format(delete_after)
                msg = box("{}\n"
                          "Valid register roles:\n"
                          "{}"
                          "".format(quiet_status, ", ".join(sorted(valid_roles)) if valid_roles else None)
                          )
            await self.bot.say(msg)

    @regedit.command(name="addrole", pass_context=True, no_pm=True)
    async def _regedit_addrole(self, ctx: commands.Context, *, role_name: str):
        """Adds a register role."""
        server = ctx.message.server
        if server.id not in self.settings:
            self._json_server_check(server.id)
        role_id = next((r.id for r in server.roles if r.name == role_name and
                       r.id not in self.settings[server.id]["roles"]), None)
        if role_id is None:
            await self.bot.say("Couldn't add that role to register. "
                               "Make sure the role exists and isn't already added to register.")
            return
        else:
            self.settings[server.id]["roles"].append(role_id)
            dataIO.save_json(SETTINGS_PATH, self.settings)
            await self.bot.say("Role was successfully added to register.")

    @regedit.command(name="removerole", pass_context=True, no_pm=True)
    async def _regedit_removerole(self, ctx, *, role_name: str):
        """Removes a register role."""
        server = ctx.message.server
        if server.id not in self.settings:
            await self.bot.say("Register is not enabled in this server.")
            return
        role_id = next((r.id for r in server.roles if r.name == role_name and
                       r.id in self.settings[server.id]["roles"]), None)
        if role_id is None:
            await self.bot.say("Couldn't remove that role from register. "
                               "Make sure the role exists and is in register.")
        else:
            self.settings[server.id]["roles"].remove(role_id)
            dataIO.save_json(SETTINGS_PATH, self.settings)
            await self.bot.say("Role was successfully removed from register.")

    @regedit.command(name="quiet", pass_context=True, no_pm=True)
    async def _regedit_quiet(self, ctx, delete_after: float):
        """Make the bot clean up after a user registers.
        
        <delete_after> is how many seconds the bot will wait before cleaning up.
        Set to zero to disable quiet mode."""
        server = ctx.message.server
        if server.id not in self.settings:
            self._json_server_check(server.id)
        if delete_after == 0:
            delete_after = None
        self.settings[server.id]["delete_after"] = delete_after
        msg = "Register commands are now cleaned up after {} seconds.".format(delete_after)
        if delete_after is None:
            msg = "Cleaning up register commands is disabled."
        await self.bot.say(msg)
        dataIO.save_json(SETTINGS_PATH, self.settings)
        
    @commands.command(pass_context=True, no_pm=True)
    @checks.serverowner_or_permissions(manage_roles=True)
    async def giverole(self, ctx, role_name: str, user: discord.Member=None):
        """Gives a role to a user. 
        
        If <user> is not specified, it gives the role to whoever invoked the command."""
        author = ctx.message.author
        server = author.server
        if user is None:
            user = author
        role = discord.utils.get(server.roles, name=role_name)
        if role is not None:
            if role not in user.roles and (author.top_role > role or author == server.owner):
                try:
                    await self.bot.add_roles(user, role)
                    await self.bot.say("The `{}` role has been assigned to {}.".format(role.name, user.display_name))
                except discord.errors.Forbidden:
                    await self.bot.say("I do not have permission to add the `{}` role.".format(role.name))
            elif author.top_role <= role and author != server.owner:
                await self.bot.say("You do not have permission to give the `{}` role.".format(role.name))
            else:
                await self.bot.say("{} already has the `{}` role.".format(user.display_name, role.name))
        else:
            await self.bot.say("The `{}` role does not exist. Remember role names are case-sensitive.\n".format(role_name) +
                               "If the role name is more than one word surround it with `\'` or `\"`.")

    @commands.command(pass_context=True, no_pm=True)
    @checks.serverowner_or_permissions(manage_roles=True)
    async def removerole(self, ctx, role_name: str, user: discord.Member=None):
        """Removes a role  from a user.
        
        If <user> is not specified, it removes the role from whoever invoked the command."""
        author = ctx.message.author
        server = author.server
        if user is None:
            user = author
        role_name = role_name.strip('\"\'')
        role = discord.utils.get(server.roles, name=role_name)
        if role is not None:
            if role in user.roles and (author.top_role > role or author == server.owner):
                try:
                    await self.bot.remove_roles(user, role)
                    await self.bot.say("The `{}` role has been removed from {}.".format(role.name, user.display_name))
                except discord.errors.Forbidden:
                    await self.bot.say("I do not have permission to remove the `{}` role.".format(role.name))
            elif author.top_role <= role and author != server.owner:
                await self.bot.say("You do not have permission to remove the `{}` role.".format(role.name))
            else:
                await self.bot.say("{} does not have the `{}` role.".format(user.display_name, role.name))
        else:
            await self.bot.say("The `{}` role does not exist. Remember role names are case-sensitive.\n".format(role_name) +
                               "If the role name is more than one word surround it with `\'` or `\"`.")

    def _json_server_check(self, server_id):
        if server_id not in self.settings:
                log.debug('Adding server({}) in Json'.format(server_id))
                self.settings[server_id] = DEFAULT_SETTINGS
                dataIO.save_json(SETTINGS_PATH, self.settings)
        
def check_folder():
    if not os.path.exists(FOLDER_PATH):
        log.debug("Creating " + FOLDER_PATH + " folder...")
        os.makedirs(FOLDER_PATH)

def check_file():
    if dataIO.is_valid_json(SETTINGS_PATH) is False:
        log.debug('Creating json: settings.json')
        dataIO.save_json(SETTINGS_PATH, {})

def setup(bot):
    check_folder()
    check_file()
    bot.add_cog(Register(bot))
