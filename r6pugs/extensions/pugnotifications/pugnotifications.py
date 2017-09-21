"""Module for PugNotifications cog."""
import re
from datetime import datetime, timedelta
import discord
from discord.ext import commands
from redbot.core import Config
from r6pugs import LOG, UNIQUE_ID, Pug

__all__ = ["BadTimeExpr", "PugNotifications"]


class BadTimeExpr(Exception):
    """Bad time expression passed."""
    pass


_UNIT_TABLE = {'s': 1, 'm': 60, 'h': 60 * 60}


# _parse_time and _timespec_sec functions are taken from
#  the 'punish' cog, written by calebj:
#  https://github.com/calebj/calebj-cogs
def _parse_time(time: str):
    if any(u in time for u in _UNIT_TABLE):
        delim = '([0-9.]*[{}])'.format(''.join(_UNIT_TABLE))
        time = re.split(delim, time)
        time = sum([_timespec_sec(t) for t in time if t != ''])
    elif not time.isdigit():
        raise BadTimeExpr("invalid expression '%s'" % time)
    return int(time)


def _timespec_sec(time: str):
    timespec = time[-1]
    if timespec.lower() not in _UNIT_TABLE:
        raise BadTimeExpr("unknown unit '%c'" % timespec)
    timeint = float(time[:-1])
    return timeint * _UNIT_TABLE[timespec]


class PugNotifications:
    """Stay notified about PUGs."""

    def __init__(self):
        self.conf = Config.get_conf(
            self, identifier=UNIQUE_ID, force_registration=True)
        self.conf.register_guild(
            role=None, mention_cooldown=1800, last_mention=None)
        self.conf.register_member(online_sub=False)

    @commands.group()
    async def subpugs(self, ctx: commands.Context):
        """Manage PUG notifications."""
        if not ctx.invoked_subcommand:
            await ctx.bot.send_cmd_help(ctx)

    @subpugs.command(name="always")
    async def sub_always(self, ctx: commands.Context):
        """Get notified about PUGs always."""
        role = await self.get_role(ctx.guild)
        if role is None:
            await ctx.send("The PUG role for this server has not been set.")
            return
        author = ctx.author
        if role not in author.roles:
            await author.add_roles(role)
            await ctx.send("Done.")

    @subpugs.command(name="online")
    async def sub_online(self, ctx: commands.Context):
        """Get notified when you're online."""
        role = await self.get_role(ctx.guild)
        if role is None:
            await ctx.send("The PUG role for this server has not been set.")
            return
        author = ctx.author
        if role in author.roles:
            await author.remove_roles(role)
        await self.conf.member(author).online_sub.set(True)
        await ctx.send("Done.")

    @subpugs.command(name="next")
    async def sub_next(self, ctx: commands.Context, duration: str):
        """Get notified for a period of time.

        Time specification is any combination of numbers with the units s, m, h."""
        role = await self.get_role(ctx.guild)
        if role is None:
            await ctx.send("The PUG role for this server has not been set.")
            return
        try:
            duration = _parse_time(duration)
        except BadTimeExpr:
            await ctx.send(
                "Invalid time specification. Must be any combination"
                " of numbers with the units s, m, h.")
            return
        if duration > 24 * 60 * 60:
            await ctx.send("Duration must not exceed 24 hours.")
            return
        author = ctx.author
        if role not in author.roles:
            await author.add_roles(role)
        ctx.bot.loop.call_later(duration, author.remove_roles, role)
        await ctx.send("Done.")

    @commands.command()
    async def unsubpugs(self, ctx: commands.Context):
        """Unsubscribe from all PUG notifcations."""
        role = await self.get_role(ctx.guild)
        if role is None:
            await ctx.send("The PUG role for this server has not been set.")
            return
        author = ctx.message.author
        if role in author.roles:
            await author.remove_roles(role)
        settings = self.conf.member(author)
        await settings.online_sub.set(False)
        await ctx.send("Done")

    @commands.group()
    async def pugsubset(self, ctx: commands.Context):
        """Manage settings for the PugNotifications cog."""
        if not ctx.invoked_subcommand:
            await ctx.bot.send_cmd_help(ctx)

    @pugsubset.command(name="role")
    async def _set_role(self, ctx: commands.Context, *, role: discord.Role):
        """Set the PUG role for this server."""
        if not role.mentionable:
            await role.edit(
                mentionable=True, reason="Making PUG role mentionable")
            return
        settings = self.conf.guild(ctx.guild)
        await settings.role.set(role.id)
        await ctx.send("Done.")

    @pugsubset.command(name="mentioncd")
    async def _set_mentioncd(self, ctx: commands.Context, duration: str):
        """Set the mention cooldown for notifications."""
        try:
            duration = _parse_time(duration)
        except BadTimeExpr:
            await ctx.send(
                "Invalid time specification. Must be any combination"
                " of numbers with the units s, m, h.")
            return
        await self.conf.guild(ctx.guild).mention_cooldown.set(duration)
        await ctx.send("Done.")

    async def on_pug_start(self, pug: Pug):
        """Fires when a PUG starts and assigns the PUG role
         to any members who requested to be notified whilst
         online. Then it mentions.
        """
        guild = pug.ctx.guild
        role = await self.get_role(guild)
        if role is None:
            return
        last = await self.conf.guild(guild).last_mention()
        if last is not None:
            last = datetime.fromtimestamp(last)
            cooldown = await self.conf.guild(guild).mention_cooldown()
            cooldown = timedelta(seconds=cooldown)
            if datetime.now() < last + cooldown:
                return
        LOG.debug("Members are being notified of PUG")
        now = datetime.now().timestamp()
        await self.conf.guild(guild).last_mention.set(now)
        member = next(iter(guild.members))
        all_dict = await self.conf.member(member).all_from_kind()
        later = 5 * 60
        loop = pug.ctx.bot.loop
        for member_id, settings in all_dict.items():
            if not isinstance(settings, dict):
                continue  # Some weird bug with config
            if settings["online_sub"]:
                member = guild.get_member(int(member_id))
                if member is not None and _is_online(member):
                    await member.add_roles(role)
                    loop.call_later(later, loop.create_task,
                                    member.remove_roles(role))
                    later += 2
        await pug.ctx.send(
            "Paging {0.mention} - a PUG has started here!".format(role))

    async def get_role(self, guild: discord.Guild):
        """Get the role for PUG notifications in a guild."""
        role_id = await self.conf.guild(guild).role()
        if role_id is None:
            return
        return next((r for r in guild.roles if r.id == role_id), None)


def _is_online(member: discord.Member):
    statuses = (discord.Status.online, discord.Status.idle)
    return member.status in statuses
