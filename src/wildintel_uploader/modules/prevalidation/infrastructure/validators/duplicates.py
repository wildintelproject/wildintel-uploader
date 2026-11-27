"""Files with exactly the same content, and images imported before into the research project."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from wildintel_uploader.modules.prevalidation.domain.models import ImageOptions
from wildintel_uploader.modules.prevalidation.domain.validators import ImageValidator
from wildintel_uploader.modules.fileinfo.domain.folder import MediaFolder

class Duplicates(ImageValidator):
    key = "duplicates"
    label = "Duplicates"
    description = ("Groups of two or more files with exactly the same content — only files of the same size are compared —; and, with what the "
                   "research project already has, the images imported before into another deployment of it.")

    def run(self, folder: MediaFolder, options: ImageOptions) -> dict:
        result: dict = {"duplicates": self._groups(folder)}
        if options.imported is not None:
            result["duplicates_in_project"] = self._imported_before(folder, options.imported)
        return result

    @staticmethod
    def _groups(folder: MediaFolder) -> list[dict]:
        by_size: dict[int, list[Path]] = defaultdict(list)
        for path in sorted(folder.images):
            try:
                by_size[path.stat().st_size].append(path)
            except OSError:
                continue
        candidates = {size: paths for size, paths in by_size.items() if len(paths) > 1}
        hashes = folder.hashes([p for paths in candidates.values() for p in paths], "sha256")
        groups: list[dict] = []
        for size, paths in candidates.items():
            by_hash: dict[str, list[Path]] = defaultdict(list)
            for path in paths:
                if (digest := hashes[path]) is not None:
                    by_hash[digest].append(path)
            groups += [{"size": size, "files": [folder.relative(p) for p in same]} for same in by_hash.values() if len(same) > 1]
        return sorted(groups, key=lambda g: g["files"][0])

    @staticmethod
    def _imported_before(folder: MediaFolder, imported: dict[str, list[dict]]) -> list[dict]:
        """By the SHA-1 of the file, as the preprocessing kept it: {"file", "deployment_id", "collection", "original"}."""
        if not imported:
            return []
        ordered = sorted(folder.images)
        hashes = folder.hashes(ordered, "sha1")
        return [{"file": folder.relative(path), **before} for path in ordered for before in imported.get(hashes[path] or "", [])]
