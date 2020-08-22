"""Module for the WelcomeCount Cog."""
import datetime
from typing import List, Union

import discord
from redbot.core import Config, checks, commands
from redbot.core.utils.chat_formatting import box

__all__ = ["UNIQUE_ID", "WelcomeCount"]

UNIQUE_ID = 0x6F7951A4
_DEFAULT_WELCOME = (
    "Welcome, {mention}, to {server}!\n\n{count} user{plural} joined today!"
)


class WelcomeCount(commands.Cog):
    """A special welcome cog which keeps a daily count of new users.

    Idea came from Twentysix's version of Red on the official Red-DiscordBot
    server.
    """

    def __init__(self):
        super().__init__()
        self.conf: Config = Config.get_conf(
            self, identifier=UNIQUE_ID, force_registration=True
        )
        self.conf.register_channel(
            enabled=False,
            last_message=None,
            delete_last_message=True,
            welcome_msg=_DEFAULT_WELCOME,
        )
        self.conf.register_channel(
            enabled=False, last_message=None, welcome_msg=_DEFAULT_WELCOME
        )
        self.conf.register_guild(count=0, day=None, join_role=None)

    @checks.admin_or_permissions(manage_guild=True)
    @commands.guild_only()
    @commands.group(invoke_without_command=True, aliases=["wcount"])
    async def welcomecount(self, ctx: commands.Context):
        """Manage settings for WelcomeCount."""
        if not ctx.invoked_subcommand:
            await ctx.send_help()
            channel: discord.TextChannel = ctx.channel
            settings = self.conf.channel(channel)
            if await settings.enabled():
                msg: str = await settings.welcome_msg()
                delete_last: bool = await settings.delete_last_message()
                await ctx.send(
                    box(
                        "Enabled in this channel.\n"
                        "Deletion of previous welcome message enabled: {0}\n"
                        "Welcome message: {1}"
                        "".format(delete_last, msg)
                    )
                )
            else:
                await ctx.send(box("Disabled in this channel."))

    @welcomecount.command(name="toggle")
    async def welcomecount_toggle(self, ctx: commands.Context):
        """Toggle welcome messages in this channel."""
        channel: discord.TextChannel = ctx.channel
        settings = self.conf.channel(channel)
        now_enabled: bool = not await settings.enabled()
        await settings.enabled.set(now_enabled)
        await ctx.send(
            "Welcome messages are now {0} in this channel."
            "".format("enabled" if now_enabled else "disabled")
        )

    @welcomecount.command(name="message")
    async def welcomecount_message(self, ctx: commands.Context, *, message: str):
        """Set the bot's welcome message.

        This message can be formatted using these parameters:
            mention - Mention the user who joined
            username - The user's display name
            server - The name of the server
            count - The number of users who joined today.
            plural - Empty if `count` is 1. 's' otherwise.
            total - The total number of users in the server.
        To format the welcome message with the above parameters, include them
        in your message surrounded by curly braces {}.
        """
        channel: discord.TextChannel = ctx.channel
        settings = self.conf.channel(channel)
        await settings.welcome_msg.set(message)
        member: discord.Member = ctx.author
        count: int = await self.conf.guild(ctx.guild).count()
        params = {
            "mention": member.mention,
            "username": member.display_name,
            "server": ctx.guild.name,
            "count": count,
            "plural": "" if count == 1 else "s",
            "total": ctx.guild.member_count,
        }
        try:
            to_send = message.format(**params)
        except KeyError as exc:
            await ctx.send(
                f"The welcome message cannot be formatted, because it contains an "
                f"invalid placeholder `{{{exc.args[0]}}}`. See `{ctx.clean_prefix}help "
                f"welcomecount message` for a list of valid placeholders."
            )
        else:
            await ctx.send(
                "Welcome message set, here's what it'll look like:\n\n" + to_send
            )

    @welcomecount.command(name="deletelast")
    async def welcomecount_deletelast(self, ctx: commands.Context):
        """Toggle deleting the previous welcome message in this channel.

        When enabled, the last message is deleted *only* if it was sent on
        the same day as the new welcome message.
        """
        channel: discord.TextChannel = ctx.channel
        settings = self.conf.channel(channel)
        now_deleting: bool = not await settings.delete_last_message()
        await settings.delete_last_message.set(now_deleting)
        await ctx.send(
            "Deleting welcome messages are now {0} in this channel."
            "".format("enabled" if now_deleting else "disabled")
        )

    @welcomecount.command(name="joinrole")
    async def welcomecount_joinrole(
        self, ctx: commands.Context, *, role: Union[discord.Role, str]
    ):
        """Set a role which a user must receive before they're welcomed.

        This means that, instead of the welcome message being sent when
        the user joins the server, the welcome message will be sent when
        they receive a particular role.

        Use `[p]welcomecount joinrole disable` to revert to the default
        behaviour.
        """
        if isinstance(role, discord.Role):
            await self.conf.guild(ctx.guild).join_role.set(role.id)
            await ctx.tick()
        elif role.lower() == "disable":
            await self.conf.guild(ctx.guild).join_role.clear()
            await ctx.tick()
        else:
            await ctx.send(f'Role "{role}" not found.')

    async def send_welcome_message(self, member: discord.Member) -> None:
        guild: discord.Guild = member.guild
        server_settings = self.conf.guild(guild)
        today: datetime.date = datetime.date.today()
        new_day: bool = False
        if await server_settings.day() == str(today):
            cur_count: int = await server_settings.count()
            await server_settings.count.set(cur_count + 1)
        else:
            new_day = True
            await server_settings.day.set(str(today))
            await server_settings.count.set(1)

        welcome_channels: List[discord.TextChannel] = []
        # noinspection PyUnusedLocal
        channel: discord.TextChannel
        for channel in guild.channels:
            if await self.conf.channel(channel).enabled():
                welcome_channels.append(channel)

        for channel in welcome_channels:
            channel_settings = self.conf.channel(channel)

            delete_last: bool = await channel_settings.delete_last_message()
            if delete_last and not new_day:
                last_message: int = await channel_settings.last_message()
                try:
                    last_message: discord.Message = await channel.fetch_message(
                        last_message
                    )
                except discord.HTTPException:
                    # Perhaps the message was deleted
                    pass
                else:
                    await last_message.delete()
            count: int = await server_settings.count()
            params = {
                "mention": member.mention,
                "username": member.display_name,
                "server": guild.name,
                "count": count,
                "plural": "" if count == 1 else "s",
                "total": guild.member_count,
            }
            welcome: str = await channel_settings.welcome_msg()
            msg: discord.Message = await channel.send(welcome.format(**params))
            await channel_settings.last_message.set(msg.id)

    # Events

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Send the welcome message and update the last message."""
        if await self.conf.guild(member.guild).join_role() is None:
            await self.send_welcome_message(member)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        join_role_id = await self.conf.guild(before.guild).join_role()
        if join_role_id is None:
            return

        before_roles = frozenset(before.roles)
        after_roles = frozenset(after.roles)
        try:
            added_role = next(iter(after_roles - before_roles))
        except StopIteration:
            # A role wasn't added
            return

        if added_role.id == join_role_id:
            await self.send_welcome_message(after)
