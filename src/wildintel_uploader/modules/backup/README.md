# backup — backups of the settings and of a research project

A backup is a `.zip` with the settings and the data of a research project — its records (the project, its locations, cameras, SD cards, roles and
the history of their states), its visits, and the deployments chosen, with or without their images —, written whole or not at all. It is read
back to see what it holds and what of it is already here, and restored.

## Its contract

| Contract | What it is | Operations |
|---|---|---|
| `BackupService` |  | `describe`, `create`, `download`, `read`, `restore` |

## How it is used

The web app (`/api/backup/…`) streams what a backup and a restoration do, as events — `{"type": "file", "index", "total", "name"}` for each file,
`{"type": "done", …}` at the end:

```python
events = backups.create(dest_dir, "DONA", Choice(settings=True, project_files=True, visits=True, deployments=["R0001-DONA_01"], images=False))
for event in events:            # the first is taken before answering: what can't be done at all is said at once
    ...
```

A restoration (`restore(path, choice, replace)`) adds what is not here, and replaces only when asked — what is archived stays archived. It is
**checked whole before it writes** (what the backup lacks, where each file would go), and **undone if it stops half way**: the records and the
people put back exactly as they were, the files it wrote removed. A file that was there and was replaced is said; restoring again finishes it.

The settings go without the passwords nor the folders of this computer; restoring them keeps those of here.

## What it refuses

`BackupError` — the message says why, for the person (no such backup, it holds no visits, a path that leaves the research project…);
`BackupGone` — a backup to download that is not there any more.

## How it is made

- `domain/` — `archive.py`: the format of a backup and its rules (what a record is keyed by, how one is merged in, what the settings keep).
- `application/use_cases.py` — `BackupUseCases`: making, reading and restoring, over the ports.
- `infrastructure/` — `zip_files.py` (the archives), `folders.py` (the folders of the research projects), `outside.py` (the other modules: the
  catalog through its contract and its records as they are kept — `CatalogRecordStore` —, the visits through theirs, the settings whole),
  `api_schemas.py`.
