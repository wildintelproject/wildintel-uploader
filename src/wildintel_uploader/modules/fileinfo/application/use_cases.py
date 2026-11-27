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


class FileInfoUseCases(FileInfoService):
    def __init__(self, *, reader: MetadataReader, fallback: FallbackReader, decoder: Decoder, hasher: Hasher, stamps: FileStamps, memory: Memory,
                 store: Store) -> None:
        self._reader, self._fallback, self._decoder, self._hasher = reader, fallback, decoder, hasher
        self._stamps, self._memory, self._store = stamps, memory, store
        # Only one reading runs at a time: one that asks while another is under way — the one started when the folder was scanned — waits for it,
        # and then finds what it read instead of reading the same images again.
        self._reading = threading.Lock()

    # ── the metadata ──

    def tags(self, paths: list[Path], tags: list[str]) -> dict[Path, dict[str, str | None]]:
        if not tags or not paths:
            return {path: {} for path in paths}
        read = self.metadata(paths, tags)
        if read is not None:
            return {path: {tag: read[path].get(tag.lower()) for tag in tags} for path in paths}
        return {path: self._fallback.tags(path, tags) for path in paths}

    def dates(self, paths: list[Path]) -> dict[Path, datetime | None]:
        if not paths:
            return {}
        read = self.metadata(paths, [])
        if read is not None:
            return {p: date_of(read[p]) for p in paths}
        return {p: self._fallback.date(p) for p in paths}

    def cameras(self, paths: list[Path]) -> tuple[dict[Path, CameraInfo], str]:
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
        """What is remembered of these paths with all the tags wanted: in memory, then — unless only the memory — on disk."""
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
        if not paths or not self._reader.available():
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
        if stamp is not None:
            self._memory.put_fact(stamp, kind, value)
            self._store.put_facts({stamp: value}, kind)

    def decode_error(self, path: Path) -> str | None:
        stamp, decoded = self._fact(path, DECODED)
        if decoded:
            return None
        error = self._decoder.decode_error(path)
        if error is None:
            self._remember(stamp, DECODED, "1")
        return error

    def mark_decoded(self, path: Path) -> None:
        self._remember(self._stamps.stamp(path), DECODED, "1")

    def hash(self, path: Path, algorithm: str) -> str | None:
        stamp, digest = self._fact(path, algorithm)
        if digest is None:
            digest = self._hasher.hash(path, algorithm)
            if digest is not None:
                self._remember(stamp, algorithm, digest)
        return digest

    def forget(self) -> None:
        self._memory.clear()
        self._store.clear()
