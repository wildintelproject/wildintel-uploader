"""#248: each module says what it does, its contract and how it is used in a README.md beside it — the docstring of its package points there —,
and the developer manual links it. A part of a contract that is not named in its README is a README out of date."""
import ast
from pathlib import Path

import pytest

MODULES = Path(__file__).resolve().parents[3] / "src" / "wildintel_uploader" / "modules"
MANUAL = Path(__file__).resolve().parents[3] / "docs" / "developer-manual.md"
NAMES = sorted(p.name for p in MODULES.iterdir() if (p / "domain" / "ports.py").is_file())


def _contract(module: str) -> set[str]:
    """The contract of a module: its …Service, and the parts it is made of."""
    tree = ast.parse((MODULES / module / "domain" / "ports.py").read_text(encoding="utf-8"))
    classes = {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}
    found = set()
    for name, node in classes.items():
        if name.endswith("Service"):
            found |= {name, *(b.id for b in node.bases if isinstance(b, ast.Name) and b.id in classes)}
    return found


@pytest.mark.parametrize("module", NAMES)
def test_each_module_has_a_readme_that_names_every_part_of_its_contract(module: str):
    readme = MODULES / module / "README.md"
    assert readme.is_file(), f"{module} has no README.md"
    text = readme.read_text(encoding="utf-8")
    missing = sorted(part for part in _contract(module) if f"`{part}`" not in text)
    assert _contract(module) and not missing, f"{module}/README.md does not name {missing}"


@pytest.mark.parametrize("module", NAMES)
def test_the_package_of_each_module_points_to_its_readme(module: str):
    doc = ast.get_docstring(ast.parse((MODULES / module / "__init__.py").read_text(encoding="utf-8"))) or ""
    assert "README.md" in doc


@pytest.mark.parametrize("module", NAMES)
def test_the_developer_manual_links_the_readme_of_each_module(module: str):
    """By an address of the repository — it works in the manual published and read on GitHub alike."""
    assert f"/blob/development/src/wildintel_uploader/modules/{module}/README.md)" in MANUAL.read_text(encoding="utf-8")
