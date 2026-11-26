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
