"""#248: the layers of the modules keep to themselves — checked on the imports of their files, so that what is put together does not get mixed up again.

- The domain of a module is plain Python: no Pydantic, SQLModel, SQLAlchemy, FastAPI, Typer, Rich, Dynaconf, nor anything of an infrastructure.
- Its application — the use cases — uses its domain only: no infrastructure, no framework.
- Nothing asks for the code of before (core): each module has its own models, in its infrastructure (api_schemas.py)."""
import ast
import sys
import re
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[3] / "src" / "wildintel_uploader"
FRAMEWORKS = ("pydantic", "sqlmodel", "sqlalchemy", "fastapi", "typer", "rich", "dynaconf", "dishka", "starlette")


def _module_of(path: Path) -> str:
    """The dotted name of a file of the app: src/wildintel_uploader/modules/visits/domain/rules.py is wildintel_uploader.modules.visits.domain.rules."""
    parts = path.relative_to(SRC.parent).with_suffix("").parts
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def _imports(path: Path) -> set[str]:
    """What a file imports, by the absolute name — a relative import (from . import x, from ..domain import y) resolved where the file is."""
    names: set[str] = set()
    package = _module_of(path) if path.name == "__init__.py" else _module_of(path).rpartition(".")[0]
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                up = package.split(".")[: len(package.split(".")) - (node.level - 1)]
                base = ".".join([*up, *([base] if base else [])])
            if base:
                names.add(base)
                # `from package import module` imports that module too
                names |= {f"{base}.{a.name}" for a in node.names if (SRC.parent / f"{base}.{a.name}".replace(".", "/")).with_suffix(".py").exists()
                          or (SRC.parent / f"{base}.{a.name}".replace(".", "/") / "__init__.py").exists()}
    return names


def _files(layer: str) -> list[Path]:
    """Every file of that layer of every module — those in its subfolders too (infrastructure/steps/…)."""
    return sorted(SRC.glob(f"modules/*/{layer}/**/*.py"))


@pytest.mark.parametrize("path", _files("domain"), ids=lambda p: f"{p.parts[-3]}/domain/{p.name}")
def test_the_domain_is_plain_python(path: Path):
    wrong = {i for i in _imports(path) if i.split(".")[0] in FRAMEWORKS or ".infrastructure" in i or ".application" in i or "entrypoints" in i}
    assert not wrong, f"{path.name} imports {sorted(wrong)}"


@pytest.mark.parametrize("path", _files("application"), ids=lambda p: f"{p.parts[-3]}/application/{p.name}")
def test_the_use_cases_use_their_domain_only(path: Path):
    wrong = {i for i in _imports(path) if i.split(".")[0] in FRAMEWORKS or ".infrastructure" in i or "entrypoints" in i}
    assert not wrong, f"{path.name} imports {sorted(wrong)}"


def _the_format_of_a_section(path: Path, name: str) -> bool:
    """The one way into another module's adapters: the format of the file of the settings puts together the format of every section, which each
    module owns in its infrastructure/settings.py (SCHEMAS) — that file only, and only there."""
    # `from <module>.infrastructure import settings` is read as both the package and its settings.py
    return path == SRC / "modules" / "settings" / "infrastructure" / "schema.py" and name.endswith((".infrastructure.settings", ".infrastructure"))


@pytest.mark.parametrize("path", sorted(SRC.glob("modules/*/**/*.py")), ids=lambda p: str(p.relative_to(SRC)))
def test_a_module_uses_another_only_through_its_domain(path: Path):
    own = path.relative_to(SRC / "modules").parts[0]
    wrong = {i for i in _imports(path) if i.startswith("wildintel_uploader.modules.") and i.split(".")[2] != own
             and (len(i.split(".")) < 4 or i.split(".")[3] != "domain") and not _the_format_of_a_section(path, i)}
    assert not wrong, f"{path.name} imports {sorted(wrong)}"


@pytest.mark.parametrize("path", sorted(SRC.rglob("*.py")), ids=lambda p: str(p.relative_to(SRC)))
def test_nothing_of_the_app_asks_the_code_of_before(path: Path):
    """The code of before (core, its services and the plugs its functions were given what they needed through) is gone: nothing asks for it."""
    assert not {i for i in _imports(path) if i == "wildintel_uploader.core" or i.startswith("wildintel_uploader.core.") or i == "wildintel_uploader.shared.plugs"}


