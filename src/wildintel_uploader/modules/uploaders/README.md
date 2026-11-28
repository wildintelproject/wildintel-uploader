# uploaders — sending the deployments where they are published

Sending the deployments kept to where they are published — TRAPPER for now —, bringing back what is there (sync), and the account to do it with.

## Its contract

| Contract | What it is | Operations |
|---|---|---|
| `UploadersAccount` | The account of TRAPPER: what the settings keep of it, and whether it works | `account_defaults`, `test_connection` |
| `UploadersTrapper` | What TRAPPER has: its research projects, classification projects, locations and deployments | `research_projects`, `classification_projects`, `locations`, `deployments`, `project_classification_projects` |
| `UploadersImport` | A deployment brought from the wizard into TRAPPER, its images in the timezone of its location | `import_deployment` |
| `UploadersUpload` | Uploading the deployments kept: the collections to choose from, what TRAPPER says of the choice, the upload and its report | `collections`, `check_selection`, `check_access`, `upload`, `upload_report` |
| `UploadersState` | Where each deployment kept was uploaded: to TRAPPER, to each uploader in use | `trapper_state`, `uploads_of`, `upload_states` |
| `UploadersSync` | Bringing back what TRAPPER has into the collections folder | `collection_names`, `sync` |
| `UploadersService` | All of them: what the module offers | — |

## How it is used

```python
uploaders.test_connection(Account(url, username, password))   # once it works, the account is kept in the settings
for event in uploaders.upload(account, "DONA", "R0001", "R0001-DONA_01", mode="new", classification_project_pk=None, delete_files=False):
    ...
```

Each route and command asks for the part it uses — the page of the account `UploadersAccount`, the upload `UploadersUpload`, the sync
`UploadersSync`…; the command that imports a deployment, which lists what TRAPPER has too, the whole contract.

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
