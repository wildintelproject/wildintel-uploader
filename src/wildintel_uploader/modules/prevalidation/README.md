# prevalidation — the checks of the images of a folder

Before a folder of images is imported, its images are checked: corrupted ones, the order of the shots, the structure of the folder, one camera,
the EXIF fields the settings ask for, duplicates (in the folder, and with the images imported before into the research project). Each check is a
class of `domain/checks/` — plain Python over what is known of the images (`MediaFolder`, from modules.fileinfo).

## Its contract

| Contract | What it is | Operations |
|---|---|---|
| `PrevalidationService` |  | `validators`, `validate`, `check_folder` |

## How it is used

```python
result = prevalidation.check_folder(folder, frozenset({"corrupted", "sequence"}), research_project_id="DONA", on_check=tell)
```

The web app (`/api/deployment-import/validate-images`) runs them as a deployment is imported; each check says what it found, and the report is kept
(modules.reports).

How each check starts in an import — `required` (it has to pass), `warn`, or `skip` (offered unticked) — is a setting.

## Its settings

`VALIDATION` in `settings.toml`: which checks are on, the EXIF fields asked for, how a camera is told (`camera_levels`), and how each starts
(`defaults`). Their rules are in `domain/settings.py`; their format in the file in `infrastructure/settings.py`.

## Adding a check

A file `domain/checks/x.py` with a class `X(ImageValidator)` — its `key`, `label`, `description` and `run(folder, options) -> dict` —, a line
in the registry of `domain/checks/__init__.py` (the order they run in), and a test. See the developer manual.

## What it refuses

`PrevalidationError` — a folder that cannot be checked.

## How it is made

- `domain/` — the models, the settings, the ports, the base of a check (`validators.py`) and the checks (`checks/`).
- `application/use_cases.py` — running the checks it is given, in their order, over a `MediaFolder`.
- `infrastructure/` — `adapters.py` (the images imported before, the report), `settings.py`, `api_schemas.py`.
