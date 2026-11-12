# store

What the app keeps, described for the day it is kept in a database. **Nothing here is used by the app**: it is there to be read.

| Folder | What it has |
|---|---|
| [`files/`](files/README.md) | JSON Schemas of each JSON file the app keeps — with the constraints, in `x-…` keywords for what a schema cannot say |
| [`sql/`](sql/README.md) | The same records as [SQLModel](https://sqlmodel.tiangolo.com/) models: tables, keys and checks |

What is **not** here, because it is not kept in the database: the images and what is written beside them (`images.json`, `preprocessing.json`, the logs of a collection), the
reports and the sessions. The settings are in `settings.toml`; their schema is in `files/` only to see them.

The app already goes through one door to keep its records — `core/storage` (`ProjectStore`) —, so a database is a backend to register there, not a change of the app.

The schemas are written from the models the app validates with, so they do not drift from it:

    .venv/bin/python store/generate_schemas.py
