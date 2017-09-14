"""Package for R6Pugs."""
from core.bot import Red
from .r6pugs import *
from .errors import *
from .pug import *
from .match import *
from .reactionmenus import *
from .log import LOG

def setup(bot: Red):
    """Load R6Pugs"""
    bot.add_cog(R6Pugs(bot))
