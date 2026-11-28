# fileinfo — what is known of the files of the images

What their metadata say (read with ExifTool — the camera, the capture date, any field — or Pillow when there is no ExifTool), whether they
decode, their hashes and sizes: each found out once while the file is the same, and remembered — in memory, and on disk (a SQLite database in the
cache folder of the system), so that a restart does not read them again (#140). The validations, the preprocessing, the seal and the reports ask it.

## Its contract

| Contract | What it is | Operations |
|---|---|---|
| `FileInfoMetadata` | What the metadata of the images say — read with ExifTool, or Pillow when there is none —, and reading them ahead | `tags`, `dates`, `cameras`, `metadata`, `prefetch`, `exiftool_path` |
| `FileInfoContent` | What the content of a file is: whether an image decodes, its hash, its size | `decode_error`, `mark_decoded`, `hash`, `size` |
| `FileInfoFiles` | The files of a folder, as what is known of them is asked for | `is_folder`, `files_in` |
| `FileInfoCache` | What is remembered of the files | `forget` |
| `FileInfoService` | All of them: what the module offers | — |

## How it remembers

What is found out of a file is kept by its **stamp** — its path, its size, when its content was last modified and when the file last changed
(ctime), in nanoseconds —, and only while the file is the same: a file written again, or replaced by another even of the same size with its
modification time kept (`cp -p`, `rsync -a`), has another stamp, and is read again.

It is kept at two levels:

| Level | Where | What | How much |
|---|---|---|---|
| Memory of the process (`ProcessMemory`) | One for the whole app, shared by every check and step | Everything: the tags read, the camera and date of each image, whether it decodes, its hashes | Up to 50,000 of each kind; the least used is forgotten first |
| Disk (`SqliteStore`) | `exif.sqlite3` in the cache folder of the system (`~/.cache/wildintel-uploader` on Linux; the one of the system on macOS and Windows) | What ExifTool read, whether each image decodes, and its hashes — so a restart does not read them again | Up to 300,000 files of each kind; the oldest written is forgotten first |

What Pillow reads (when there is no ExifTool) stays in memory only: it is less than ExifTool reads, and the image is read again with ExifTool once
it is installed. The disk is a help, never a need: if the cache cannot be read or written, it is said in the log (debug) and the app goes on with
the memory only. A cache written by a version whose stamps had no ctime is let go, and filled again as the images are read. `forget()` forgets
both.

## How it is used

```python
info: FileInfoService
dates = info.dates(images)                       # {path: datetime | None} — the capture date of each
cameras, reader = info.cameras(images)           # the camera of each, and what read them: "exiftool" or "pillow"
digest = info.hash(path, "sha1")                 # remembered while the file is the same
```

Each part of the contract is asked for by who needs it: the deployments and the page that says whether ExifTool is there ask only
`FileInfoMetadata`.

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