@pytest.mark.parametrize("path", sorted(SRC.glob("modules/**/*.py")), ids=lambda p: str(p.relative_to(SRC)))
def test_no_module_imports_the_entry_points(path: Path):
    """What a module needs from outside comes in — given to its classes when they are made —: the entry points, and where the app is put
    together, use the modules, never the other way round."""
    assert not {i for i in _imports(path) if i.startswith("wildintel_uploader.entrypoints") or i.startswith("wildintel_uploader.web")}


def test_no_module_has_plugs():
    """No module's adapters are functions waiting to be given what they need: they are classes, given it when they are made."""
    assert sorted(SRC.glob("modules/*/infrastructure/plugs.py")) == [] and not (SRC / "shared" / "plugs.py").exists()


@pytest.mark.parametrize("path", sorted(p for p in [*SRC.glob("entrypoints/**/*.py"), *SRC.glob("web/*.py")]
                                         if p.name != "config.py" and "wiring" not in p.relative_to(SRC).parts),
                         ids=lambda p: str(p.relative_to(SRC)))
def test_the_entry_points_take_of_a_module_its_contract_and_its_api_schemas_only(path: Path):
    """What an entry point asks of a module is its contract (domain) and the models of its web API (infrastructure.api_schemas): the adapters
    are chosen where the app is put together (entrypoints.wiring, and entrypoints.config for the settings), never by the entry points themselves."""
    wrong = {i for i in _imports(path) if i.startswith("wildintel_uploader.modules.") and ".infrastructure" in i and not i.endswith(".infrastructure.api_schemas")}
    assert not wrong, f"{path.name} imports {sorted(wrong)}"


@pytest.mark.parametrize("path", sorted(SRC.glob("modules/*/infrastructure/*.py")), ids=lambda p: str(p.relative_to(SRC)))
def test_an_adapter_is_given_what_it_reads_of_the_settings_not_all_of_them(path: Path):
    """An adapter is given the section or the folder of the settings it reads, not the settings whole — but the backup of the settings, which
    keeps them whole."""
    takes_all = "StoredSettings" in path.read_text(encoding="utf-8")
    assert not takes_all or path.relative_to(SRC).as_posix() == "modules/backup/infrastructure/outside.py"


@pytest.mark.parametrize("path", sorted(p for p in SRC.glob("modules/*/**/*.py") if p.relative_to(SRC / "modules").parts[0] != "catalog"),
                         ids=lambda p: str(p.relative_to(SRC)))
def test_only_a_backup_takes_the_records_of_the_catalog_round_its_rules(path: Path):
    """The records of the catalog as they are kept (CatalogRecordStore) go round its rules: only the backup, which copies and restores them as
    they are, is given them."""
    takes_them = "CatalogRecordStore" in path.read_text(encoding="utf-8")
    assert not takes_them or path.relative_to(SRC).as_posix() == "modules/backup/infrastructure/outside.py"


def test_the_catalog_does_not_hand_out_its_records():
    """The catalog (CatalogService) is its rules: the records as a backup copies them are a contract of their own (catalog.domain.records), given
    apart."""
    from wildintel_uploader.modules.catalog.domain.ports import CatalogService
    assert not hasattr(CatalogService, "records")


@pytest.mark.parametrize("path", sorted(SRC.glob("modules/catalog/**/*.py")), ids=lambda p: str(p.relative_to(SRC)))
def test_the_catalog_does_not_need_the_module_of_the_visits(path: Path):
    """The visits need the catalog; the catalog reads what it needs of the visits where they are kept, with its own records — never through the
    contract of the visits (VisitsService), so that the two are not put together in a circle."""
    assert "wildintel_uploader.modules.visits.domain.ports" not in _imports(path)


@pytest.mark.parametrize("path", sorted(SRC.glob("modules/catalog/infrastructure/*_repository.py")), ids=lambda p: p.name)
def test_a_repository_of_the_catalog_keeps_records_only(path: Path):
    """Where the records of the catalog are kept — files or a database — knows nothing of the folders of the research projects
    (ports.ProjectFolders): a backend of records can be swapped for another."""
    text = path.read_text(encoding="utf-8")
    assert "iterdir(" not in text and "collections_dir" not in text and ".acronym).mkdir(" not in text


