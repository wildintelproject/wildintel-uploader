# deployments — bringing a deployment's images into its collection

A deployment's images brought from a folder or a memory card into the collection of its research project — scanned, their details guessed,
prepared by the preprocessing or copied as they are, and sealed —, and what is known of the deployments kept: where they are, their seal, their
revisions and statistics, their photos; and the sessions of the wizard of an import. A deployment is always of a visit (modules.visits).

## Its contract

| Contract | What it is | Operations |
|---|---|---|
| `DeploymentsCards` | The memory card a deployment's images come from: copied to the computer, ejected, its copy discarded | `copy_card`, `eject_card`, `discard_card_copy` |
| `DeploymentsScanning` | A folder of images, looked at before it is imported: what it holds, the details it suggests, the session it is of | `scan_folder`, `guess_details`, `scan_session` |
| `DeploymentsCollections` | The collections of the collections folder and the deployments kept in them: where one goes, which are there, what each says | `layout`, `check_collection`, `collection_path`, `existing`, `local_deployments`, `imported_images`, `log_entry`, `seal_status`, `previous`, `next_revision`, `previous_revisions` |
| `DeploymentsImporting` | Bringing a deployment into a collection: from a folder of images, consolidated from its staging, or organized for an upload | `import_local`, `consolidate`, `organize` |
| `DeploymentsRepairing` | The deployments kept, checked against their seal and repaired | `repair_collections`, `inspect`, `repair` |
| `DeploymentsStatistics` | The statistics of the deployments of a revision, and two deployments side by side | `revision_statistics`, `compare` |
| `DeploymentsSessions` | The sessions of the wizard of an import | `sessions` |
| `DeploymentsPhotos` | The photos of a deployment kept, to be looked at | `photos`, `photo` |
| `DeploymentsService` | All of them: what the module offers | — |

## How it is used

Each route and command asks for the part it uses:

```python
@router.post("/scan-folder")
def scan_folder(req: ScanFolderRequest, deployments: FromDishka[DeploymentsScanning]) -> …:
    return deployments.scan_folder(Path(req.folder))
```

```python
for event in importing.import_local(source_dir, collection_dir, "R0001", deployment, preprocessing=None):
    ...      # copied as it is when there is no preprocessing; sealed at the end
```

The **seal** (`seal.json`) records, for the deployment and each image, the checks it passed: a deployment kept is valid while its images are what
the seal says (`seal_status`), and can be repaired (`DeploymentsRepairing`). The web app has `/api/deployment-import/…`, `/api/sessions/…`,
`/api/repair/…`, `/api/statistics/…`; the command line, `wucli statistics …`.

## What it refuses

`DeploymentsFailed` (the message says why), `DeploymentMissing`, `CardCopyError`, `RepairError`, `InvalidTaskId`, `PickerUnavailable`, and
`DeploymentsError` for any of them.

## How it is made

- `domain/` — the models, the naming of deployments and collections (`naming.py`), the seal (`seal.py`), imports, repairs, statistics, the ports.
- `application/` — `use_cases.py` (the contract), `imports.py`, `repair.py`, `seal.py`, `sessions.py`, `statistics.py`.
- `infrastructure/` — the memory cards, the collections folder and its layout, the import of a folder, the seal on disk, the repairs, the
  revisions, the photos, the sessions, `api_schemas.py`.
