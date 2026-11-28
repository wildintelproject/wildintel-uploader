"""#248: each module says the sections of the settings it owns — their dataclasses in domain/settings.py (SECTIONS), their format in
infrastructure/settings.py (SCHEMAS) —, and the module of the settings lists them by name and puts them together with its own, in the order the file
has always had. Nothing is registered on import, and nothing is found by looking at the packages."""
import doctest
from dataclasses import dataclass, fields
from pathlib import Path

import pytest

from wildintel_uploader.modules.settings.domain import models, registry
from wildintel_uploader.modules.settings.domain.registry import Section, put_together
from wildintel_uploader.modules.settings.infrastructure import schema

ORDER = ["GENERAL", "TRAPPER", "EPICOLLECT5", "AGOUTI", "EPICOLLECTCSV", "DATA", "VALIDATION", "POSTVALIDATION", "PREPROCESSING", "FIELDWORK", "FIELDLOG"]
MODULES = Path(models.__file__).parents[2]


def test_the_sections_are_put_together_in_the_order_of_the_file():
    assert list(schema.Settings.model_fields) == ORDER
    assert [models.Settings.SECTIONS[f.name] for f in fields(models.Settings)] == ORDER


def test_each_section_is_owned_by_its_module_and_has_its_format():
    owner = {x.name: (x.domain.__module__, schema.SCHEMAS[x.name].__module__) for x in models.SECTIONS}
    assert owner["VALIDATION"] == ("wildintel_uploader.modules.prevalidation.domain.settings", "wildintel_uploader.modules.prevalidation.infrastructure.settings")
    assert owner["PREPROCESSING"][0].startswith("wildintel_uploader.modules.preprocessing.")
    assert owner["GENERAL"][0] == "wildintel_uploader.modules.settings.domain.models"
    assert set(schema.SCHEMAS) == {x.name for x in models.SECTIONS}


@pytest.mark.parametrize("layer, listing", [("domain", "domain/models.py"), ("infrastructure", "infrastructure/schema.py")])
def test_every_module_with_settings_is_listed_by_the_module_of_the_settings(layer: str, listing: str):
    """What discovery did, held by a test: a module that has a settings.py of a layer is imported by name where the sections are put together."""
    having = {p.parents[1].name for p in MODULES.glob(f"*/{layer}/settings.py")} - {"settings"}
    text = (MODULES / "settings" / listing).read_text(encoding="utf-8")
    missing = sorted(m for m in having if f"from wildintel_uploader.modules.{m}.{layer} import settings" not in text)
    assert not missing, f"{listing} does not list the settings of {missing}"


def test_the_registry_keeps_nothing_and_its_example_holds():
    assert doctest.testmod(registry).failed == 0
    assert not [n for n, v in vars(registry).items() if not n.startswith("_") and isinstance(v, (dict, list, set))]


def test_a_section_given_twice_is_a_mistake():
    @dataclass(frozen=True)
    class Thing:
        size: int = 1
    with pytest.raises(ValueError, match="THING"):
        put_together([Section("THING", "thing", 5, Thing), Section("THING", "other", 6, Thing)], __name__)
