# store/sql

The records as [SQLModel](https://sqlmodel.tiangolo.com/) models: [`models.py`](models.py). It needs `sqlmodel` (not a dependency of the app yet) and uses nothing of SQLite, so it
is as good for PostgreSQL.

    from sqlmodel import SQLModel, create_engine
    import models
    SQLModel.metadata.create_all(create_engine("sqlite:///wildintel.db"))

Checked: it creates its 13 tables on SQLite, and refuses a second visit of a location in a revision, negative photos, a camera with both height and depth, photos on a full card, a
location id repeated in another case, and an archived camera with no reason.

## From the JSON files to the tables

| JSON file | Table | Notes |
|---|---|---|
| `research_project.json` | `research_projects` | `acronym` unique |
| `trappers.json` | `trappers` | `username` unique, whatever its case |
| `roles.json` | `trapper_roles` | unique (project, trapper, role) |
| `locations.json` | `locations` | `location_id` unique in the project, whatever its case |
| `cameras.json` | `cameras` | `label` and `camera_id` unique in the project, whatever their case |
| `sd_cards.json` | `sd_cards` | `label` unique in the project, whatever its case |
| `visits.json` | `visits`, `visit_actions`, `visit_trappers` | one visit to a location in a revision; actions and who went are tables |
| `unknown_visits.json` | `unknown_visits` | primary key (location, session) |
| `upload_failures.json` | `upload_failures` | primary key (project, deployment, destination) |
| `<R000N>/collection.json` | `collections` | unique (project, name) |
| `<R000N>/<deployment>/deployment.json` | `deployments` | Camtrap DP's fields; its images stay files |

## What changes with a database

* **A visit's location is required** (a foreign key). The JSON files keep the name of a location the project does not have; a migration must create it or refuse the visit. The camera,
  the SD card and who set it up are optional keys, and what was said and is not one of the project's goes to `camera_text`, `sd_text`, `setup_by_text` and `trappers_text`.
* **Instants are `datetime` in UTC.** The text of the JSON files (`…Z`) becomes a value; the timezone of the location is how it is told.
* **Days are `date`** (`in_service`, `status_date`).
* **Case-insensitive uniqueness** is a unique index on `lower(column)`.
* **Removed is `deleted_at`**, as in the files; a unique key still counts a removed record, because it comes back with its id when it is added again.

## What a table cannot say

The services check these across records, and they stay in code (they are in `x-rules` of each schema): a revision starts when the one before it is finished, the first visit to a
location is an Installation, a camera is up at one location at a time and a card is in one camera at a time, a Stolen visit finds the camera stolen, what a status allows, and the
`state` of a visit, worked out from the visits.
