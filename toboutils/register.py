"""Module for Register cog."""
import asyncio
import discord
from discord.ext import commands
from core import checks, Config
from core.bot import Red
from core.utils.chat_formatting import box

UNIQUE_ID = 0x9c9519a1
_REMOVE = "removed from"
_ADD = "assigned to"


class Register:
    """Allows users to register for certain roles."""

    def __init__(self, bot: Red):
        self.bot = bot
        self.conf = Config.get_conf(self, unique_identifier=UNIQUE_ID,
                                    force_registration=True)

        self.conf.register_guild(
            roles=[],
            delete_after=None
        )

    @commands.command(no_pm=True)
    async def register(self, ctx: commands.Context, *,
                       role_name: str = ''):
        """Gives the user a role

        Valid roles can be added using !regedit
        Example usage: !register PC"""
        guild = ctx.guild
        member = ctx.author
        delete_after = None # is set if the 'quiet' option is on
        reply = ''
        if not self.conf.guild(guild).roles():
            reply = "Register is not enabled on this server."
        elif role_name:
            role = next((r for r in guild.roles if r.name == role_name and
                         r.id in self.conf.guild(guild).roles()), None)
            if role is None:
                reply = "You can't register for that role."
            else:
                reply = await self._set_role(role, member)
        else:
            # --- SEND VALID ROLES ---
            valid_roles = [r.name for r in guild.roles
                           if r.id in self.conf.guild(guild).roles()]
            reply = box("Valid register roles in {}:\n"
                        "{}"
                        "".format(guild.name, ", ".join(sorted(valid_roles))))
        delete_after = self.conf.guild(guild).delete_after()
        await ctx.send(reply, delete_after=delete_after)
        if delete_after is not None:
            await self._cleanup(delete_after, ctx.message)

    @commands.group(no_pm=True)
    @checks.admin_or_permissions(administrator=True)
    async def regedit(self, ctx: commands.Context):
        """Manages valid register roles."""
        if ctx.invoked_subcommand is None:
            # Send server's current settings
            guild = ctx.guild
            await self.bot.send_cmd_help(ctx)
            if not self.conf.guild(guild).roles():
                reply = box("Register is not enabled in this server."
                            " Use [p]regedit addrole to add the first role"
                            " and enable it.")
            else:
                valid_roles = [r.name for r in guild.roles
                               if r.id in self.conf.guild(guild).roles()]
                delete_after = self.conf.guild(guild).delete_after()
                quiet_status = None
                if delete_after is None:
                    quiet_status = "Quiet mode is disabled."
                else:
                    quiet_status = ("Register commands are cleaned up after {} seconds"
                                    "".format(delete_after))
                reply = box("{}\n"
                            "Valid register roles:\n"
                            "{}"
                            "".format(quiet_status, (", ".join(sorted(valid_roles))
                                                     if valid_roles else None)))
            await ctx.send(reply)

    @regedit.command(name="addrole", no_pm=True)
    async def _regedit_addrole(self, ctx: commands.Context, *,
                               role_name: str):
        """Adds a register role."""
        guild = ctx.guild
        role_id = next((r.id for r in guild.roles if r.name == role_name and
                        r.id not in self.conf.guild(guild).roles()), None)
        if role_id is None:
            await ctx.send("Couldn't add that role to register. "
                           "Make sure the role exists and isn't already added to register.")
            return
        else:
            _roles = self.conf.guild(guild).roles()
            _roles.append(role_id)
            await self.conf.guild(guild).set('roles', _roles)
            await ctx.send("Role was successfully added to register.")

    @regedit.command(name="removerole", no_pm=True)
    async def _regedit_removerole(self, ctx: commands.Context, *,
                                  role_name: str):
        """Removes a register role."""
        guild = ctx.guild
        if not self.conf.guild(guild).roles():
            await ctx.send("Register is not enabled in this server.")
            return
        role_id = next((r.id for r in guild.roles if r.name == role_name and
                        r.id in self.conf.guild(guild).roles()), None)
        if role_id is None:
            await ctx.send("Couldn't remove that role from register. "
                           "Make sure the role exists and is in register.")
        else:
            _roles = self.conf.guild(guild).roles()
            _roles.remove(role_id)
            await self.conf.guild(guild).set('roles', _roles)
            await ctx.send("Role was successfully removed from register.")

    @regedit.command(name="quiet", no_pm=True)
    async def _regedit_quiet(self, ctx: commands.Context,
                             delete_after: float):
        """Make the bot clean up after a user registers.

        <delete_after> is how many seconds the bot will wait before cleaning up.
        Set to zero to disable quiet mode."""
        guild = ctx.message.guild
        if delete_after == 0:
            delete_after = None
        await self.conf.guild(guild).set('delete_after', delete_after)
        reply = "Register commands are now cleaned up after {} seconds.".format(delete_after)
        if delete_after is None:
            reply = "Cleaning up register commands is disabled."
        await ctx.send(reply)

    @commands.command()
    @commands.guild_only()
    @checks.guildowner_or_permissions(manage_roles=True)
    async def giverole(self, ctx: commands.Context,
                       role_name: str, member: discord.Member=None):
        """Gives a role to a user.

        If <user> is not specified, it gives the role to whoever invoked the command."""
        if member is None:
            member = ctx.author
        role_name = role_name.strip('\"\'')
        role = discord.utils.get(ctx.guild.roles, name=role_name)
        reply = ''
        if role is not None:
            if (role not in member.roles and
                    (ctx.author.top_role > role or ctx.author == ctx.guild.owner)):
                try:
                    await member.add_roles(role)
                    reply = ("The `{role_name}` role has been assigned to {member}."
                             "".format(role_name=role.name, member=member.display_name))
                except discord.errors.Forbidden:
                    reply = ("I do not have permission to add the `{role_name}` role."
                             "".format(role_name=role.name))
            elif ctx.author.top_role <= role and ctx.author != ctx.guild.owner:
                reply = ("You do not have permission to give the `{role_name}` role."
                         "".format(role_name=role.name))
            else:
                reply = ("{member} already has the `{role_name}` role."
                         "".format(member=member.display_name, role_name=role.name))
        else:
            reply = ("The `{role_name}` role does not exist. Remember role names are"
                     " case-sensitive.\nIf the role name is more than one word surround"
                     " it with `\'` or `\"`.".format(role_name=role.name))
        await ctx.send(reply)

    @commands.command(no_pm=True)
    @checks.guildowner_or_permissions(manage_roles=True)
    async def removerole(self, ctx: commands.Context,
                         role_name: str, member: discord.Member=None):
        """Removes a role  from a user.

        If <user> is not specified, it removes the role from whoever invoked the command."""
        if member is None:
            member = ctx.author
        role_name = role_name.strip('\"\'')
        role = discord.utils.get(ctx.guild.roles, name=role_name)
        reply = ''
        if role is not None:
            if (role in member.roles and
                    (ctx.author.top_role > role or ctx.author == ctx.guild.owner)):
                try:
                    await member.remove_roles(role)
                    reply = ("The `{role_name}` role has been removed from {member}."
                             "".format(role_name=role.name, member=member.display_name))
                except discord.errors.Forbidden:
                    reply = ("I do not have permission to remove the"
                             " `{role_name}` role.".format(role_name=role.name))
            elif ctx.author.top_role <= role and ctx.author != ctx.guild.owner:
                reply = ("You do not have permission to remove the"
                         " `{role_name}` role.".format(role_name=role.name))
            else:
                reply = ("{member} does not have the `{role_name}` role."
                         "".format(member=member.display_name, role_name=role.name))
        else:
            reply = ("The `{role_name}` role does not exist. Remember role names are"
                     " case-sensitive.\nIf the role name is more than one word surround"
                     " it with `\'` or `\"`.".format(role_name=role_name))
        await ctx.send(reply)

    async def _set_role(self, role: discord.Role,
                        member: discord.Member) -> str:
        task = None # Whether we are removing or adding a role
        try:
            if role not in member.roles:
                task = _ADD
                await member.add_roles(role)
            else:
                task = _REMOVE
                await member.remove_roles(role)
            reply = ("The {role_name} role has been {action} {member}."
                     "".format(role_name=role.name, action=task, member=member.display_name))
        except discord.errors.Forbidden:
            reply = "I don't have permission to do that."
        return reply

    async def _cleanup(self, delete_after, msg):
        await asyncio.sleep(delete_after)
        try:
            await self.bot.delete_message(msg)
        except discord.errors.NotFound:
            # Just in case some fool deletes their message before the bot does
            pass
        except discord.errors.Forbidden:
            # Bot doesn't have permission to delete messages
            pass # We don't want to make even more of a mess
