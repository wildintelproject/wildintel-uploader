"""The catalog (#248) — what the user registers and keeps by hand: the research projects, their locations, cameras and SD cards, the people who go
to the field (trappers) and their roles, and the history of the states of the locations, cameras and SD cards.

The visits, the deployments, the uploaders and the backups are modules of their own, which use the catalog through its contract; the catalog
needs nothing of them but a little of the visits, through the one door they open to it (visits.domain.for_the_catalog).


What it keeps
-------------
- **Research projects** (`ResearchProject`) — named by their acronym, which never changes and names their folder in the collections folder.
  Status: planned → active → finished → archived (archived is for good: nothing of it changes any more).
- **Locations** (`Location`) — where a camera trap is put up, in a research project. Their timezone and whether their cameras ignore summer time
  are fixed when they are made: every instant kept for one was worked out with them (`location_time`). Status: planned, pending, ready, active,
  archived — the visits move them, a person sets only what the visits do not say.
- **Cameras and SD cards** (`Camera`, `SdCard`, "the equipment") — of a research project, by their label (as written: 7b and 7B are two), a
  camera by its serial number too. Status: planned, ready, active (in the field), archived (lost, stolen, broken… for good).
- **The people** (`Trapper`) — kept for all the research projects, by their username; and their **roles** in each project (`Role`).
- **The history** — a line for each change of status of a location, a camera or an SD card: what changed, from what to what, when and why. It
  is written as the changes happen, and can be rebuilt from the visits for what was changed before it was kept.

Every record keeps its id and its dates (`Audit`), and is removed logically: it stays, with the day it was removed.


How it is used
--------------
Its contract is `domain.ports.CatalogService`, in parts — whoever needs only some of it asks for that part:

    CatalogPeople        the people                         trappers, save_trappers, add_trappers
    CatalogProjects      the research projects              projects, project, add_project, update_project, delete_project, require_project
    CatalogLocations     their locations                    locations, location, add_location, update_location, delete_location, location_time
    CatalogEquipment     their cameras and SD cards          equipment, all_equipment, save_equipment, camera, set_camera_identity, add_equipment,
                                                            retire_equipment
    CatalogRoles         the roles of the people             roles, all_roles, add_roles, save_roles
    CatalogHistory       the history of the states           status_history, rebuild_status_history
    CatalogCheckpoints   undoing a save of many writes      checkpoint
    CatalogFieldwork     the field work of the settings page fieldwork, save_fieldwork

From another module, the part it needs is given where the app is put together (entrypoints/wiring), and the module keeps to the domain's models
— so the seal of a deployment (deployments.application.seal) asks only for the equipment:

    class Sealing:
        def __init__(self, ..., catalog_of: Callable[[Path], CatalogEquipment], ...) -> None: ...

        def _camera(self, collections_dir: Path, research_project_id: str, label: str | None) -> dict | None:
            camera = self._catalog_of(collections_dir).camera(research_project_id, label) if label else None   # a Camera, or None
            ...

From a route of the web app or a command of the command line, Dishka gives it — the whole contract, or a part (FromDishka[CatalogLocations]) —,
and the route answers with a schema of the module's api_schemas, never with the model itself (entrypoints/api/catalog.py):

    @router.get("/projects/{project}/locations", response_model=list[GetLocationsItem], response_model_exclude_unset=True)
    def get_locations(project: str, catalog: FromDishka[CatalogService], include_deleted: bool = False) -> list[dict]:
        return [_location(loc) for loc in catalog.locations(project, include_deleted)]

What it refuses is said by the domain: a `CatalogError` naming the field and why (`ProjectExists`, `LocationArchived`, `EquipmentArchived`…),
or a `LookupError` for what is not there (`UnknownProject`, `UnknownLocation`, `UnknownCamera`, `UnknownTrapper`):

    try:
        catalog.add_location("DONA", Location(location_id="DONA_01", timezone="Europe/Madrid", ignore_dst=False, latitude=37.0, longitude=-6.4),
                             by_hand=True)
    except LocationExists:
        ...

A save made of many writes (an import of visits, the settings page) takes a checkpoint first, and puts it back if a later write fails:

    put_back = catalog.checkpoint("DONA")
    try:
        ...   # the writes
    except Exception:
        put_back()
        raise

From the outside: the web API (`/api/catalog/…`, and `/api/setup/…`, `/api/deployment-import/…` for the pages that use it) and the command line
(`wucli catalog trappers|projects|locations list|add|set-status|delete`, `wucli catalog where`, `wucli catalog migrate`).


How it is made
--------------
- `domain/` — plain Python: the models and their rules (`models`, `rules`), the history (`history`), the contract and the ports (`ports`), and
  what a backup copies (`records.CatalogRecordStore`).
- `application/` — `CatalogUseCases`, the contract over the ports; and the move of the catalog from one place to another (`migration`).
- `infrastructure/` — where it is kept: the JSON files of the collections folder (`json_repository`) or a database (`sql_repository`, SQLite by
  default, with the versions of its tables in `sql_migrations`), chosen by the setting DATA.catalog_storage; the folders of the research
  projects (`project_folders`); the history as it is written (`status_history`); the visits as the catalog reads them (`visits`); what versions
  before left in the settings (`legacy`); the records as a backup copies them (`records`); and its web API (`api_schemas`).

To move the catalog from the files to a database or back: `wucli catalog migrate` — everything copied as it is kept, ids and dates too, and read
back to see it is the same."""
