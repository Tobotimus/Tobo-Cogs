from .streamroles import StreamRoles

def setup(bot):
    """Load StreamRoles."""
    bot.add_cog(StreamRoles.start(bot))
