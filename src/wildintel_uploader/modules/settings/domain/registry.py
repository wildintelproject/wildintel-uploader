"""The sections of the settings, each registered by the module it belongs to (#248): a module that has settings of its own says so in its
`domain/settings.py` — the dataclass of its section, with its rules — and in its `infrastructure/settings.py` — the format of that section in
settings.toml (Pydantic) —, each with a decorator:

    @settings_registry.section("VALIDATION", "validation", order=70)
    @dataclass(frozen=True)
    class ValidationSettings: ...

    @settings_registry.schema("VALIDATION")
    class ValidationSettings(BaseModel): ...

The module of the settings puts its own sections and the registered ones together — the settings of the domain and the format of the file —, in
the order they are written in. It finds them by itself (discover): every module's settings.py of a layer is imported, so a module only has to have
one. Plain Python: what a schema is, the registry does not look at."""
from __future__ import annotations

import importlib
import importlib.util
import pkgutil
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T", bound=type)

MODULES_PACKAGE = "wildintel_uploader.modules"


@dataclass
class Section:
    """A section of settings.toml: its name there (VALIDATION), its attribute in the settings of the domain (validation), where it is written among
    the others, its dataclass and its schema."""
    name: str
    attribute: str
    order: int
    domain: type | None = None
    schema: type | None = None


class SettingsRegistry:
    def __init__(self) -> None:
        self._sections: dict[str, Section] = {}

    def section(self, name: str, attribute: str, *, order: int = 1000) -> Callable[[T], T]:
        """Registers the dataclass of a section."""
        def register(cls: T) -> T:
            found = self._sections.setdefault(name, Section(name, attribute, order))
            found.attribute, found.order, found.domain = attribute, order, cls
            return cls
        return register

    def schema(self, name: str) -> Callable[[T], T]:
        """Registers the format of a section in the file."""
        def register(cls: T) -> T:
            self._sections.setdefault(name, Section(name, name.lower(), 1000)).schema = cls
            return cls
        return register

    def sections(self) -> list[Section]:
        """Every section registered, in the order they are written in."""
        return sorted(self._sections.values(), key=lambda s: (s.order, s.name))

    def get(self, name: str) -> Section:
        return self._sections[name]


settings_registry = SettingsRegistry()


def discover(layer: str, package: str = MODULES_PACKAGE) -> list[str]:
    """Imports `<module>.<layer>.settings` of every module that has one — so that each registers its sections —; gives the ones imported."""
    found = []
    for module in pkgutil.iter_modules(importlib.import_module(package).__path__):
        name = f"{package}.{module.name}.{layer}.settings"
        try:
            exists = importlib.util.find_spec(name) is not None
        except ModuleNotFoundError:
            exists = False
        if exists:
            importlib.import_module(name)
            found.append(name)
    return found
