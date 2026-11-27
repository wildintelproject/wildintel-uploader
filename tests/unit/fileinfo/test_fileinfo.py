"""#248: what is known of the files (modules.fileinfo) — found out once while the file is the same, remembered in memory and on disk: the metadata,
whether an image decodes, the hashes."""
from pathlib import Path

from PIL import Image

from wildintel_uploader.entrypoints import wiring
from wildintel_uploader.modules.fileinfo.application.use_cases import FileInfoUseCases
from wildintel_uploader.modules.fileinfo.domain.models import CameraInfo, camera_of, date_of
from wildintel_uploader.modules.fileinfo.infrastructure import memory, store
from wildintel_uploader.modules.fileinfo.infrastructure.files import FileHasher, OsStamps
from wildintel_uploader.modules.fileinfo.infrastructure.memory import ProcessMemory
from wildintel_uploader.modules.fileinfo.infrastructure.pillow import PillowDecoder, PillowReader
from wildintel_uploader.modules.fileinfo.infrastructure.store import SqliteStore


class Counting:
    def __init__(self, inner) -> None:
        self.inner, self.calls = inner, 0

    def decode_error(self, path):
        self.calls += 1
        return self.inner.decode_error(path)

    def hash(self, path, algorithm):
        self.calls += 1
        return self.inner.hash(path, algorithm)


class NoExifTool:
    def available(self):
        return False

    def read(self, paths, tags):
        raise AssertionError("not available")


def _service(decoder, hasher) -> FileInfoUseCases:
    return FileInfoUseCases(reader=NoExifTool(), fallback=PillowReader(), decoder=decoder, hasher=hasher, stamps=OsStamps(), memory=ProcessMemory(),
                            store=SqliteStore())


def test_the_tags_of_an_image_say_its_camera_and_its_date():
    tags = {"make": "RECONYX", "model": "RECONYX HC600", "internalserialnumber": "S1", "datetimeoriginal": None, "createdate": "2024:09:04 10:00:00"}
    assert camera_of(tags) == CameraInfo(model="RECONYX HC600", camera_id="S1")
    assert date_of(tags).isoformat() == "2024-09-04T10:00:00"
    assert date_of({"datetimeoriginal": "0000:00:00 00:00:00"}) is None


def test_whether_an_image_decodes_is_found_out_once_and_kept_for_after_a_restart(tmp_path: Path):
    good, bad = tmp_path / "good.jpg", tmp_path / "bad.jpg"
    Image.new("RGB", (8, 8)).save(good)
    bad.write_bytes(b"\xff\xd8 not an image")
    decoder = Counting(PillowDecoder())
    service = _service(decoder, Counting(FileHasher()))

    assert service.decode_error(good) is None and service.decode_error(bad)
    service.decode_error(good)
    assert decoder.calls == 2                         # the good one once; the bad one is looked at again next time
    memory.forget_all()                               # the app restarted
    service.decode_error(good)
    assert decoder.calls == 2

    Image.new("RGB", (9, 9)).save(good)               # another file: looked at again
    service.decode_error(good)
    assert decoder.calls == 3


def test_a_hash_is_found_out_once_while_the_file_is_the_same(tmp_path: Path):
    path = tmp_path / "a.jpg"
    path.write_bytes(b"one")
    hasher = Counting(FileHasher())
    service = _service(Counting(PillowDecoder()), hasher)

    first = service.hash(path, "sha256")
    assert service.hash(path, "sha256") == first and hasher.calls == 1
    memory.forget_all()
    assert service.hash(path, "sha256") == first and hasher.calls == 1 and store.path().is_file()
    assert service.hash(path, "sha1") != first and hasher.calls == 2
    path.write_bytes(b"two!")
    assert service.hash(path, "sha256") != first and hasher.calls == 3
    assert service.hash(tmp_path / "none.jpg", "sha256") is None


def test_forgetting_forgets_in_memory_and_on_disk(tmp_path: Path):
    path = tmp_path / "a.jpg"
    path.write_bytes(b"one")
    hasher = Counting(FileHasher())
    service = _service(Counting(PillowDecoder()), hasher)
    service.hash(path, "sha256")
    service.forget()
    service.hash(path, "sha256")
    assert hasher.calls == 2


def test_the_app_has_one_and_the_container_gives_it():
    from dishka import make_container
    from wildintel_uploader.modules.fileinfo.domain.ports import FileInfoService
    assert wiring.file_info() is wiring.file_info()
    assert make_container(wiring.FileInfoProvider()).get(FileInfoService) is wiring.file_info()
