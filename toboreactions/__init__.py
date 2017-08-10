"""ToboReactions - Fun with reactions!"""
from core.bot import Red
from .reactkarma import ReactKarma
from .triggerreact import TriggerReact

def setup(bot: Red):
    """Load toboreactions."""
    karma = ReactKarma(bot)
    bot.add_listener(karma.reaction_added, "on_reaction_add")
    bot.add_listener(karma.reaction_removed, "on_reaction_remove")
    bot.add_cog(karma)
    trigger = TriggerReact(bot)
    bot.add_listener(trigger.trigger_reactions, "on_message")
