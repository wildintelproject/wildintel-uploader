# Developer Manual

Same architecture as its sibling project, [wildintel-zooniverse](https://github.com/wildintelproject/wildintel-zooniverse):
a FastAPI backend (`src/wildintel_uploader/`) with a React/Vite frontend (`frontend/`), packaged
together into one executable per platform with PyInstaller. `wucli` is the development CLI (not to
be confused with `wildintel-uploader`, the app's own command-line interface).

## Setup

```
./setup.sh
```

This installs `uv` if it's missing, clones `wildintel-trapper-sdk` next to this project (its
Python dependency — see `[tool.uv.sources]` in `pyproject.toml`), and installs both the backend
and frontend dependencies.

## Running it

```
uv run wucli dev                  # backend + frontend, with hot reload
uv run wucli backend serve dev    # backend only
uv run wucli frontend dev         # frontend only
```

## Tests

```
uv run wucli backend test
uv run wucli frontend test
```

## Project layout

- `src/wildintel_uploader/core/` — the app's own logic, independent of how it's driven:
    - `services/trapper_service.py` — Trapper lookups (research projects, classification
      projects, locations) and registering a deployment (`deployments.import_deployments()`, the
      SDK's simulation of Trapper's classic deployment import form).
    - `services/deployment_import_service.py` — scanning a folder for EXIF dates/camera model,
      organizing it locally, and orchestrating the import.
    - `schemas/requests.py` — the web API's request/response models, also used directly by the CLI.
    - `config.py` — `settings.toml` (Trapper credentials, the local data folder), Dynaconf-backed.
- `src/wildintel_uploader/web/` — the FastAPI app (`main.py`) and its routers
  (`api/routers/`), mounting the built frontend as static files.
- `src/wildintel_uploader/cli/` — the command-line app (`wildintel-uploader`), a Typer app over
  the same `core` services.
- `frontend/` — the React app: one wizard page for now (`pages/`), the picker components it's
  built from (`components/`), reusing `Combobox` for the searchable research
  project/classification project/location pickers.

## Packaging

```
uv run wucli package build
```

Builds this system's package (`.AppImage`, `.exe` or `.dmg`) into `dist/` — the same
`wildintel-uploader.spec` the release workflow uses. Each platform builds on its own runner;
PyInstaller doesn't cross-compile.
