# catalog — what the user registers and keeps by hand

The research projects, their locations, cameras and SD cards, the people who go to the field (trappers) and their roles, and the history of the
states of the locations, cameras and SD cards. The visits, the deployments, the uploaders and the backups are modules of their own, which use the
catalog through its contract; the catalog needs nothing of them but a little of the visits, through the one door they open to it
(`visits/domain/for_the_catalog.py`).

## What it keeps

| Record | What it is | Its states |
|---|---|---|
| **Research project** (`ResearchProject`) | Named by its acronym, which never changes and names its folder in the collections folder | planned → active → finished → archived (for good: nothing of it changes any more) |
| **Location** (`Location`) | Where a camera trap is put up. Its timezone and whether its cameras ignore summer time are fixed when it is made: every instant kept for it was worked out with them (`location_time`) | planned, pending, ready, active, archived — the visits move them; a person sets only what the visits do not say |
| **Camera, SD card** (`Camera`, `SdCard`: "the equipment") | Of a research project, by its label (as written: 7b and 7B are two); a camera by its serial number too | planned, ready, active (in the field), archived (lost, stolen, broken… for good) |
| **Person** (`Trapper`) and **role** (`Role`) | The people are kept for all the research projects, by their username; a role is of a person in one project | active, inactive, archived |
| **History** | A line for each change of status of a location, a camera or an SD card: what changed, from what to what, when and why | Written as the changes happen; rebuilt from the visits for what was changed before it was kept |

Every record keeps its id and its dates (`Audit`), and is removed logically: it stays, with the day it was removed.

## Its contract

| Contract | What it is | Operations |
|---|---|---|
| `CatalogPeople` | The people of the field work — kept for all the research projects | `trappers`, `save_trappers`, `add_trappers` |
| `CatalogProjects` | The research projects, and whether one is there to be worked on | `projects`, `project`, `add_project`, `update_project`, `delete_project`, `require_project` |
| `CatalogLocations` | The locations of a research project, and the wall clock of each | `locations`, `location`, `add_location`, `update_location`, `delete_location`, `location_time` |
| `CatalogEquipment` | The cameras and the SD cards of a research project | `equipment`, `all_equipment`, `save_equipment`, `camera`, `set_camera_identity`, `add_equipment`, `retire_equipment` |
| `CatalogRoles` | The roles of the people in a research project | `roles`, `all_roles`, `add_roles`, `save_roles` |
| `CatalogHistory` | The history of the states of the locations, the cameras and the SD cards | `status_history`, `rebuild_status_history` |
| `CatalogCheckpoints` | What a save of many writes puts back when one of them fails | `checkpoint` |
| `CatalogFieldwork` | The field work of the settings page — the people, and the cameras, SD cards and roles of each research project | `fieldwork`, `save_fieldwork` |
| `CatalogService` | All of them: what the module offers | — |

## How it is used

From another module, the part it needs is given where the app is put together (`entrypoints/wiring`), and the module keeps to the domain's
models — so the seal of a deployment (`deployments/application/seal.py`) asks only for the equipment:

```python
class Sealing:
    def __init__(self, ..., catalog_of: Callable[[Path], CatalogEquipment], ...) -> None: ...

    def _camera(self, collections_dir: Path, research_project_id: str, label: str | None) -> dict | None:
        camera = self._catalog_of(collections_dir).camera(research_project_id, label) if label else None   # a Camera, or None
        ...
```

From a route of the web app or a command of the command line, Dishka gives it — the whole contract, or a part (`FromDishka[CatalogLocations]`) —,
and the route answers with a schema of the module's `api_schemas`, never with the model itself (`entrypoints/api/catalog.py`):

```python
@router.get("/projects/{project}/locations", response_model=list[GetLocationsItem], response_model_exclude_unset=True)
def get_locations(project: str, catalog: FromDishka[CatalogService], include_deleted: bool = False) -> list[dict]:
    return [_location(loc) for loc in catalog.locations(project, include_deleted)]
```

A save made of many writes (an import of visits, the settings page) takes a checkpoint first, and puts it back if a later write fails:

```python
put_back = catalog.checkpoint("DONA")
try:
    ...   # the writes
except Exception:
    put_back()
    raise
```

From the outside: the web API (`/api/catalog/…`, and `/api/setup/…`, `/api/deployment-import/…` for the pages that use it) and the command line
(`wucli catalog trappers|projects|locations list|add|set-status|delete`, `wucli catalog where`, `wucli catalog migrate`).

## What it refuses

A `CatalogError` naming the field and why (`ProjectExists`, `LocationArchived`, `EquipmentArchived`, `SiteStatusRefused`…), or a
`LookupError` for what is not there (`UnknownProject`, `UnknownLocation`, `UnknownCamera`, `UnknownTrapper`):

```python
try:
    catalog.add_location("DONA", Location(location_id="DONA_01", timezone="Europe/Madrid", ignore_dst=False, latitude=37.0, longitude=-6.4),
                         by_hand=True)
except LocationExists:
    ...
```

## How it is made

- `domain/` — plain Python: the models and their rules (`models.py`, `rules.py`), the history (`history.py`), the contract and the ports
  (`ports.py`), and what a backup copies (`records.py`: `CatalogRecordStore`).
- `application/` — `CatalogUseCases`, the contract over the ports; and the move of the catalog from one place to another (`migration.py`).
- `infrastructure/` — where it is kept: the JSON files of the collections folder (`json_repository.py`) or a database (`sql_repository.py`,
  SQLite by default, with the versions of its tables in `sql_migrations.py`), chosen by the setting `DATA.catalog_storage`; the folders of the
  research projects (`project_folders.py`); the history as it is written (`status_history.py`); the visits as the catalog reads them
  (`visits.py`); what versions before left in the settings (`legacy.py`); the records as a backup copies them (`records.py`); and its web API
  (`api_schemas.py`).

To move the catalog from the files to a database or back: `wucli catalog migrate` — everything copied as it is kept, ids and dates too, and read
back to see it is the same.
