# store/files

One JSON Schema (draft 2020-12) for each file the app keeps, **as it is kept** — not as the API takes it. They are made by `../generate_schemas.py` from the models of the app
(`core/config.py`, `core/schemas/requests.py`), and checked against real files: a schema accepts what the app wrote and refuses what it would refuse.

| Schema | File |
|---|---|
| `research_project` | `<collections folder>/<research project id>/research_project.json` |
| `locations` | `…/<research project id>/locations.json` |
| `visits` | `…/<research project id>/visits.json` |
| `unknown_visits` | `…/<research project id>/unknown_visits.json` |
| `cameras` | `…/<research project id>/cameras.json` |
| `sd_cards` | `…/<research project id>/sd_cards.json` |
| `roles` | `…/<research project id>/roles.json` |
| `upload_failures` | `…/<research project id>/upload_failures.json` |
| `trappers` | `<collections folder>/trappers.json` (the people: they belong to no project) |
| `collection` | `…/<R000N>/collection.json` |
| `deployment` | `…/<R000N>/<deployment id>/deployment.json` |
| `settings` | `settings.toml` of the user's configuration folder |

Use one with any validator, for example `jsonschema`:

    jsonschema -i collections/WICP_02/visits.json store/files/visits.schema.json

## What a schema says besides its types

JSON Schema cannot say that a value is unique among the items, that it points to another file, or what a status allows. Each schema says it in keywords that a validator ignores:

* `x-file` — where the file is.
* `x-unique` — the lists of properties that are unique among the items (compared without regard to case).
* `x-references` — what a property points to (`location_ref` → `locations.id`).
* `x-rules` — what the services check across records: one visit to a location in a revision, a revision starts when the one before it is finished, a camera is up at one location at
  a time, an archived thing never goes back…

## What every record has

`id` (a UUID the app generates and never changes), `created_at`, `updated_at` and `deleted_at`, all written by the app. **Nothing is deleted**: what is removed gets `deleted_at` and is
no longer listed; if it is added again it comes back with its id.

## The visits

A visit is kept with `when`, the instant in UTC (`2026-09-14T08:30:00Z`); its day and its time are told on the wall clock of its location (its `timezone`). What it points to — its
location, camera, SD card, who set it up and who went — it says by id (`location_ref`, `camera_ref`, `sd_ref`, `setup_by_ref`, `trapper_refs`); what is not one of the project's is kept
as it was said (`location_id`, `camera_id`, `sd`, `setup_by`, `trappers`).
