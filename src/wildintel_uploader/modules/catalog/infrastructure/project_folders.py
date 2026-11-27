"""The folders of the research projects in the collections folder: <collections folder>/<research project>, where their collections go — apart
from where their records are kept, which may be a database."""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from wildintel_uploader.modules.catalog.domain.ports import ProjectFolders


class ResearchProjectFolders(ProjectFolders):
    """`root` says the collections folder, asked each time."""

    def __init__(self, root: Callable[[], Path]) -> None:
        self._root = root

    def make(self, acronym: str) -> None:
        (self._root() / acronym).mkdir(parents=True, exist_ok=True)

    def held(self, acronym: str, besides: set[str]) -> list[str]:
        folder = self._root() / acronym
        return sorted(e.name for e in folder.iterdir() if e.name not in besides) if folder.is_dir() else []
