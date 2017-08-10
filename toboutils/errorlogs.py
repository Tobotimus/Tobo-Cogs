"""Module for ErrorLogs cog."""
import traceback
import discord
from discord.ext import commands
from core import checks, Config
from core.utils.chat_formatting import pagify, box

UNIQUE_ID = 0x082745e9
_ENABLE = "enable"
_DISABLE = "disable"

class ErrorLogs():
    """Logs traceback of command errors in specified channels."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.conf = Config.get_conf(self, unique_identifier=UNIQUE_ID,
                                    force_registration=True)

        self.conf.register_global(
            logger_channels=[]
        )

    @commands.command()
    @checks.is_owner()
    async def logerrors(self, ctx: commands.Context):
        """Toggle error logging in this channel."""
        channel = ctx.channel
        task = _ENABLE
        if channel.id in self.conf.logger_channels():
            task = _DISABLE
        await ctx.send("This will {} error logging in this channel. Are you sure"
                       " about this? Type `yes` to agree".format(task))
        user_resp = await self.bot.wait_for('message', check=_author_reply_pred(ctx))
        reply = ''
        if user_resp is not None and user_resp.content == 'yes':
            updated_settings = None
            if task == _ENABLE:
                updated_settings = self.conf.logger_channels()
                updated_settings.append(channel.id)
            else:
                updated_settings = self.conf.logger_channels()
                updated_settings.remove(channel.id)
            await self.conf.set('logger_channels', updated_settings)
            reply = "Error logging {}d.".format(task)
        else:
            reply = "The operation was cancelled."
        await ctx.send(reply)

    async def command_error(self, ctx: commands.Context, error: commands.CommandError):
        """Fires when a command error occurs and sends tracebacks to logger channels."""
        if not self.conf.logger_channels() or not isinstance(error, commands.CommandInvokeError):
            return
        error_title = "Exception in command `{}` ¯\\_(ツ)_/¯".format(ctx.command.qualified_name)
        _traceback = "".join(traceback.format_exception(type(error), error,
                                                        error.__traceback__))
        channel = ctx.channel
        embed = discord.Embed(title=error_title, colour=discord.Colour.red(),
                              timestamp=ctx.message.created_at)
        embed.add_field(name="Invoker", value="{}\n({})".format(ctx.message.author.mention,
                                                                str(ctx.message.author)))
        embed.add_field(name="Content", value=ctx.message.content)
        _channel_disp = "Private channel" if isinstance(channel, discord.abc.PrivateChannel) else (
            "{}\n({})".format(channel.mention, channel.name))
        embed.add_field(name="Channel", value=_channel_disp)
        if not isinstance(channel, discord.abc.PrivateChannel):
            embed.add_field(name="Server", value=ctx.guild.name)
        for channel_id in self.conf.logger_channels():
            channel = self.bot.get_channel(channel_id)
            try:
                await channel.send(embed=embed)
            except discord.errors.Forbidden: # If bot can't embed
                msg = ("Invoker: {}\n"
                       "Content: {}\n"
                       "Channel: {}".format(str(ctx.message.author),
                                            ctx.message.content, _channel_disp))
                if not channel.is_private:
                    msg += "\nServer : {}".format(ctx.guild.name)
                await channel.send(box(msg))
            for page in pagify(_traceback):
                await channel.send(box(page, lang="py"))

def _author_reply_pred(ctx: commands.Context):
    def _pred(msg: discord.Message):
        return msg.author == ctx.author and msg.channel == ctx.channel
    return _pred
