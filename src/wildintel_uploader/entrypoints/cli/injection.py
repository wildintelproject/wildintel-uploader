"""Dishka for the commands of the command line: `@inject` fills the parameters marked `FromDishka[...]` from the container of `entrypoints.wiring`, in a
scope of their own for each command (Scope.REQUEST, opened when the command starts and closed when it ends), and leaves them out of what Typer sees.

Dishka's own integration for Click does not serve: this Typer carries a copy of Click of its own, whose context is not the one that integration looks
for. So it is built here on what dishka gives for integrations of one's own (`dishka.integrations.base.wrap_injection`).

    @settings_app.command("show")
    @inject
    def show(service: FromDishka[SettingsService]) -> None: ..."""
from __future__ import annotations

import atexit
from collections.abc import Callable
from typing import TypeVar

from dishka import Container
from dishka.integrations.base import wrap_injection

from wildintel_uploader.entrypoints import wiring

T = TypeVar("T")
_container: Container | None = None


def container() -> Container:
    """The container of the command line: made the first time a command asks, closed when the program ends."""
    global _container
    if _container is None:
        _container = wiring.make_app_container()
        atexit.register(_container.close)
    return _container


def inject(func: Callable[..., T]) -> Callable[..., T]:
    return wrap_injection(func=func, container_getter=lambda _args, _kwargs: container(), remove_depends=True, is_async=False, manage_scope=True)
