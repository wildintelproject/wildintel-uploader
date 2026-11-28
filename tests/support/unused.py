"""A port a test does not use, said so: given where a module needs it, and failing — naming it — if the test reaches it after all."""
from __future__ import annotations


class Unused:
    def __init__(self, port: str) -> None:
        object.__setattr__(self, "_port", port)

    def __getattr__(self, name: str):
        raise AssertionError(f"This test does not give the module a {object.__getattribute__(self, '_port')}, and it asked it for {name!r}.")

    def __call__(self, *args, **kwargs):
        raise AssertionError(f"This test does not give the module a {object.__getattribute__(self, '_port')}, and it called it.")


def unused(port: str):
    return Unused(port)
