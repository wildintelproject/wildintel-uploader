"""What every command of the command line shares: the console, friendly errors — a module's own words, or what TRAPPER and the network say,
as the web API tells them (modules.uploaders) — and a clean exit."""
from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

import typer
from rich.console import Console

console = Console()
err_console = Console(stderr=True)

T = TypeVar("T")


def describe(exc: BaseException) -> str:
    """What went wrong, for a person — the words the web API shows."""
    from wildintel_uploader.entrypoints.wiring import error_words
    message = getattr(exc, "message", None)
    if isinstance(message, str) and message:
        return message
    return error_words(exc) if isinstance(exc, Exception) else (str(exc) or type(exc).__name__)


def fail(message: str, code: int = 1) -> typer.Exit:
    err_console.print(f"[red]✘  {message}[/red]")
    return typer.Exit(code)


def call(fn: Callable[[], T]) -> T:
    """fn(), its errors as a clean message and exit code 1."""
    try:
        return fn()
    except typer.Exit:
        raise
    except Exception as exc:
        raise fail(describe(exc)) from exc
