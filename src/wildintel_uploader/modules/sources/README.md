# sources — where the visits come from

The entries of the Epicollect5 project of the field work, read through its API, or the CSV downloaded from it — as rows with the columns a visit
has, for the module of the visits to read as any other file of visits —; and the entries of an Epicollect5 project that say the details of a
deployment.

## Its contract

| Contract | What it is | Operations |
|---|---|---|
| `SourcesVisits` | Where the visits come from: the sources there are, the visits of one, and whether a CSV is the download of the form of a visit | `sources`, `visits`, `form_columns`, `form_error` |
| `SourcesDeployments` | The entries of the Epicollect5 project that say the details of a deployment | `deployment_entries`, `location_entries` |
| `SourcesProject` | The Epicollect5 project of the settings: its form, whether it can be read, and forgetting the tokens of its API | `project_form`, `test_connection`, `forget_tokens` |
| `SourcesService` | All of them: what the module offers | — |

## How it is used

```python
rows = sources.visits("epicollect-api")        # VisitRows: the CSV of the visits, its columns, and where the time of each comes from
                                               #   (None: the settings choose — FIELDLOG.time_source)
csv = sources.visits("epicollect-csv", text)   # the CSV downloaded from the project, as the same rows
form = sources.project_form()                  # the questions of the form of the project of the settings
```

The module of the visits asks only for `SourcesVisits`; the routes of the Epicollect5 project and of the details of a deployment, for
`SourcesProject` and `SourcesDeployments`. Each source is a class of `infrastructure/sources/` (`epicollect_api.py`, `epicollect_csv.py`) with its `key` and `label`; the visits
(modules.visits) ask them by key. The web app has `/api/epicollect/…`.

## Its settings

`EPICOLLECT5` (the project: its slug, and the client of its API for a private one — its secret kept as a `Secret`) and `EPICOLLECTCSV`.

## What it refuses

`SourceError` — the message says why (no project saved, the form is not the one of a visit…); `Unreachable` — Epicollect5 cannot be reached.

## How it is made

- `domain/` — the models (how a form and its entries are read), the settings, the ports.
- `application/use_cases.py` — the contract over the sources it is given.
- `infrastructure/` — the sources (`sources/`), the API of Epicollect5 (`epicollect5.py`, with its tokens), the settings in use, `api_schemas.py`.
