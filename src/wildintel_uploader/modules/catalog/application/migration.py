"""Moving the catalog from where it is kept to another place — the JSON files of the collections folder, a SQLite database —: everything copied as it
is kept (ids and dates too, nothing dated anew), and read back to see that it is the same. It knows only the port: any two repositories do."""
from __future__ import annotations

from dataclasses import dataclass

from wildintel_uploader.modules.catalog.domain.models import CatalogError
from wildintel_uploader.modules.catalog.domain.ports import CatalogRepository


@dataclass(frozen=True)
class CopiedCatalog:
    trappers: int
    projects: int


class TargetNotEmpty(CatalogError):
    """Where the catalog would go holds a catalog already: it is not overwritten unless asked to."""

    def __init__(self) -> None:
        super().__init__("catalog_storage", "Where the catalog would go already holds one: replace it, or choose another place.")


def copy_catalog(source: CatalogRepository, target: CatalogRepository, *, replace: bool = False) -> CopiedCatalog:
    """Copies the people and the research projects of `source` to `target`, as they are kept, and reads them back. TargetNotEmpty: `target` has
    records and `replace` is off (with it, the people are replaced, and the research projects of `source` replace those with their acronym);
    CatalogError: what was copied does not read back as it was."""
    trappers, projects = source.read_trappers(), source.read_projects()
    if not replace and (target.read_trappers() or target.read_projects()):
        raise TargetNotEmpty()
    target.write_trappers(trappers)
    for project in projects:
        if target.read_project(project.acronym) is not None:
            target.save_project(project)
        else:
            target.add_project(project)
    if target.read_trappers() != trappers or any(target.read_project(p.acronym) != p for p in projects):
        raise CatalogError("catalog_storage", "What was copied does not read back as it was: the catalog stays where it was.")
    return CopiedCatalog(trappers=len(trappers), projects=len(projects))
