# preprocessing — the images of a deployment as they are imported

What `prepare_collections_for_trapper` of wildintel-tools did, and a bit more: the date of each image in UTC, its new name, resized, its hashes,
the XMP of its authorship and license. Prepared in the `.staging` folder of the collection and, once saved, moved to its place and sealed.

## Its contract

| Contract | What it is | Operations |
|---|---|---|
| `PreprocessingService` |  | `preprocess`, `consolidate` |

## How it is used

The deployments (modules.deployments) ask it, as they import a folder:

```python
for event in preprocessing.preprocess(source, collection_dir, "R0001", deployment, options):
    ...           # {"type": "image", …}, {"type": "sealing"}, {"type": "done", …}
```

`consolidate` moves to its place a deployment prepared before. Moving it is one rename; if its metadata or its seal cannot be written
after it, it goes back to its staging folder — a deployment is never left in the collection unsealed —, and consolidating it again finishes it. Each step is a class:

- **image steps** — `CaptureDate`, `Rename`, `ResizeOrCopy`, `Hashes`, `CameraOfTheImage` — run for each image;
- **folder steps** — `XmpMetadata`, `FinalHashes` — run once all of them are done.

They read and write the images (Pillow, ExifTool, the disk), so they are adapters (`infrastructure/steps/`); the rules they apply — the name of
an image, its date in UTC — are of the domain (`domain/models.py`).

## Its settings

`PREPROCESSING` in `settings.toml`: whether to rename, the width to resize to, the authorship and license of the XMP.

## What it refuses

`PreprocessingError` — a folder or a collection that cannot be prepared.

## How it is made

- `domain/` — the models and their rules, the settings, the ports, and what a step is (`steps.py`: `ImageStep`, `FolderStep`, `Job`).
- `application/use_cases.py` — the steps it is given, in their order.
- `infrastructure/` — the steps (`steps/`), the images (`images.py`), the folders and the seal (`folders.py`), `settings.py`.
