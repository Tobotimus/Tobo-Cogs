"""Module for Autorole cog."""
import discord
from discord.ext import commands
from core import Config, checks

UNIQUE_ID = 0x0bbbbade

class Autorole:
    """Simple cog which can give users a role on join."""

    def __init__(self):
        self.conf = Config.get_conf(self, identifier=UNIQUE_ID,
                                    force_registration=True)
        self.conf.register_guild(role=None, enabled=True)

    @commands.group()
    @checks.admin_or_permissions(manage_role=True)
    async def autorole(self, ctx: commands.Context):
        """Manage Autorole settings"""
        if not ctx.invoked_subcommand:
            await ctx.bot.send_cmd_help(ctx)

    @autorole.command(name="setrole")
    async def _autorole_set(self, ctx: commands.Context, *, role: discord.Role):
        """Set the role."""
        await self.conf.guild(ctx.guild).role.set(role.id)
        await ctx.send("Done.")

    @autorole.command(name="toggle")
    async def _autorole_toggle(self, ctx: commands.Context):
        """Toggle Autorole on or off."""
        enabled = await self.conf.guild(ctx.guild).enabled()
        await self.conf.guild(ctx.guild).enabled.set(not enabled)
        await ctx.send("Done.")

    async def on_member_join(self, member: discord.Member):
        """Fires when a member joins and gives them the role, if enabled."""
        guild = member.guild
        settings = await self.conf.guild(guild).all()
        if not settings["enabled"] or settings["role"] is None:
            return
        role = next((r for r in guild.roles if r.id == settings["role"]), None)
        if role is None:
            return
        await member.add_roles(role)
