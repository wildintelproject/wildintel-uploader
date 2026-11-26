"""The settings of the domain (dataclasses, `settings.general`) and the format of the settings files (Pydantic, `GENERAL`), one into the other.

Reading: the schema validates what the file says — migrating what older versions kept —, and the domain is made from it. Writing: the domain is turned
back into the schema, and that is what is written. What settings.toml still holds of the field work (FIELDWORK) goes across as it is: the domain keeps
it only to give it back."""
from __future__ import annotations

from dataclasses import asdict, fields

from wildintel_uploader.modules.settings.domain import models
from wildintel_uploader.modules.settings.infrastructure import schema

# Each section of the domain and the class it is made with.
_KINDS = {f.name: f.default_factory for f in fields(models.Settings)}  # type: ignore[misc]


def to_domain(kept: schema.Settings) -> models.Settings:
    """The settings of the domain, from what the schema validated."""
    sections = {}
    for name, section in models.Settings.SECTIONS.items():
        data = getattr(kept, section)
        if name == "legacy_fieldwork":
            sections[name] = models.LegacyFieldwork(**{kind: tuple(item.model_dump(mode="json") for item in getattr(data, kind))
                                                      for kind in ("trappers", "sd_cards", "cameras", "roles")})
            continue
        values = data.model_dump()
        if name == "validation":
            values["camera_levels"] = tuple(tuple(level) for level in values["camera_levels"])
            values["exif_fields"] = tuple(values["exif_fields"])
        sections[name] = _KINDS[name](**values)
    return models.Settings(**sections)


def _plain(value):
    """Tuples as lists, mappings as dicts: what the schema and TOML take."""
    if isinstance(value, (tuple, list)):
        return [_plain(v) for v in value]
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    return value


def to_schema(settings: models.Settings) -> schema.Settings:
    """The format of the file, from the settings of the domain — validated again, as anything written to it is."""
    data = {section: _plain(asdict(getattr(settings, name))) for name, section in models.Settings.SECTIONS.items()}
    return schema.Settings.model_validate(data)
