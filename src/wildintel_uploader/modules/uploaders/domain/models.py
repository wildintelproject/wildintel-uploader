"""What the uploaders are given — an account, perhaps only in part: what it lacks is taken from the settings — and what they refuse, each saying
the HTTP status the entry points tell it with."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Account:
    """An account of TRAPPER as a request gives it."""
    url: str | None = None
    username: str | None = None
    password: str | None = None


Credentials = tuple[str, str, str]   # (url, username, password), all of them


class UploaderError(Exception):
    """What an uploader refuses or can't do, with its words."""
    status = 400

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotAuthorized(UploaderError):
    status = 401


class Forbidden(UploaderError):
    status = 403


class NotThere(UploaderError):
    status = 404


class Unreachable(UploaderError):
    status = 502


class TimedOut(UploaderError):
    status = 504
