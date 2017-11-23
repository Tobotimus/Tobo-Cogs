from .sticky import Sticky

def setup(bot):
    """Load Sticky."""
    bot.add_cog(Sticky(bot))
