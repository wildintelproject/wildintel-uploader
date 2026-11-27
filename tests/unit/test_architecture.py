"""#248: the layers of the modules keep to themselves — checked on the imports of their files, so that what is put together does not get mixed up again.

- The domain of a module is plain Python: no Pydantic, SQLModel, SQLAlchemy, FastAPI, Typer, Rich, Dynaconf, nor anything of an infrastructure.
- Its application — the use cases — uses its domain only: no infrastructure, no framework.
- The new code (modules/, entrypoints/) does not take the models of the API of before (core/schemas): each module has its own, in its infrastructure
  (api_schemas.py)."""
import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src" / "wildintel_uploader"
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


@pytest.mark.parametrize("path", sorted([*SRC.glob("modules/**/*.py"), *SRC.glob("entrypoints/**/*.py")]), ids=lambda p: str(p.relative_to(SRC)))
def test_the_new_code_does_not_take_the_models_of_the_api_of_before(path: Path):
    assert not {i for i in _imports(path) if i.startswith("wildintel_uploader.core.schemas")}


@pytest.mark.parametrize("path", sorted(SRC.glob("modules/*/**/*.py")), ids=lambda p: str(p.relative_to(SRC)))
def test_a_module_uses_another_only_through_its_domain(path: Path):
    own = path.relative_to(SRC / "modules").parts[0]
    wrong = {i for i in _imports(path) if i.startswith("wildintel_uploader.modules.") and i.split(".")[2] != own
             and (len(i.split(".")) < 4 or i.split(".")[3] != "domain")}
    assert not wrong, f"{path.name} imports {sorted(wrong)}"


# ── what a module still asks of the code of before, or of another module, through the old names of core.services ──
# Each line is a coupling to cut: a new one fails this test, and one that is cut has to leave this list — it only shrinks.
STILL_COUPLED = {
}


def _owner(name: str) -> str:
    """The module a name of core.services is now — or "core", while it is still the code of before there."""
    import re
    text = (SRC / "core" / "services" / f"{name}.py").read_text(encoding="utf-8")
    found = re.search(r"from wildintel_uploader\.(?:modules\.(\w+)|shared)[\w.]* import", text) if "sys.modules[__name__] = _moved" in text else None
    return (found.group(1) or "shared") if found else "core"


def _coupled() -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for path in SRC.glob("modules/*/**/*.py"):
        module = path.relative_to(SRC / "modules").parts[0]
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = []
            if isinstance(node, ast.ImportFrom) and node.module == "wildintel_uploader.core.services":
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("wildintel_uploader.core.services."):
                names = [node.module.rsplit(".", 1)[1]]
            for name in names:
                if _owner(name) not in (module, "shared"):
                    out.setdefault(str(path.relative_to(SRC / "modules")), set()).add(name)
    return out


def test_no_module_is_coupled_to_another_but_what_is_still_to_cut():
    assert _coupled() == STILL_COUPLED


@pytest.mark.parametrize("path", sorted(p for p in SRC.rglob("*.py") if p.relative_to(SRC).parts[0] != "core"), ids=lambda p: str(p.relative_to(SRC)))
def test_nothing_of_the_app_asks_the_code_of_before(path: Path):
    """core is only the old names of what moved to the modules, the shared kernel and the entry points — kept for what has not been told yet."""
    assert not {i for i in _imports(path) if i == "wildintel_uploader.core" or i.startswith("wildintel_uploader.core.")}


@pytest.mark.parametrize("path", sorted(SRC.glob("modules/**/*.py")), ids=lambda p: str(p.relative_to(SRC)))
def test_no_module_imports_the_entry_points(path: Path):
    """What a module needs from outside comes in — given to its classes when they are made, or plugged into its plugs (shared.plugs) —:
    the entry points, and where the app is put together, use the modules, never the other way round."""
    assert not {i for i in _imports(path) if i.startswith("wildintel_uploader.entrypoints") or i.startswith("wildintel_uploader.web")}


def test_every_plug_of_every_module_is_plugged_when_the_app_is_put_together():
    import importlib
    import pkgutil

    from wildintel_uploader import modules
    from wildintel_uploader.entrypoints import wiring
    from wildintel_uploader.shared.plugs import Plug
    wiring.plug_the_modules()
    plugs = {}
    for found in pkgutil.iter_modules(modules.__path__):
        if (SRC / "modules" / found.name / "infrastructure" / "plugs.py").is_file():
            module = importlib.import_module(f"wildintel_uploader.modules.{found.name}.infrastructure.plugs")
            plugs |= {f"{found.name}.{n}": p for n, p in vars(module).items() if isinstance(p, Plug)}
    assert plugs and [n for n, p in plugs.items() if not p.plugged] == []
