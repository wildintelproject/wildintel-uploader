"""Plugs (#248): the ports out of the adapters that are still functions of the code of before — not classes, to be given what they need when they
are made. Each module says in its `infrastructure/plugs.py` what those functions need — another module through its contract, the settings… —,
and where the app is put together (entrypoints.wiring) plugs in what it is. A module so never imports the entry points: what it needs comes in.

A plug stands for what is plugged into it: it is called as it is called, and asked for what it has."""
from __future__ import annotations

from typing import Any, Generic, TypeVar

T = TypeVar("T")


class NotPlugged(RuntimeError):
    """A plug asked before the app was put together: entrypoints.wiring plugs them all when it is imported."""


class Plug(Generic[T]):
    def __init__(self, what: str) -> None:
        self._what = what
        self._to: T | None = None

    def plug(self, to: T) -> None:
        self._to = to

    @property
    def plugged(self) -> bool:
        return self._to is not None

    def _plugged(self) -> Any:
        if self._to is None:
            raise NotPlugged(f"Nothing is plugged into {self._what}: entrypoints.wiring plugs it when the app is put together.")
        return self._to

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self._plugged()(*args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("__") or name in ("_to", "_what"):
            raise AttributeError(name)
        return getattr(self._plugged(), name)

    def __setattr__(self, name: str, value: Any) -> None:
        """Only the plug's own: what is asked of it is what is plugged in's — patch that (a test patches entrypoints.config, not this)."""
        if name not in ("_what", "_to"):
            raise AttributeError(f"{name} is not the plug's: patch what is plugged into {self._what}, not the plug")
        object.__setattr__(self, name, value)

    def __repr__(self) -> str:
        return f"<plug: {self._what}{'' if self.plugged else ' (not plugged)'}>"
