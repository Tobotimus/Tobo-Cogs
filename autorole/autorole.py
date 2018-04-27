"""Module for Autorole cog."""
import discord
from discord.ext import commands
from redbot.core import Config, checks
from redbot.core.utils.chat_formatting import box

__all__ = ["UNIQUE_ID", "Autorole"]

UNIQUE_ID = 0x0bbbbade


class Autorole:
    """Simple cog which can give users a role on join."""

    def __init__(self):
        self.conf = Config.get_conf(
            self, identifier=UNIQUE_ID, force_registration=True)
        self.conf.register_guild(role=None, enabled=True)

    @commands.group()
    @checks.admin_or_permissions(manage_role=True)
    async def autorole(self, ctx: commands.Context):
        """Manage Autorole settings.

        I must have the Manage Roles permission in order for this to work."""
        if not ctx.invoked_subcommand:
            await ctx.send_help()
            settings = self.conf.guild(ctx.guild)
            role = await settings.role()
            if role is not None:
                role = discord.utils.get(ctx.guild.roles, id=role)
            if role is None:
                role = "Not set"
            await ctx.send(
                box("Enabled: {!s}\n"
                    "Role: {!s}"
                    "".format(await settings.enabled(), role)))

    @autorole.command(name="setrole")
    @commands.bot_has_permissions(manage_roles=True)
    async def _autorole_set(self, ctx: commands.Context, *,
                            role: discord.Role):
        """Set the role."""
        if role > ctx.guild.me.top_role:
            await ctx.send("I cannot apply roles which are above me in the"
                           " role hierarchy.")
            return
        await self.conf.guild(ctx.guild).role.set(role.id)
        await ctx.send("Done.")

    @autorole.command(name="toggle")
    @commands.bot_has_permissions(manage_roles=True)
    async def _autorole_toggle(self, ctx: commands.Context):
        """Toggle Autorole on or off."""
        guild = ctx.guild
        role = await self.conf.guild(guild).role()
        role = discord.utils.get(guild.roles, id=role)
        if role is None:
            await ctx.send("The role is not set - see `{}autorole setrole`."
                           "".format(ctx.prefix))
            return
        enabled = not await self.conf.guild(guild).enabled()
        await self.conf.guild(guild).enabled.set(enabled)

        await ctx.send("Done. The `{!s}` role will {} be applied when a"
                       " new member joins."
                       "".format(role, "now" if enabled else "no longer"))

    async def on_member_join(self, member: discord.Member):
        """Fires when a member joins and gives them the role, if enabled."""
        guild = member.guild
        enabled = await self.conf.guild(guild).enabled()
        role_id = await self.conf.guild(guild).role()
        if not enabled or role_id is None:
            return
        role = discord.utils.get(guild.roles, id=role_id)
        if role is None:
            return
        try:
            await member.add_roles(role)
        except discord.HTTPException:
            pass
