from .strikes import Strikes

def setup(bot):
    """Load Strikes."""
    bot.add_cog(Strikes(bot))
