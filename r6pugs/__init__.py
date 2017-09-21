"""Package for R6Pugs."""
from .r6pugs import *
from .errors import *
from .pug import *
from .match import *
from .reactionmenus import *
from .log import *

def setup(bot):
    """Load R6Pugs"""
    bot.add_cog(R6Pugs(bot))
