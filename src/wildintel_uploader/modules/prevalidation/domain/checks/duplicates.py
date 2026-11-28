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
        """The duplicates of the folder, and — when what the research project has is given — the images imported before.
    def _imported_before(folder: MediaFolder, imported: dict[str, list[dict]]) -> list[dict]:

        Args:
            folder: The folder whose images are checked.
            options: What the caller says of the checks; only ``imported`` is read here: the images the research
                project already has, by the SHA-1 of their originals. None leaves that part of the check out.

        Returns:
            ``{"duplicates": [...]}`` — the groups of files with the same content (see ``_groups``) —, and, when
            ``options.imported`` is not None, ``"duplicates_in_project": [...]`` too — the images imported before
            (see ``_imported_before``).

        Example:
            A folder with two copies of one picture, one of them imported before into R0012-DONA_01::

                {
                    "duplicates": [{"size": 1874512, "files": ["IMG_0001.JPG", "IMG_0007.JPG"]}],
                    "duplicates_in_project": [
                        {"file": "IMG_0001.JPG", "deployment_id": "R0012-DONA_01", "collection": "R0012",
                         "original": "100RECNX/IMG_0412.JPG"},
                        {"file": "IMG_0007.JPG", "deployment_id": "R0012-DONA_01", "collection": "R0012",
                         "original": "100RECNX/IMG_0412.JPG"},
                    ],
                }
        """
        result: dict = {"duplicates": self._groups(folder)}
        if options.imported is not None:
            result["duplicates_in_project"] = self._imported_before(folder, options.imported)
        return result

    @staticmethod
    def _groups(folder: MediaFolder) -> list[dict]:
        """The files of the folder with exactly the same content.

        Only the files of a size that more than one has are hashed (SHA-256) — two of different sizes cannot be the
        same —; one whose size or hash cannot be read is in no group.

        Args:
            folder: The folder whose images are compared; its sizes and hashes come from the file cache.

        Returns:
            A dict for each group of two or more files with the same content, sorted by their first file:
            ``{"size": int, "files": list[str]}`` — the size in bytes they share and their paths relative to the
            folder, in order. An empty list when there is no duplicate.

        Example:
            A folder where IMG_0001.JPG and IMG_0007.JPG are the same picture, and DCIM/IMG_0003.JPG, IMG_0004.JPG
            and IMG_0009.JPG are another one copied twice::

                [
                    {"size": 2345678, "files": ["DCIM/IMG_0003.JPG", "IMG_0004.JPG", "IMG_0009.JPG"]},
                    {"size": 1874512, "files": ["IMG_0001.JPG", "IMG_0007.JPG"]},
                ]
        """
        by_size: dict[int, list[Path]] = defaultdict(list)
        sizes = folder.sizes(sorted(folder.images))
        for path, size in sizes.items():
            if size is not None:
                by_size[size].append(path)
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
        """The images of the folder imported before into the research project.

        An image is matched by the SHA-1 of its content, as the preprocessing of each deployment kept it for the
        originals it imported (``source_hash`` in its preprocessing.json); one whose hash cannot be read matches
        none. No hash is computed when the research project has nothing imported.

        Args:
            folder: The folder whose images are checked.
            imported: What the research project already has: for each SHA-1, where an original with it was
                imported — ``{"deployment_id", "collection", "original"}``, one for each deployment that has it.

        Returns:
            A dict for each image and each deployment it was imported into, in the order of the files:
            ``{"file": str, "deployment_id": str, "collection": str, "original": str}`` — its path relative to the
            folder, the deployment and the collection it is in, and the path it had in the folder it was imported
            from. An image imported into two deployments is in two. An empty list when none was imported before.

        Example:
            IMG_0001.JPG was imported into R0012-DONA_01 and into R0013-DONA_01; the other images of the folder
            never were::

                [
                    {"file": "IMG_0001.JPG", "deployment_id": "R0012-DONA_01", "collection": "R0012",
                     "original": "100RECNX/IMG_0412.JPG"},
                    {"file": "IMG_0001.JPG", "deployment_id": "R0013-DONA_01", "collection": "R0013",
                     "original": "IMG_0412.JPG"},
                ]
        """
        if not imported:
            return []
        ordered = sorted(folder.images)
        hashes = folder.hashes(ordered, "sha1")
        return [{"file": folder.relative(path), **before} for path in ordered for before in imported.get(hashes[path] or "", [])]
