"""#248: each module registers the section of the settings it owns — its dataclass in domain/settings.py, its format in infrastructure/settings.py —,
and the module of the settings puts them together with its own, in the order the file has always had."""
from dataclasses import dataclass, fields

from pydantic import BaseModel

from wildintel_uploader.modules.settings.domain import models
from wildintel_uploader.modules.settings.domain.registry import SettingsRegistry, discover, settings_registry
from wildintel_uploader.modules.settings.infrastructure import schema

ORDER = ["GENERAL", "TRAPPER", "EPICOLLECT5", "AGOUTI", "EPICOLLECTCSV", "DATA", "VALIDATION", "POSTVALIDATION", "PREPROCESSING", "FIELDWORK", "FIELDLOG"]


def test_each_module_with_settings_is_found_by_itself():
    found = {name.split(".")[2] for name in discover("domain")}
    assert {"prevalidation", "postvalidation", "preprocessing"} <= found
    assert {"prevalidation", "postvalidation", "preprocessing"} <= {name.split(".")[2] for name in discover("infrastructure")}


def test_the_sections_are_put_together_in_the_order_of_the_file():
    assert list(schema.Settings.model_fields) == ORDER
    assert [models.Settings.SECTIONS[f.name] for f in fields(models.Settings)] == ORDER


def test_each_section_is_owned_by_its_module():
    owner = {x.name: (x.domain.__module__, x.schema.__module__) for x in settings_registry.sections()}
    assert owner["VALIDATION"] == ("wildintel_uploader.modules.prevalidation.domain.settings", "wildintel_uploader.modules.prevalidation.infrastructure.settings")
    assert owner["PREPROCESSING"][0].startswith("wildintel_uploader.modules.preprocessing.")
    assert owner["GENERAL"][0] == "wildintel_uploader.modules.settings.domain.models"


def test_a_section_registers_its_dataclass_and_its_format():
    registry = SettingsRegistry()

    @registry.schema("THING")
    class ThingFile(BaseModel):
        size: int = 1

    @registry.section("THING", "thing", order=5)
    @dataclass(frozen=True)
    class Thing:
        size: int = 1

    (section,) = registry.sections()
    assert (section.name, section.attribute, section.order, section.domain, section.schema) == ("THING", "thing", 5, Thing, ThingFile)