@pytest.mark.parametrize("path", sorted(SRC.rglob("*.py")), ids=lambda p: str(p.relative_to(SRC)))
def test_no_file_takes_a_private_name_of_another(path: Path):
    """What a file offers to the others is named so: a name with an underscore in front is its own, never imported from elsewhere."""
    taken = {f"{node.module}.{a.name}" for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
             if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("wildintel_uploader")
             for a in node.names if a.name.startswith("_") and not a.name.startswith("__")}
    assert not taken, f"{path.name} takes {sorted(taken)}"


def test_the_app_has_no_catalog_as_records():
    """The catalog as dicts (CatalogRecords) is gone (#248): the modules ask the catalog's contract and see its models; the backup copies and
    restores the records as they are kept (CatalogRecordStore). Only the tests set up what they need as records (tests/support/catalog_records)."""
    users = sorted(str(p.relative_to(SRC)) for p in SRC.rglob("*.py") if "CatalogRecords" in p.read_text(encoding="utf-8"))
    assert not users, users


_IO = re.compile(r"\.(read_text|write_text|read_bytes|write_bytes|rglob|glob|iterdir|mkdir|unlink|rmdir|touch)\(|\.(is_file|is_dir|exists|stat|resolve)\(\)"
                 r"|(?<![\w.])(?<!def )open\(|\bshutil\.|\bsubprocess\b|\bos\.(?!path\.sep)|\bjson\.(load|dump)\(|\b(requests|httpx|urllib)\.")


@pytest.mark.parametrize("path", [*_files("domain"), *_files("application")], ids=lambda p: f"{p.parts[-3]}/{p.parts[-2]}/{p.name}")
def test_the_domain_and_the_use_cases_touch_no_file_process_or_network(path: Path):
    """What a module reads or writes — files, folders, processes, the network — goes through its ports: the domain and the use cases only ask them."""
    found = [f"{n}: {line.strip()}" for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
             if _IO.search(line) and not line.lstrip().startswith(("#", '"""'))]
    assert not found, "\n".join(found)


@pytest.mark.parametrize("path", _files("infrastructure"), ids=lambda p: f"{p.parts[-3]}/infrastructure/{p.name}")
def test_an_adapter_asks_the_ports_not_the_use_cases(path: Path):
    """An adapter depends on the ports of the domain — never on the use cases (application), which it would then be built around."""
    wrong = {i for i in _imports(path) if ".application" in i or "entrypoints" in i}
    assert not wrong, f"{path.name} imports {sorted(wrong)}"


@pytest.mark.parametrize("path", [*_files("domain"), *_files("application")], ids=lambda p: f"{p.parts[-3]}/{p.parts[-2]}/{p.name}")
def test_the_domain_and_the_use_cases_do_not_lean_on_pydantic(path: Path):
    """A record validated by Pydantic (shared.camtrap) may pass through the domain and the use cases, but what it is made into — a dict, a copy —
    is asked of the adapters: neither calls Pydantic's own API."""
    found = [f"{n}: {line.strip()}" for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
             if re.search(r"\.model_(dump|dump_json|copy|validate|fields)\b", line)]
    assert not found, "\n".join(found)


@pytest.mark.parametrize("path", sorted(SRC.glob("shared/**/*.py")), ids=lambda p: str(p.relative_to(SRC)))
def test_the_shared_kernel_needs_no_module_and_no_entry_point(path: Path):
    """The shared kernel is under every module: it never reaches up for one of them, nor for the entry points — what it needs of them is given."""
    wrong = {i for i in _imports(path) if i.startswith(("wildintel_uploader.modules", "wildintel_uploader.entrypoints", "wildintel_uploader.web"))}
    assert not wrong, f"{path.name} imports {sorted(wrong)}"


def test_the_parser_resolves_relative_imports_and_finds_the_files_in_subfolders(tmp_path):
    """The tests above hold only as far as they see: a relative import is read as the module it names, and the files of a layer's subfolders are
    among those checked."""
    here = SRC / "modules" / "visits" / "domain" / "rules.py"
    probe = here.with_name("_probe_of_the_tests.py")
    probe.write_text("from . import rules\nfrom ..infrastructure import csv_file\n", encoding="utf-8")
    try:
        found = _imports(probe)
    finally:
        probe.unlink()
    assert {"wildintel_uploader.modules.visits.domain", "wildintel_uploader.modules.visits.infrastructure"} <= found
    assert any("infrastructure/steps" in str(p) for p in _files("infrastructure")) and any("domain/checks" in str(p) for p in _files("domain"))


