"""The use cases of what is known of the files: each thing is looked for in memory, then on disk, and only then found out — and remembered in both.
The metadata of the images not remembered are read all at once, in one run of the reader, asking for BASE_TAGS besides the tags asked for, so that
the next steps find them (#140)."""
from __future__ import annotations

import logging
import threading
from datetime import datetime
from pathlib import Path

from wildintel_uploader.modules.fileinfo.domain.models import BASE_TAGS, DECODED, CameraInfo, Stamp, Tags, camera_of, date_of
from wildintel_uploader.modules.fileinfo.domain.ports import (
    Decoder, FallbackReader, FileInfoService, FileStamps, Hasher, Memory, MetadataReader, MetadataReadFailed, Store,
)

logger = logging.getLogger(__name__)
# Whether prefetch reads ahead at all: the tests turn it off (conftest), so that no reading started by one test is still running in the next.
PREFETCH = True


class FileInfoUseCases(FileInfoService):
    """What is known of the files (FileInfoService): looked for in memory, then on disk, and only then found out —
    and remembered in both.

    Only one reading of the metadata runs at a time: one that asks while another is under way (the one started when
    the folder was scanned) waits for it, and then finds what it read.

    Args:
        reader: What reads the metadata of many images at once (ExifTool).
        fallback: What reads an image at a time when there is no reader, or it failed (Pillow).
        decoder: Whether an image decodes.
        hasher: The hash of a file.
        stamps: The stamps of the files, and the files of a folder.
        memory: What is remembered in the process.
        store: What is kept on disk.
    """
    def __init__(self, *, reader: MetadataReader, fallback: FallbackReader, decoder: Decoder, hasher: Hasher, stamps: FileStamps, memory: Memory,
                 store: Store) -> None:
        self._reader, self._fallback, self._decoder, self._hasher = reader, fallback, decoder, hasher
        self._stamps, self._memory, self._store = stamps, memory, store
        # Only one reading runs at a time: one that asks while another is under way — the one started when the folder was scanned — waits for it,
        # and then finds what it read instead of reading the same images again.
        self._reading = threading.Lock()

    # ── the metadata ──

    def is_folder(self, path: Path) -> bool:
        """See FileInfoFiles.is_folder."""
        return self._stamps.is_folder(path)

    def files_in(self, folder: Path) -> list[Path]:
        """See FileInfoFiles.files_in."""
        return self._stamps.files_in(folder)

    def tags(self, paths: list[Path], tags: list[str]) -> dict[Path, dict[str, str | None]]:
        """See FileInfoMetadata.tags: what ``metadata`` gives, by the names asked; with no reader, Pillow's."""
        if not tags or not paths:
            return {path: {} for path in paths}
        read = self.metadata(paths, tags)
        if read is not None:
            return {path: {tag: read[path].get(tag.lower()) for tag in tags} for path in paths}
        return {path: self._fallback.tags(path, tags) for path in paths}

    def dates(self, paths: list[Path]) -> dict[Path, datetime | None]:
        """See FileInfoMetadata.dates: the date of what ``metadata`` gives; with no reader, Pillow's."""
        if not paths:
            return {}
        read = self.metadata(paths, [])
        if read is not None:
            return {p: date_of(read[p]) for p in paths}
        return {p: self._fallback.date(p) for p in paths}

    def cameras(self, paths: list[Path]) -> tuple[dict[Path, CameraInfo], str]:
        """See FileInfoMetadata.cameras: the camera of what ``metadata`` gives; with no reader, Pillow's — remembered
        only in memory, as it says less than ExifTool.
        """
        if not paths:
            return {}, "pillow"
        read = self.metadata(paths, [])
        if read is not None:
            return {p: camera_of(read[p]) for p in paths}, "exiftool"
        found: dict[Path, CameraInfo] = {}
        for path in paths:   # what Pillow read is remembered too, but only in memory: it says less than ExifTool
            stamp = self._stamps.stamp(path)
            camera = self._memory.get_camera(stamp)
            if camera is None:
                camera = self._fallback.camera(path)
                self._memory.put_camera(stamp, camera)
            found[path] = camera
        return found, "pillow"

    def metadata(self, paths: list[Path], tags: list[str]) -> dict[Path, Tags] | None:
        """See FileInfoMetadata.metadata: what is remembered first (``_remembered``); the rest, read in one run
        (``_read``), one reading at a time — what another reading left meanwhile is taken before reading.
        """
        if not self._reader.available():
            return None
        wanted = {t.lower() for t in tags}
        stamps = {path: self._stamps.stamp(path) for path in paths}
        found = self._remembered(paths, stamps, wanted)
        if len(found) == len(paths):
            return found
        with self._reading:
            # what another reading left meanwhile is taken first
            found.update(self._remembered([p for p in paths if p not in found], stamps, wanted, memory_only=True))
            missing = [p for p in paths if p not in found]
            if not missing:
                return found
            return self._read(missing, tags, stamps, found)

    def _remembered(self, paths: list[Path], stamps: dict[Path, Stamp | None], wanted: set[str], memory_only: bool = False) -> dict[Path, Tags]:
        """What is remembered of these images with all the tags wanted.

        Args:
            paths: The images.
            stamps: The stamp of each one; one with None has nothing remembered.
            wanted: The tags wanted, in lowercase: an image remembered without one of them is read again.
            memory_only: Whether only the memory is looked in; otherwise, then the disk — what is found there is put
                in memory too.

        Returns:
            The tags of each image remembered with all of them, by their names in lowercase; the others are left out.
        """
        found: dict[Path, Tags] = {}
        for path in paths:
            known = self._memory.get_tags(stamps[path])
            if known is not None and wanted <= known.keys():
                found[path] = known
        if memory_only:
            return found
        kept = self._store.get_tags([s for p in paths if p not in found and (s := stamps[p]) is not None])
        for path in paths:
            known = kept.get(stamps[path]) if path not in found and stamps[path] is not None else None  # type: ignore[arg-type]
            if known is not None and wanted <= known.keys():
                self._memory.put_tags(stamps[path], known)
                found[path] = known
        return found

    def _read(self, missing: list[Path], tags: list[str], stamps: dict[Path, Stamp | None], found: dict[Path, Tags]) -> dict[Path, Tags] | None:
        """Reads the images not remembered, in one run of the reader, and remembers what it read.

        What every reading asks for (BASE_TAGS) is asked besides ``tags``, so that the next steps find it (#140).

        Args:
            missing: The images to read.
            tags: The tags wanted, by their ExifTool names.
            stamps: The stamp of each image: one with None is read, but not remembered.
            found: What is remembered of the others; the images read are added to it.

        Returns:
            ``found``, with the tags of the images read by their names in lowercase, merged with what was remembered
            of them; an image the reader could not read has every tag asked as None, and is not remembered. None when
            the reader failed as a whole: then the readings go to the fallback.
        """
        ask = list({t.lower(): t for t in (*BASE_TAGS, *tags)}.values())
        try:
            read = self._reader.read(missing, ask)
        except MetadataReadFailed as exc:
            logger.warning("ExifTool failed (%s) — falling back to Pillow.", exc)
            return None
        fresh: dict[Stamp, Tags] = {}
        for path in missing:
            if path not in read:   # it could not be read: it has none of them, and it is looked at again next time
                found[path] = dict.fromkeys((t.lower() for t in ask), None)
                continue
            stamp = stamps[path]
            values = {**(self._memory.get_tags(stamp) or {}), **{t.lower(): v for t, v in read[path].items()}}
            found[path] = values
            if stamp is not None:
                self._memory.put_tags(stamp, values)
                fresh[stamp] = values
        self._store.put_tags(fresh)
        return found

    def prefetch(self, paths: list[Path], tags: list[str] | None = None) -> threading.Thread | None:
        """See FileInfoMetadata.prefetch: ``metadata`` in a thread of its own, that does not keep the app open."""
        if not PREFETCH or not paths or not self._reader.available():
            return None

        def run() -> None:
            try:
                self.metadata(paths, list(tags or []))
            except Exception as exc:  # noqa: BLE001 — a reading ahead that fails only means the steps read the images themselves
                logger.debug("Reading the EXIF ahead failed: %s", exc)
        thread = threading.Thread(target=run, name="exif-prefetch", daemon=True)
        thread.start()
        return thread

    # ── what else is known of a file ──

    def _fact(self, path: Path, kind: str) -> tuple[Stamp | None, str | None]:
        """Something else remembered of a file: in memory, else on disk (then put in memory too).

        Args:
            path: The file.
            kind: What: ``"decoded"``, ``"sha1"``, ``"sha256"``…

        Returns:
            ``(stamp, value)``: the stamp of the file — to remember what is found out — and the value remembered;
            ``(None, None)`` for a file that cannot be looked at, and None for the value when it is not remembered.
        """
        stamp = self._stamps.stamp(path)
        if stamp is None:
            return None, None
        value = self._memory.get_fact(stamp, kind)
        if value is None:
            value = self._store.get_facts([stamp], kind).get(stamp)
            if value is not None:
                self._memory.put_fact(stamp, kind, value)
        return stamp, value

    def _remember(self, stamp: Stamp | None, kind: str, value: str) -> None:
        """Remembers something else of a file, in memory and on disk.

        Args:
            stamp: The stamp of the file; None remembers nothing.
            kind: What: ``"decoded"``, ``"sha1"``, ``"sha256"``…
            value: Its value.
        """
        if stamp is not None:
            self._memory.put_fact(stamp, kind, value)
            self._store.put_facts({stamp: value}, kind)

    def decode_error(self, path: Path) -> str | None:
        """See FileInfoContent.decode_error: what is remembered first; an image that decodes is remembered."""
        stamp, decoded = self._fact(path, DECODED)
        if decoded:
            return None
        error = self._decoder.decode_error(path)
        if error is None:
            self._remember(stamp, DECODED, "1")
        return error

    def mark_decoded(self, path: Path) -> None:
        """See FileInfoContent.mark_decoded: remembered in memory and on disk."""
        self._remember(self._stamps.stamp(path), DECODED, "1")

    def size(self, path: Path) -> int | None:
        """See FileInfoContent.size: the size its stamp says."""
        stamp = self._stamps.stamp(path)
        return stamp[1] if stamp is not None else None

    def hash(self, path: Path, algorithm: str) -> str | None:
        """See FileInfoContent.hash: what is remembered first; a hash found out is remembered."""
        stamp, digest = self._fact(path, algorithm)
        if digest is None:
            digest = self._hasher.hash(path, algorithm)
            if digest is not None:
                self._remember(stamp, algorithm, digest)
        return digest

    def exiftool_path(self) -> str | None:
        """See FileInfoMetadata.exiftool_path: where the reader is."""
        return self._reader.location()

    def forget(self) -> None:
        """See FileInfoCache.forget: the memory and the store, cleared."""
        self._memory.clear()
        self._store.clear()
