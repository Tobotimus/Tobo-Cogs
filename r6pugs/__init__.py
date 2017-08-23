"""Package for R6Pugs."""
from core.bot import Red
from .r6pugs import R6Pugs

def setup(bot: Red):
    """Load R6Pugs"""
    cog = R6Pugs()
    bot.add_listener(cog.pug_ended, "on_pug_end")
    bot.add_listener(cog.pug_started, "on_pug_start")
    bot.add_listener(cog.pug_match_ended, "on_pug_match_end")
    bot.add_listener(cog.pug_match_started, "on_pug_match_start")
    bot.add_listener(cog.ten_players_waiting, "on_tenth_player")
    bot.add_cog(R6Pugs())
