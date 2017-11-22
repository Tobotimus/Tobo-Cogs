__all__ = ["StreamRolesError", "InvalidToken", "StreamNotFound", "APIError"]

class StreamRolesError(Exception):
    """Base error for StreamRoles."""
    pass


class InvalidToken(StreamRolesError):
    """Invalid twitch token.

    The bot owner can set the twitch token using `streamrole clientid`.
    """
    pass


class StreamNotFound(StreamRolesError):
    """That stream could not be found."""
    pass


class APIError(StreamRolesError):
    """Something went wrong whilst contacting the twitch API."""
    pass
