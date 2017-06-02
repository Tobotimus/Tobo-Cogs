import os
import copy
import asyncio
import logging
import discord
from discord.ext import commands
from cogs.utils import checks
from cogs.utils.dataIO import dataIO
from cogs.utils.chat_formatting import box

log = logging.getLogger('red.register')
default_settings = {
    "roles"     : {},
    "whisper"   : False,
    "delcmds"   : False
}

class Register:
    """Allows users to register for certain roles."""
    
    def __init__(self, bot):
        self.bot = bot
        self.location = 'data/register/settings.json'
        self.json = dataIO.load_json(self.location)

    @commands.command(pass_context=True, no_pm=True)
    async def register(self, ctx, role_name: str=''):
        """Gives the user a role

        Valid roles can be added using !regedit
        Example usage: !register PC"""
        server = ctx.message.server
        user = ctx.message.author
        channel = ctx.message.channel
        if self.json[server.id]["whisper"]:
            channel = user
        if role_name:
            # --- CHECK VALID ROLE ---
            try:
                role = discord.utils.get(server.roles, name=role_name)
                if role.id in self.json[server.id]["roles"]:
                    # VALID ROLE!
                    if role not in user.roles:
                        # --- ADD TO USER ---
                        await self.bot.add_roles(user, role)
                        await self.bot.send_message(channel, '`{}` role has been assigned to you in {}!'.format(role.name, server.name))
                    else:
                        # --- REMOVE FROM USER ---
                        await self.bot.remove_roles(user, role)
                        await self.bot.send_message(channel, '`{}` role has been removed from you in {}!'.format(role.name, server.name))
                else:
                    # ROLE NOT IN REGISTER
                    await self.bot.send_message(channel, 'You can\'t register for `{}` in {}.'.format(role.name, server.name))
            except:
                # ROLE NOT IN SERVER
                await self.bot.send_message(channel, '`{}` isn\'t a role in {}.'.format(role_name, server.name))
        else:
            # NO ROLE GIVEN
            # --- SEND HELP MESSAGE ---
            pages = self.bot.formatter.format_help_for(ctx, ctx.command)
            for page in pages:
                await self.bot.send_message(channel, page)
            # --- SEND VALID ROLES ---
            if server.id in self.json and self.json[server.id]["roles"]:
                valid_roles = []
                for r in self.json[server.id]["roles"]:
                    role = discord.utils.get(server.roles, id=r)
                    if role is None:
                        log.debug("Invalid role ID: {}".format(r))
                        continue
                    else:
                        log.debug(role.id)
                        valid_roles.append(role.name)
                msg = ("Valid register roles in {}:\n"
                        "{}"
                        "".format(server.name, ", ".join(sorted(valid_roles)))
                        )
                await self.bot.send_message(channel, box(msg))
            else:
                msg = "There aren't any roles you can register for in {}".format(server.name)
                await self.bot.send_message(channel, box(msg))
        if self.json[server.id]["delcmds"]:
            await self.bot.delete_message(ctx.message)

    @commands.group(pass_context=True, no_pm=True)
    @checks.admin_or_permissions(administrator=True)
    async def regedit(self, ctx):
        """Manages valid register roles."""
        if ctx.invoked_subcommand is None:
            # Display valid register roles
            server = ctx.message.server
            await self.bot.send_cmd_help(ctx)
            valid_roles = []
            if server.id in self.json:
                for r in self.json[server.id]["roles"]:
                    # Get the role name
                    role = discord.utils.get(server.roles, id=r)
                    if role is None:
                        log.debug("Invalid role ID: {}".format(r))
                        continue
                    else:
                        valid_roles.append(role.name)
            msg = ("Valid register roles:\n"
                   "{}"
                   "".format(", ".join(sorted(valid_roles)))
                   )
            await self.bot.say(box(msg))

    @regedit.command(name="addrole", pass_context=True, no_pm=True)
    async def _regedit_addrole(self, ctx, *, role_name: str):
        """Adds a register role."""
        server = ctx.message.server
        # --- CREATING ROLE ---
        role = discord.utils.get(server.roles, name=role_name)
        if role is None:
            await self.bot.say('The {} role doesn\'t exist! Creating it now!'.format(role_name))
            log.debug('Creating {} role in {}'.format(role_name, server.id))
            try:
                perms = discord.Permissions.none()
                await self.bot.create_role(server, name=role_name, permissions=perms)
                await self.bot.say("Role created!")
            except discord.Forbidden:
                await self.bot.say("I cannot create a role. Please assign Manage Roles to me!")
            role = discord.utils.get(server.roles, name=role_name)
        # --- DONE CREATING ROLE! ---
        self.json_server_check(server)
        # --- ADDING ROLE TO JSON ---
        try:
            if role.id not in self.json[server.id]["roles"]:
                # ROLE NOT IN REGISTER
                self.json[server.id]["roles"][role.id] = {'role_name': role.name}
                dataIO.save_json(self.location, self.json)
                await self.bot.say('``{}`` is now in register.'.format(role.name))
            else:
                # ROLE ALREADY IN REGISTER
                await self.bot.say('``{}`` is already in register!'.format(role.name))
        except:
            await self.bot.say('Something went wrong.')

    @regedit.command(name="removerole", pass_context=True, no_pm=True)
    async def _regedit_removerole(self, ctx, *, role_name: str):
        """Removes a register role."""
        server = ctx.message.server
        if server.id in self.json:
            role = discord.utils.get(server.roles, name=role_name)
            if role:
                # ROLE IS IN SERVER
                if role.id in self.json[server.id]["roles"]:
                    # --- REMOVE ROLE FROM JSON ---
                    del self.json[server.id]["roles"][role.id]
                    dataIO.save_json(self.location, self.json)
                    await self.bot.say('``{}`` role has been removed from register.'.format(role.name))
                else:
                    # ROLE ISN'T IN JSON
                    await self.bot.say('``{}`` role isn\'t in register yet.'.format(role.name))
            else:
                # ROLE ISN'T IN SERVER
                await self.bot.say('That role isn\'t in this server.')
                # TODO : REMOVE NONEXISTENT ROLE FROM JSON
                role_in_json = False
                for r in self.json[server.id]["roles"]:
                    if self.json[server.id]["roles"][r]["role_name"] == role_name:
                        role_in_json = True
                        # REMOVE ROLE FROM JSON
                        del self.json[server.id]["roles"][r]
                        dataIO.save_json(self.location, self.json)
                        await self.bot.say('Role was in register regardless, and has been removed. It must have been renamed or deleted from the server.')
                        break
        else:
            msg = 'There aren\'t any roles you can register for in this server.'.format(server.name)
            await self.bot.say(box(msg))

    @regedit.command(name="delcmds", pass_context=True, no_pm=True)
    async def _regedit_delcmds(self, ctx):
        """Toggles whether or not !register is deleted
        Note: This forces WHISPER to be set to ON."""
        server = ctx.message.server
        self.json_server_check(server)
        self.json[server.id]["delcmds"] = not self.json[server.id]["delcmds"]
        if self.json[server.id]["delcmds"]:
            await self.bot.say("Register commands will now be deleted after sending.")
            if not self.json[server.id]["whisper"]:
                self.json[server.id]["whisper"] = True
                await self.bot.say("I will now respond to register commands via DM.")
        else:
            await self.bot.say("Register commands will no longer be deleted after sending.")
        dataIO.save_json(self.location, self.json)
        
    @regedit.command(name="whisper", pass_context=True, no_pm=True)
    async def _regedit_whisper(self, ctx):
        """Toggles whether or not I respond to register commands via DM.
        NOTE: Is always set to ON whilst DELCMDS is set to ON."""
        server = ctx.message.server
        self.json_server_check(server)
        if self.json[server.id]["delcmds"]:
            await self.bot.say("DELCMDS is ON! Please use !regedit delcmds to toggle off before toggling WHISPER off.")
        else:
            self.json[server.id]["whisper"] = not self.json[server.id]["whisper"]
            if self.json[server.id]["whisper"]:
                await self.bot.say("I will now respond to register commands via DM.")
            else:
                await self.bot.say("I will no longer respond to register commands via DM.")
        
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

    def json_server_check(self, server):
        if server.id not in self.json:
                log.debug('Adding server({}) in Json'.format(server.id))
                self.json[server.id] = default_settings
                dataIO.save_json(self.location, self.json)

    
        
def check_folder():
    if not os.path.exists('data/register'):
        log.debug('Creating folder: data/register')
        os.makedirs('data/register')


def check_file():
    f = 'data/register/settings.json'
    if dataIO.is_valid_json(f) is False:
        log.debug('Creating json: settings.json')
        dataIO.save_json(f, {})


def setup(bot):
    check_folder()
    check_file()
    n = Register(bot)
    bot.add_cog(n)
