"""#248: the layers of the modules keep to themselves — checked on the imports of their files, so that what is put together does not get mixed up again.

- The domain of a module is plain Python: no Pydantic, SQLModel, SQLAlchemy, FastAPI, Typer, Rich, Dynaconf, nor anything of an infrastructure.
- Its application — the use cases — uses its domain only: no infrastructure, no framework.
- Nothing asks for the code of before (core): each module has its own models, in its infrastructure (api_schemas.py)."""
import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[3] / "src" / "wildintel_uploader"
FRAMEWORKS = ("pydantic", "sqlmodel", "sqlalchemy", "fastapi", "typer", "rich", "dynaconf", "dishka", "starlette")


def _imports(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def _files(layer: str) -> list[Path]:
    return sorted(SRC.glob(f"modules/*/{layer}/*.py"))


@pytest.mark.parametrize("path", _files("domain"), ids=lambda p: f"{p.parts[-3]}/domain/{p.name}")
def test_the_domain_is_plain_python(path: Path):
    wrong = {i for i in _imports(path) if i.split(".")[0] in FRAMEWORKS or ".infrastructure" in i or ".application" in i or "entrypoints" in i}
    assert not wrong, f"{path.name} imports {sorted(wrong)}"


@pytest.mark.parametrize("path", _files("application"), ids=lambda p: f"{p.parts[-3]}/application/{p.name}")
def test_the_use_cases_use_their_domain_only(path: Path):
    wrong = {i for i in _imports(path) if i.split(".")[0] in FRAMEWORKS or ".infrastructure" in i or "entrypoints" in i}
    assert not wrong, f"{path.name} imports {sorted(wrong)}"


@pytest.mark.parametrize("path", sorted(SRC.glob("modules/*/**/*.py")), ids=lambda p: str(p.relative_to(SRC)))
def test_a_module_uses_another_only_through_its_domain(path: Path):
    own = path.relative_to(SRC / "modules").parts[0]
    wrong = {i for i in _imports(path) if i.startswith("wildintel_uploader.modules.") and i.split(".")[2] != own
             and (len(i.split(".")) < 4 or i.split(".")[3] != "domain")}
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


@pytest.mark.parametrize("path", sorted(p for p in [*SRC.glob("entrypoints/**/*.py"), *SRC.glob("web/*.py")] if p.name not in ("wiring.py", "config.py")),
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
    """The catalog (CatalogService) is its rules: the catalog as records is a contract of its own (catalog.domain.records), given apart."""
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

