"""StreamRoles - Give roles to streaming users."""
import logging

from .streamroles import StreamRoles

log = logging.getLogger("red.streamroles")


async def setup(bot):
    try:
        cog = StreamRoles(bot)
        await cog.initialize()
        bot.add_cog(cog)
    except Exception as exc:
        log.exception("Error whilst loading streamroles:", exc_info=exc)
        raise
