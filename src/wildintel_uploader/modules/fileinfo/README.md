# fileinfo — what is known of the files of the images

What their metadata say (read with ExifTool — the camera, the capture date, any field — or Pillow when there is no ExifTool), whether they
decode, their hashes and sizes: each found out once while the file is the same, and remembered — in memory, and on disk (a SQLite database in the
cache folder of the system), so that a restart does not read them again (#140). The validations, the preprocessing, the seal and the reports ask it.

## Its contract

| Contract | What it is | Operations |
|---|---|---|
| `FileInfoService` | What is known of the files of images, each thing found out once while the file is the same | `tags`, `dates`, `cameras`, `metadata`, `decode_error`, `mark_decoded`, `hash`, `size`, `prefetch`, `exiftool_path`, `forget`, `is_folder`, `files_in` |

A file is the same while its **stamp** is: its path, its size and when it was last modified (in nanoseconds).

## How it is used

```python
info: FileInfoService
dates = info.dates(images)                       # {path: datetime | None} — the capture date of each
cameras, reader = info.cameras(images)           # the camera of each, and what read them: "exiftool" or "pillow"
digest = info.hash(path, "sha1")                 # remembered while the file is the same
```

The checks of a folder go through **`MediaFolder`** (`domain/folder.py`), which asks each thing once for every check that asks it — the
cameras, the dates, which images decode, the hashes, the sizes — and gives it again to the next:

```python
folder = MediaFolder(root, info, pmap)
folder.dates()      # read once, for every check of the folder
```

`prefetch(paths)` starts reading in the background what the steps of an import will ask, so that it is there when they ask.

## What it refuses

Nothing: what cannot be read is said as `None` (a date, a hash) or as the error of a file (`decode_error`). `MetadataReadFailed` is the
reader's own, and never leaves the module.

## How it is made

- `domain/` — the models (`CameraInfo`, the stamp of a file), the ports, and `MediaFolder`.
- `application/use_cases.py` — the contract over its ports: what is in memory first, then on disk, then read.
- `infrastructure/` — `exiftool.py` and `pillow.py` (the readers), `files.py` (the stamps, the hashes, the files of a folder), `memory.py` and
  `store.py` (what is remembered).
