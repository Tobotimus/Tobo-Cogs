"""Errors used throughout this package."""

class R6Error(Exception):
    """Base exception for r6cogs."""
    pass

class NoStatsFound(R6Error):
    """No stats found for the specified player."""
    pass

class ResourceNotFound(R6Error):
    """Search had no results."""
    pass

class InvalidUsername(R6Error):
    """Invalid platform username specified."""
    pass

class InvalidPlatform(R6Error):
    """Invalid platform specified. Must be `uplay`, `xbox` or `ps4`."""
    pass

class InvalidRegion(R6Error):
    """Invalid region specified. Must be `NA`, `EU` or `Asia`."""
    pass

class Forbidden(R6Error):
    """User doesn't have permission to join the PuG."""
    pass

class HttpError(R6Error):
    """HTTP data was invalid or unexpected."""
    def __init__(self, resp, content):
        super().__init__()
        self.resp = resp
        if not isinstance(content, dict):
            raise TypeError("HTTP content should be dict")
        self.content = content

    def get_reason(self):
        """Calculate the reason for the error from the response content."""
        reason = self.resp.reason
        try:
            reason = self.content['error']['message']
        except (ValueError, KeyError, TypeError):
            pass
        return reason

    def __repr__(self):
        return '<HttpError %s "%s">' % (self.resp.status, self.get_reason())

    __str__ = __repr__
