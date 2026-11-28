# uploaders — sending the deployments where they are published

Sending the deployments kept to where they are published — TRAPPER for now —, bringing back what is there (sync), and the account to do it with.

## Its contract

| Contract | What it is | Operations |
|---|---|---|
| `UploadersService` |  | `account_defaults`, `test_connection`, `research_projects`, `classification_projects`, `locations`, `deployments`, `import_deployment`, `collections`, `project_classification_projects`, `check_selection`, `check_access`, `upload`, `upload_report`, `trapper_state`, `uploads_of`, `upload_states`, `collection_names`, `sync` |

## How it is used

```python
uploaders.test_connection(Account(url, username, password))   # once it works, the account is kept in the settings
for event in uploaders.upload(account, "DONA", "R0001", "R0001-DONA_01", mode="new", classification_project_pk=None, delete_files=False):
    ...
```

A deployment is checked before it is sent (`check_selection`, `check_access`), packed in parts of at most `TRAPPER.max_zip_mb`, and an upload
that fails is planned again until it is done. The web app has `/api/trapper/…`, `/api/upload/…`, `/api/sync/…`; the command line,
`wucli trapper …` and `wucli import-deployment`.

## Its settings

`TRAPPER` (where, and the account — its password kept as a `Secret`, never shown) and `AGOUTI`.

## What it refuses

`UploaderError` and what TRAPPER answers, each with its message: `NotAuthorized`, `Forbidden`, `NotThere`, `Unreachable`, `TimedOut`.

## How it is made

- `domain/` — the models, the rules of a sync and of the uploads, the settings, the ports.
- `application/use_cases.py` and `sync.py` — the contract over the ports.
- `infrastructure/` — TRAPPER (`trapper.py`, `trapper_site.py`), the packages (`packages.py`), the uploads and their failures (`uploads.py`,
  `failures.py`), what a sync writes (`synced_folder.py`), `settings.py`, `api_schemas.py`.
