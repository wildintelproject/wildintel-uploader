# visits — the visits to the camera traps

The visits of a research project: what each did at its site (installed a camera, revised it, took it away, found it stolen…), the rules they
follow, where the cameras and the SD cards are, and the deployments they say — read from a source (modules.sources) or a CSV, or typed by hand,
and kept.

## Its contract

| Contract | What it is | Operations |
|---|---|---|
| `VisitsService` |  | `visits`, `unknown`, `kept_count`, `replace_all`, `save`, `update`, `create_revision`, `mark_not_visited`, `import_file`, `export_file`, `epicollect_download`, `file_columns`, `closed`, `link`, `deployments`, `book`, `has_deployment` |

## How it is used

```python
saved = visits.save("DONA", visit)                        # by hand: checked against the visits before it, and the catalog
result = visits.import_file(ImportOptions(research_project_id="DONA", csv=text, format="mapped", mapping=mapping, save=True))
closed = visits.closed("DONA")                            # the deployments the visits closed, to be imported
```

A save is **all or nothing**: the visit and what it changes in the catalog (the camera and the card it leaves, the site it starts, their states)
are written together, and put back as they were if a later write fails. A file of visits with a row that cannot be added keeps none of them.

The rules a visit keeps to by itself are `domain/integrity.py`; those it keeps with the others, `domain/rules.py`. A visit is told with the names
of what it points to and kept by their ids (`domain/references.py`); its shapes are `TypedDict`s (`domain/shapes.py`). The catalog and the
fixing of times go in through doors of their own (`for_the_catalog.py`, `for_the_timefix.py`).

The web app has `/api/visits/…`.

## Its settings

`FIELDLOG`: where the time of a visit comes from (`time_source`), and whether its seconds are kept.

## What it refuses

`VisitRefused` (a visit the rules do not take — the message says which), `VisitMissing`, `VisitLocked` (it starts or closes a deployment
imported, or the visits are being saved), `VisitsFailed`, `RowError` (a row of a file), and `VisitsError` for any of them.

## How it is made

- `domain/` — the shapes, the rules, the references, the deployments the visits say, the wall clock of a location, the file of visits, the doors.
- `application/` — `use_cases.py` (the contract), `visit_file.py` (reading a file of visits).
- `infrastructure/` — the visits as they are kept (`kept_visits.py`, `adapters.py`), the catalog as the visits see it (`catalog_view.py`), the
  CSV (`csv_file.py`), the format of a visit (`records.py`), `settings.py`, `api_schemas.py`.
