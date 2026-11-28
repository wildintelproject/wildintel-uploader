# postvalidation — the checks of a deployment

The checks of a deployment as it is imported — what the wizard knows of it — against the names of wildintel-tools (its id, its collection and
its prefix), its images (their dates within the period of the visits, their camera as the catalog records it) and the visit it is of (its SD
card, how many photos); and the statistical ones, which compare it with the revisions before of its location. Each check is a class of
`domain/checks/` — plain Python over the images (`MediaFolder`) and the context (`DeploymentContext`).

## Its contract

| Contract | What it is | Operations |
|---|---|---|
| `PostvalidationService` |  | `validators`, `validate`, `check_deployment` |

## How it is used

```python
context = DeploymentContext(deployment=record, collection="R0001", expected_location_id="DONA_01", visit=visit, research_project_id="DONA")
result = postvalidation.check_deployment(folder, context, on_check=tell)
```

The web app (`/api/deployment-import/validate-deployment`) runs it in the wizard; the report is kept (modules.reports). How a camera is told —
by its serial number, by its make and model, by its model — is said by the settings, from the surest to the least
(`domain/checks/camera_of_the_deployment.py` explains it with examples).

## Its settings

`POSTVALIDATION` in `settings.toml`: which checks are on, the leeway of the dates (`tolerance_hours`), what a sequence and a similar revision are
for the statistical checks, and how each check starts (`defaults`).

What a sequence and a similar revision are reach the checks as `StatisticsParameters` (`domain/models.py`), in the context — the gap of a
sequence, the revisions before to judge by, the method and the tolerance of each check —, with the defaults of the settings.

## What it refuses

`PostvalidationError` — a deployment that cannot be checked.

## How it is made

- `domain/` — the models (`DeploymentContext`), the settings, the statistics of a deployment's times (`statistics.py`, which the deployments
  use too), the ports, the base of a check and the checks (`checks/`).
- `application/use_cases.py` — the checks it is given, in their order, with the camera of the catalog and the revisions before.
- `infrastructure/` — `adapters.py`, `settings.py`, `api_schemas.py`.
