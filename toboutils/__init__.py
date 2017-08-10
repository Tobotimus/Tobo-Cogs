"""Various utils made by Tobotimus, both for server management
and debugging."""
import logging
from core.bot import Red
from .errorlogs import ErrorLogs
from .register import Register
from .welcomecount import WelcomeCount

LOGGER = logging.getLogger('red.toboutils')

def setup(bot: Red):
    """Load toboutils."""
    error_logs = ErrorLogs(bot)
    bot.add_listener(error_logs.command_error, 'on_command_error')
    bot.add_cog(error_logs)
    bot.add_cog(Register(bot))
    bot.add_cog(WelcomeCount(bot))
