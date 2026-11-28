"""The sections of the settings, each owned by the module it belongs to (#248) — plain Python, with no state and nothing done on import. A module that
has settings of its own says which in its `domain/settings.py` — the dataclass of each section, with its rules, as a `Section` in `SECTIONS` — and
in its `infrastructure/settings.py` — the format of each in settings.toml (Pydantic), in `SCHEMAS`:

    # prevalidation/domain/settings.py
    @dataclass(frozen=True)
    class ValidationSettings: ...
    SECTIONS = (Section("VALIDATION", "validation", 70, ValidationSettings),)

    # prevalidation/infrastructure/settings.py
    class ValidationSettings(BaseModel): ...
    SCHEMAS = {"VALIDATION": ValidationSettings}

The module of the settings lists them by name — domain.models.SECTIONS, infrastructure.schema.SCHEMAS — and puts them together (put_together), in
the order they are written in. Nothing is found by looking at the packages: an architecture test holds the lists to the modules that have settings.

    >>> @dataclass(frozen=True)
    ... class Thing:
    ...     size: int = 1
    >>> Settings = put_together([Section("THING", "thing", 5, Thing)], __name__)
    >>> Settings().thing, Settings.SECTIONS
    (Thing(size=1), {'thing': 'THING'})
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field, make_dataclass


@dataclass(frozen=True)
class Section:
    """A section of settings.toml: its name there (VALIDATION), its attribute in the settings of the domain (validation), where it is written among
    the others, and its dataclass."""
    name: str
    attribute: str
    order: int
    domain: type


def in_order(sections: Iterable[Section]) -> list[Section]:
    """The sections in the order they are written in; a name given twice is a mistake of the lists."""
    listed = list(sections)
    names = [s.name for s in listed]
    twice = sorted({n for n in names if names.count(n) > 1})
    if twice:
        raise ValueError(f"A section of the settings is given twice: {', '.join(twice)}")
    return sorted(listed, key=lambda s: (s.order, s.name))


def put_together(sections: Iterable[Section], module: str) -> type:
    """The settings of one config: a frozen dataclass with an attribute for each section — made with its defaults —, in the order they are written
    in; `SECTIONS` names each in settings.toml (and in what the settings page sends and receives)."""
    ordered = in_order(sections)
    cls = make_dataclass("Settings", [(s.attribute, s.domain, field(default_factory=s.domain)) for s in ordered], frozen=True,
                         namespace={"__module__": module})
    cls.__doc__ = """All the settings of one config: the sections of the module of the settings and those of the other modules (see registry)."""
    cls.SECTIONS = {s.attribute: s.name for s in ordered}  # type: ignore[attr-defined]
    return cls