@pytest.mark.parametrize("path", sorted(SRC.rglob("*.py")), ids=lambda p: str(p.relative_to(SRC)))
def test_no_file_reaches_for_a_private_name_of_another_module(path: Path):
    """What another module offers is named so: `rules._stamp` of a module imported from elsewhere is reaching into it, as `from rules import _stamp`
    would be."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: dict[str, str] = {}   # the names in this file that are modules of the app
    package = _module_of(path) if path.name == "__init__.py" else _module_of(path).rpartition(".")[0]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name.startswith("wildintel_uploader") and a.asname:
                    modules[a.asname] = a.name
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                up = package.split(".")[: len(package.split(".")) - (node.level - 1)]
                base = ".".join([*up, *([base] if base else [])])
            for a in node.names:
                full = f"{base}.{a.name}"
                if full.startswith("wildintel_uploader") and ((SRC.parent / full.replace(".", "/")).with_suffix(".py").exists()
                                                             or (SRC.parent / full.replace(".", "/") / "__init__.py").exists()):
                    modules[a.asname or a.name] = full
    reached = {f"{modules[n.value.id]}.{n.attr}" for n in ast.walk(tree)
               if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id in modules
               and n.attr.startswith("_") and not n.attr.startswith("__") and modules[n.value.id] != _module_of(path)}
    assert not reached, f"{path.name} reaches for {sorted(reached)}"


# What of the shared kernel the domain and the use cases may lean on: plain Python, with no file, no process, no library — the ids of the records,
# how their names are compared, the dates they keep of themselves, and the errors the kernel tells of. The rest of `shared` (storage, desktop, camtrap, parallel, logs, version) is for
# the adapters and the entry points.
SHARED_KERNEL = {"wildintel_uploader.shared", "wildintel_uploader.shared.ids", "wildintel_uploader.shared.identity", "wildintel_uploader.shared.audit",
                 "wildintel_uploader.shared.errors", "wildintel_uploader.shared.deployment_record"}


@pytest.mark.parametrize("path", _files("domain") + _files("application"), ids=lambda p: str(p.relative_to(SRC / "modules")))
def test_the_domain_and_the_use_cases_take_of_shared_only_its_plain_kernel(path: Path):
    shared = {name for name in _imports(path) if name == "wildintel_uploader.shared" or name.startswith("wildintel_uploader.shared.")}
    assert shared <= SHARED_KERNEL, f"{path.name} takes {sorted(shared - SHARED_KERNEL)} of shared: only {sorted(SHARED_KERNEL)} are plain"


@pytest.mark.parametrize("name", sorted(SHARED_KERNEL - {"wildintel_uploader.shared"}))
def test_the_plain_kernel_of_shared_imports_only_the_standard_library(name: str):
    path = SRC.parent / (name.replace(".", "/") + ".py")
    others = {n.split(".")[0] for n in _imports(path)} - {"__future__", "wildintel_uploader"}
    assert others <= set(sys.stdlib_module_names), f"{path.name} imports {sorted(others - set(sys.stdlib_module_names))}"
    assert {n for n in _imports(path) if n.startswith("wildintel_uploader")} <= SHARED_KERNEL


@pytest.mark.parametrize("path", sorted(SRC.glob("modules/catalog/**/*.py")), ids=lambda p: str(p.relative_to(SRC / "modules")))
def test_the_catalog_takes_of_the_visits_only_what_they_offer_it(path: Path):
    """The visits need the catalog; the catalog needs a little of the visits — through one door, visits.domain.for_the_catalog, narrow and kept
    stable, so the rest of the domain of the visits changes without the catalog knowing."""
    door = "wildintel_uploader.modules.visits.domain.for_the_catalog"
    taken = {i for i in _imports(path) if i.startswith("wildintel_uploader.modules.visits")} - {door, "wildintel_uploader.modules.visits.domain"}
    assert not taken, f"{path.name} takes {sorted(taken)} of the visits: only {door}"


def test_every_secret_of_the_file_is_left_out_of_what_it_prints():
    """A secret of settings.toml (marked {"secret": True}) is never in the repr of its section: a log of the settings does not show it (#248)."""
    from wildintel_uploader.modules.settings.infrastructure import schema

    for section, name in schema.secret_fields():
        assert schema.Settings.model_fields[section].annotation.model_fields[name].repr is False, f"{section}.{name} is printed"


# What a module offers the others besides its contract (ports), its errors and kinds (models, shapes, errors), its settings and a door made for one
# of them (for_the_<that module>) — each said, with why: anything else of a module is its own, and may change without the others knowing.
PUBLISHED = {
    "settings": {"rules": "the rules every section of the settings follows", "registry": "how a module says the sections it owns"},
    "fileinfo": {"folder": "MediaFolder, what the checks of the images are run over"},
    "deployments": {"naming": "how deployments and collections are named and ordered", "seal": "the name of the seal a deployment keeps"},
    "postvalidation": {"statistics": "the metrics of a deployment's times, which the statistics of a revision compare"},
    "catalog": {"records": "the records as they are kept, for a backup only (see its own test)",
                "history": "because: why a change of status is written down, said by who makes it"},
}
CONTRACT = {"ports", "models", "shapes", "errors", "settings"}


def _what_of_another(path: Path) -> set[tuple[str, str]]:
    """(module, part of its domain) of each module other than its own that a file takes something of."""
    own = path.relative_to(SRC / "modules").parts[0]
    found = set()
    for name in _imports(path):
        parts = name.split(".")
        if len(parts) >= 5 and parts[:2] == ["wildintel_uploader", "modules"] and parts[2] != own and parts[3] == "domain":
            found.add((parts[2], parts[4]))
    return found


@pytest.mark.parametrize("path", sorted(SRC.glob("modules/*/**/*.py")), ids=lambda p: str(p.relative_to(SRC / "modules")))
def test_a_module_takes_of_another_only_what_that_one_offers(path: Path):
    own = path.relative_to(SRC / "modules").parts[0]
    wrong = sorted(f"{module}.domain.{part}" for module, part in _what_of_another(path)
                   if part not in CONTRACT and part != f"for_the_{own}" and part not in PUBLISHED.get(module, {}))
    assert not wrong, f"{path.name} takes {wrong}: what a module has of its own is not offered — ask it a door (for_the_{own}) or publish it"


def test_the_format_of_a_section_of_the_settings_says_its_shape_not_its_rules():
    """A bound (ge, le…) or a set of choices (Literal) of a setting is a rule, and the rules are the domain's (#248): the schema of a section says
    only what kind each setting is — the domain checks the rest on every read and every write of a settings file. The field work versions before
    kept in the settings (FIELDWORK) is read as it was, and is not a section of settings."""
    import typing

    from annotated_types import Ge, Gt, Le, Lt

    from wildintel_uploader.modules.settings.infrastructure import schema

    def kinds(kind) -> list:
        return [kind, *(k for arg in typing.get_args(kind) for k in kinds(arg))]
    rules = sorted(f"{section}.{name}" for section, info in schema.Settings.model_fields.items() if section != "FIELDWORK"
                   for name, field in info.annotation.model_fields.items()
                   if any(isinstance(m, (Ge, Gt, Le, Lt)) for m in field.metadata) or any(typing.get_origin(k) is typing.Literal for k in kinds(field.annotation)))
    assert not rules, f"Rules in the format of the file — they are the domain's: {rules}"


def test_a_port_a_class_of_the_app_implements_is_an_abc_and_a_protocol_is_only_a_narrow_view():
    """The ports a class of the app implements say so (ABC): it names the port, and a method it lacks fails when it is made, not when it is first
    used. A Protocol is for a narrow view of what was not written for that port — a module (StoredSettings: entrypoints.config), a Pydantic model
    (DeploymentRecord), a part of another contract (ImageDates, DeploymentSealer) —, met by its shape (#248)."""
    protocols = {}
    for path in [*SRC.glob("modules/*/domain/**/*.py"), *SRC.glob("shared/*.py")]:
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            if isinstance(node, ast.ClassDef) and any(ast.unparse(b) == "Protocol" for b in node.bases):
                protocols[node.name] = path
    implemented = sorted({f"{base} ({protocols[base].relative_to(SRC)}) by {node.name}"
                          for path in SRC.rglob("*.py") for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
                          if isinstance(node, ast.ClassDef) and not any(ast.unparse(b) == "Protocol" for b in node.bases)
                          for base in (ast.unparse(b) for b in node.bases) if base in protocols})
    assert not implemented, f"Protocols a class implements by name — make them ABCs: {implemented}"

