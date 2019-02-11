"""Module for the Strikes cog."""

# Copyright (c) 2017-2018 Tobotimus
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from datetime import datetime, timedelta

import discord
from redbot.core import Config, checks, commands, modlog
from redbot.core.utils.chat_formatting import box

UNIQUE_ID = 0x134087DE


class Strikes(getattr(commands, "Cog", object)):
    """Strike users to keep track of misbehaviour."""

    def __init__(self, bot):
        self.bot = bot
        self.conf = Config.get_conf(self, identifier=UNIQUE_ID, force_registration=True)
        self.conf.register_member(strikes=[])
        bot.loop.create_task(self._register_casetype())

    @staticmethod
    async def _register_casetype():
        casetype = {
            "name": "strike",
            "default_setting": True,
            "image": "\N{BOWLING}",
            "case_str": "Strike",
        }
        try:
            await modlog.register_casetype(**casetype)
        except RuntimeError:
            pass

    async def strike_user(
        self, member: discord.Member, reason: str, moderator: discord.Member
    ):
        """Give a user a strike.

        Parameters
        ----------
        member : discord.Member
            The member to strike.
        reason : str
            The reason for the strike.
        moderator : discord.Member
            The moderator who gave the strike.

        Returns
        -------
        `list` of `dict`
            The new list of strikes for the member.

        """
        date = datetime.now()
        new_strike = {
            "timestamp": date.timestamp(),
            "reason": reason,
            "moderator": moderator.id,
            "id": discord.utils.time_snowflake(date),
        }
        settings = self.conf.member(member)
        strikes = await settings.strikes()
        strikes.append(new_strike)
        await settings.strikes.set(strikes)
        await self.create_case(member, date, reason, moderator)
        return strikes

    async def create_case(
        self,
        member: discord.Member,
        timestamp: datetime,
        reason: str,
        moderator: discord.Member,
    ):
        """Create a new strike case.

        Parameters
        ----------
        member : discord.Member
            The member who was striked.
        timestamp : datetime.datetime
            The timestamp for the strike.
        reason : str
            The reason for the strike.
        moderator : discord.Member
            The moderator's ID.

        Returns
        -------
        redbot.core.modlog.Case
            New case object.

        """
        try:
            await modlog.create_case(
                bot=self.bot,
                guild=member.guild,
                created_at=timestamp,
                action_type="strike",
                user=member,
                moderator=moderator,
                reason=reason,
            )
        except RuntimeError:
            pass

    @checks.mod_or_permissions(kick_members=True)
    @commands.guild_only()
    @commands.command()
    async def strike(
        self, ctx: commands.Context, member: discord.Member, *, reason: str
    ):
        """Strike a user."""
        strikes = await self.strike_user(member, reason, ctx.author)
        month_ago = (datetime.now() - timedelta(days=30)).timestamp()
        last_month = [s for s in strikes if s["timestamp"] > month_ago]
        await ctx.send(
            "Done. {0.display_name} now has {1} strikes ({2} in the"
            " past 30 days).".format(member, len(strikes), len(last_month))
        )

    @checks.mod_or_permissions(kick_members=True)
    @commands.guild_only()
    @commands.command()
    async def delstrike(self, ctx: commands.Context, strike_id: int):
        """Remove a single strike by its ID."""
        all_data = await self.conf.all_members(ctx.guild)
        found = False
        for mem_id, mem_data in all_data.items():
            to_remove = None
            for strike in mem_data["strikes"]:
                if strike["id"] == strike_id:
                    to_remove = strike
                    break
            if to_remove is not None:
                found = True
                mem_data["strikes"].remove(to_remove)
                member = ctx.guild.get_member(mem_id)
                if member is None:
                    await ctx.send(
                        "The user who received that strike has since left the server."
                    )
                    return
                await self.conf.member(member).set(mem_data)
                break
        if found:
            await ctx.send("Strike removed successfully.")
        else:
            await ctx.send("I could not find a strike with that ID.")

    @checks.mod_or_permissions(kick_members=True)
    @commands.guild_only()
    @commands.command()
    async def delstrikes(self, ctx: commands.Context, *, member: discord.Member):
        """Remove all strikes from a member."""
        await self.conf.member(member).clear()
        await ctx.send("Done.")

    @checks.mod_or_permissions(kick_members=True)
    @commands.guild_only()
    @commands.command()
    async def strikes(self, ctx: commands.Context, *, member: discord.Member):
        """Show all previous strikes for a user."""
        strikes = await self.conf.member(member).strikes()
        if not strikes:
            await ctx.send(
                "{0.display_name} has never received any strikes." "".format(member)
            )
            return
        new_strikes = []
        for strike in strikes:
            new_strike = strike.copy()
            mod_id = strike["moderator"]
            new_strike["timestamp"] = datetime.utcfromtimestamp(new_strike["timestamp"])
            new_strike["moderator"] = ctx.guild.get_member(mod_id) or mod_id
            new_strikes.append(new_strike)
        strikes = new_strikes

        max_name_len = max(map(lambda s: len(str(s["moderator"])), strikes))
        max_rsn_len = max(map(lambda s: len(str(s["reason"])), strikes))
        # Headers
        headers = (
            "Time + Date (UTC)",
            "Moderator" + " " * (max_name_len - 9),
            "Strike ID" + " " * (len(str(strikes[0]["id"])) - 9),
            "Reason" + " " * (max_rsn_len - 6),
        )
        lines = [" | ".join(headers)]
        # Header underlines
        lines.append(" | ".join(("-" * len(h) for h in headers)))
        for strike in strikes:
            # Align fields to header width
            fields = (
                strike["timestamp"].strftime("%I:%M %p %d-%m-%y"),
                str(strike["moderator"]),
                str(strike["id"]),
                strike["reason"],
            )
            padding = [" " * (len(h) - len(f)) for h, f in zip(headers, fields)]
            fields = tuple(f + padding[i] for i, f in enumerate(fields))
            lines.append(" | ".join(fields))
        await ctx.send(
            "Strikes for {0.display_name}:\n".format(member) + box("\n".join(lines))
        )
