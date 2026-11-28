# reports — what each check, import and upload did

The report of each validation, postvalidation, preprocessing, import of visits, upload and repair, kept as files in the reports folder of the
settings: to be read, downloaded (as HTML or JSON) and removed.

## Its contract

| Contract | What it is | Operations |
|---|---|---|
| `ReportsService` |  | `list`, `read`, `as_file`, `image`, `delete`, `delete_older_than`, `save_validation`, `save_postvalidation`, `save_preprocessing`, `save_visits_import`, `save_upload`, `save_repair` |

## How it is used

The other modules save theirs through the contract; the web app (`/api/reports/…`) lists, reads and removes them:

```python
report_id = reports.save_validation(result, folder, checks)
reports.list()                      # the newest first
reports.as_file(report_id, "html")  # to download
```

## What it refuses

`ReportMissing` — a report, or an image of one, that is not there; `BadFormat` — a format it is not kept in.

## How it is made

- `domain/` — the models and the ports.
- `application/use_cases.py` — the contract over the ports.
- `infrastructure/` — `report_files.py` (the files of the reports, and the images they show), `api_schemas.py`.
