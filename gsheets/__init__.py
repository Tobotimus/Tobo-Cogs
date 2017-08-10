"""GSheets package for various integrations of Google Sheets into Discord."""
import logging
from core.bot import Red
from .gsheets import GSheets

LOGGER = logging.getLogger('red.gsheets')

def setup(bot: Red):
    """Load GSheets."""
    bot.add_cog(GSheets(bot))
