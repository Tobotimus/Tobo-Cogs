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
import contextlib
import os
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Iterator, List, Tuple, Union, cast

import discord
from redbot.core import Config, checks, commands, data_manager, modlog
from redbot.core.bot import Red
from redbot.core.i18n import Translator
from redbot.core.utils.chat_formatting import box, pagify

try:
    from tabulate import tabulate
except ImportError:
    raise RuntimeError(
        "tabulate is not installed. Please install it with the `[p]pipinstall "
        "tabulate[widechars]` command in Discord before loading strikes."
    )

UNIQUE_ID = 0x134087DE

_CASETYPE = {
    "name": "strike",
    "default_setting": True,
    "image": "\N{BOWLING}",
    "case_str": "Strike",
}

_ = Translator(":blobducklurk:", __file__)


class Strikes(commands.Cog):
    """Strike users to keep track of misbehaviour."""

    def __init__(self, bot: Red, db: Union[str, bytes, os.PathLike, None] = None):
        self.bot = bot
        self.db = db or data_manager.cog_data_path(self) / "strikes.db"
        super().__init__()

    async def initialize(self):
        # Casetype registration
        with contextlib.suppress(RuntimeError):
            await modlog.register_casetype(**_CASETYPE)

        # Data definition (table creation)
        ddl_path = data_manager.bundled_data_path(self) / "ddl.sql"
        with self._db_connect() as conn, ddl_path.open() as ddl_file:
            cursor = conn.cursor()
            cursor.execute(ddl_file.read())

            # Data migration from Config to SQLite
            json_file = data_manager.cog_data_path(self) / "settings.json"
            if json_file.exists():
                conf = Config.get_conf(self, UNIQUE_ID)
                all_members = await conf.all_members()

                def _gen_rows() -> Iterator[Tuple[int, int, int, int, str]]:
                    for guild_id, guild_data in all_members.items():
                        for member_id, member_data in guild_data.items():
                            for strike in member_data.get("strikes", []):
                                yield (
                                    strike["id"],
                                    member_id,
                                    guild_id,
                                    strike["moderator"],
                                    strike["reason"],
                                )

                cursor.executemany(
                    """
                    INSERT INTO strikes(id, user, guild, moderator, reason)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    _gen_rows(),
                )
                json_file.replace(json_file.parent / "settings.old.json")

    def _db_connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(cast(os.PathLike, self.db))
        conn.row_factory = sqlite3.Row
        conn.create_function("is_member", 2, self._is_member)
        return conn

    def _is_member(self, user_id: int, guild_id: int) -> bool:
        # Function exported to SQLite as is_member
        guild = self.bot.get_guild(guild_id)
        if guild is None:
            return False
        return guild.get_member(user_id) is not None

    async def strike_user(
        self, member: discord.Member, reason: str, moderator: discord.Member
    ) -> List[int]:
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
        List[int]
            A list of IDs for all strikes this user has received.

        """
        now = datetime.now()
        strike_id = discord.utils.time_snowflake(now)
        with self._db_connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO strikes(id, user, guild, moderator, reason)
                VALUES (?, ?, ?, ?, ?)
                """,
                (strike_id, member.id, member.guild.id, moderator.id, reason),
            )
            cursor.execute(
                "SELECT id FROM strikes WHERE user == ? AND guild == ?",
                (member.id, member.guild.id),
            )
            result = cursor.fetchall()
        await self.create_case(member, now, reason, moderator)
        return [row["id"] for row in result]

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
        month_ago = discord.utils.time_snowflake((datetime.now() - timedelta(days=30)))
        last_month = [id_ for id_ in strikes if id_ > month_ago]
        await ctx.send(
            _(
                "Done. {user.display_name} now has {num} strikes ({recent_num} in the"
                " past 30 days)."
            ).format(user=member, num=len(strikes), recent_num=len(last_month))
        )

    @checks.mod_or_permissions(kick_members=True)
    @commands.guild_only()
    @commands.command()
    async def delstrike(self, ctx: commands.Context, strike_id: int):
        """Remove a single strike by its ID."""
        with self._db_connect() as conn:
            conn.execute("DELETE FROM strikes WHERE id == ?", (strike_id,))
        await ctx.tick()

    @checks.mod_or_permissions(kick_members=True)
    @commands.guild_only()
    @commands.command()
    async def delstrikes(self, ctx: commands.Context, *, member: discord.Member):
        """Remove all strikes from a member."""
        with self._db_connect() as conn:
            conn.execute(
                "DELETE FROM strikes WHERE user == ? AND guild == ?",
                (member.id, member.guild.id),
            )
        await ctx.tick()

    @checks.mod_or_permissions(kick_members=True)
    @commands.guild_only()
    @commands.command()
    async def strikes(self, ctx: commands.Context, *, member: discord.Member):
        """Show all previous strikes for a user."""
        with self._db_connect() as conn:
            cursor = conn.execute(
                """
                SELECT id, moderator, reason FROM strikes
                WHERE user == ? AND guild == ?
                ORDER BY id DESC
                """,
                (member.id, member.guild.id),
            )
            table = self._create_table(cursor, member.guild)
        if table:
            pages = pagify(table, shorten_by=25)
            await ctx.send(
                _("Strikes for {user.display_name}:\n").format(user=member)
                + box(next(pages))
            )
            for page in pages:
                await ctx.send(box(page))
        else:
            await ctx.send(
                _("{user.display_name} has never received any strikes.").format(
                    user=member
                )
            )

    @commands.command()
    async def allstrikes(self, ctx: commands.Context, num_days: int = 30):
        """Show all recent individual strikes.

        `[num_days]` is the number of past days of strikes to display.
        Defaults to 30. When 0, all strikes from the beginning of time
        will be counted shown.

        """
        if num_days < 0:
            await ctx.send(
                _(
                    "You must specify a number of days of at least 0 to retreive "
                    "strikes from."
                )
            )
            return
        start_id = (
            discord.utils.time_snowflake(datetime.now() - timedelta(days=num_days))
            if num_days
            else 0
        )
        with self._db_connect() as conn:
            cursor = conn.execute(
                """
                SELECT id, user, moderator, reason FROM strikes
                WHERE
                  guild == ?
                  AND id > ?
                  AND is_member(user, guild)
                ORDER BY id DESC
                """,
                (ctx.guild.id, start_id),
            )
            table = self._create_table(cursor, ctx.guild)

        if table:
            pages = pagify(table, shorten_by=25)
            if num_days:
                await ctx.send(
                    _("All strikes received by users in the past {num} days:\n").format(
                        num=num_days
                    )
                    + box(next(pages))
                )
            else:
                await ctx.send(
                    _("All strikes received by users in this server:\n")
                    + box(next(pages))
                )
            for page in pages:
                await ctx.send(box(page))
        else:
            if num_days:
                await ctx.send(
                    _(
                        "No users in this server have received strikes in the past "
                        "{num} days!"
                    ).format(num=num_days)
                )
            else:
                await ctx.send(_("No users in this server have ever received strikes!"))

    @commands.command()
    async def strikecounts(
        self,
        ctx: commands.Context,
        num_days: int = 0,
        limit: int = 100,
        sort_by: str = "count",
        sort_order: str = "desc",
    ):
        """Show the strike count for multiple users.

        `[num_days]` is the number of past days of strikes to count.
        Defaults to 0, which means all strikes from the beginning of
        time will be counted.

        `[limit]` is the maximum amount of members to show the
        strike count for. Defaults to 100.

        `[sort_by]` is the column to sort the table by. May be one of
        either *count* or *date*. Defaults to *count*.

        `[sort_order]` is the order to sort in. It may be one of either
        *desc* for descending or *asc* for ascending. Defaults to
        *desc*.
        """
        if num_days < 0:
            await ctx.send(
                _(
                    "You must specify a number of days of at least 0 to retreive "
                    "strikes from."
                )
            )
            return
        if limit < 1:
            await ctx.send(
                _(
                    "You must specify a number of members of at least 1 to retreive "
                    "strikes for."
                )
            )
        sort_by = sort_by.lower()
        if sort_by not in ("count", "date"):
            await ctx.send(
                _("Sorry, I don't know how to sort by {column}").format(column=sort_by)
            )
            return
        elif sort_by == "date":
            sort_by = "most_recent_id"
        sort_order = sort_order.upper()
        if sort_order not in ("ASC", "DESC"):
            await ctx.send(
                _("Sorry, {word} is not a valid sort order.").format(word=sort_order)
            )
            return
        start_id = (
            discord.utils.time_snowflake(datetime.now() - timedelta(days=num_days))
            if num_days
            else 0
        )
        with self._db_connect() as conn:
            cursor = conn.execute(
                f"""
                SELECT max(id) as most_recent_id, user, count(user) as count FROM strikes
                WHERE
                  guild = ?
                  AND id > ?
                  AND is_member(user, guild)
                GROUP BY guild, user
                ORDER BY {sort_by} {sort_order}
                LIMIT ?
                """,
                (ctx.guild.id, start_id, limit),
            )
            table = self._create_table(cursor, ctx.guild)

        if table:
            pages = pagify(table, shorten_by=25)
            if num_days:
                await ctx.send(
                    _(
                        "Number of strikes received by users in the past {num} days:\n"
                    ).format(num=num_days)
                    + box(next(pages))
                )
            else:
                await ctx.send(
                    _("Number of strikes received by users in this server:\n")
                    + box(next(pages))
                )
            for page in pages:
                await ctx.send(box(page))
        else:
            if num_days:
                await ctx.send(
                    _(
                        "No users in this server have received strikes in the past "
                        "{num} days!"
                    ).format(num=num_days)
                )
            else:
                await ctx.send(_("No users in this server have ever received strikes!"))

    @staticmethod
    def _create_table(cursor: sqlite3.Cursor, guild: discord.Guild) -> str:
        tabular_data = defaultdict(list)
        for strike in cursor:
            with contextlib.suppress(IndexError):
                user = guild.get_member(strike["user"])
                tabular_data[_("User")].append(user)
            with contextlib.suppress(IndexError):
                mod_id = strike["moderator"]
                tabular_data[_("Moderator")].append(guild.get_member(mod_id) or mod_id)
            with contextlib.suppress(IndexError):
                strike_id = strike["id"]
                tabular_data[_("Time & Date (UTC)")].append(
                    discord.utils.snowflake_time(strike_id).strftime("%Y-%m-%d %H:%M")
                )
                tabular_data[_("Strike ID")].append(strike_id)
            with contextlib.suppress(IndexError):
                strike_count = strike["count"]
                tabular_data[_("Strike Count")].append(strike_count)
            with contextlib.suppress(IndexError):
                recent_id = strike["most_recent_id"]
                tabular_data[_("Latest Strike Given (UTC)")].append(
                    discord.utils.snowflake_time(recent_id).strftime("%Y-%m-%d %H:%M")
                )
            with contextlib.suppress(IndexError):
                reason = strike["reason"]
                if reason:
                    reason = "\n".join(
                        pagify(reason, delims=[" "], page_length=25, shorten_by=0)
                    )
                tabular_data[_("Reason")].append(reason)

        if tabular_data:
            return tabulate(
                tabular_data, headers="keys", tablefmt="fancy_grid", numalign="left"
            )
        else:
            return ""
