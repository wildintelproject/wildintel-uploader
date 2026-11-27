"""The commands of the catalog (module `modules.catalog`): `catalog trappers …`, `catalog projects …` and `catalog locations …` — the same people,
research projects and locations as the settings page, through the same contract (`domain.ports.CatalogService`). Only the asking and the showing are
here."""
from __future__ import annotations

from typing import Annotated, Optional

import typer
from dishka import FromDishka
from rich.table import Table

from wildintel_uploader.entrypoints.cli.common import console, fail
from wildintel_uploader.entrypoints.cli.injection import inject
from wildintel_uploader.modules.catalog.domain.models import (
    LOCATION_STATUSES, PROJECT_STATUSES, CatalogError, Location, ResearchProject, Trapper, UnknownLocation, UnknownProject,
)
from pathlib import Path

from wildintel_uploader.entrypoints.catalog_storage import move_catalog
from wildintel_uploader.modules.catalog.application.migration import TargetNotEmpty
from wildintel_uploader.modules.catalog.domain.ports import CatalogService
from wildintel_uploader.modules.settings.domain.ports import SettingsService

catalog_app = typer.Typer(help="The catalog: the research projects, their locations, cameras and SD cards, and the people who go to the field.",
                          no_args_is_help=True)
trappers_app = typer.Typer(help="The people who go to the field — whatever the research project.", no_args_is_help=True)
catalog_app.add_typer(trappers_app, name="trappers")
projects_app = typer.Typer(help="The research projects — each with its folder in the collections folder, named by its acronym.", no_args_is_help=True)
catalog_app.add_typer(projects_app, name="projects")
locations_app = typer.Typer(help="The locations of a research project, where the camera traps are put up.", no_args_is_help=True)
catalog_app.add_typer(locations_app, name="locations")

_STATUS = {"active": "green", "inactive": "yellow", "archived": "dim", "planned": "cyan", "finished": "blue", "pending": "yellow", "ready": "cyan"}


@trappers_app.command("list")
@inject
def trappers_list(catalog: FromDishka[CatalogService],
                  all_: Annotated[bool, typer.Option("--all", help="The removed ones too.")] = False) -> None:
    """The people who go to the field."""
    trappers = catalog.trappers(include_deleted=all_)
    table = Table(show_header=True, box=None, padding=(0, 2))
    for column in ("Username", "Name", "Affiliation", "Email", "Status"):
        table.add_column(column)
    for t in sorted(trappers, key=lambda t: t.name.lower()):
        status = f"[{_STATUS.get(t.status, '')}]{t.status}[/]" + (" [red](removed)[/red]" if t.deleted else "")
        table.add_row(t.username, t.name, t.affiliation or "—", t.email or "—", status)
    console.print(table)
    console.print(f"[dim]{len(trappers)} {'person' if len(trappers) == 1 else 'people'}[/dim]")


@trappers_app.command("add")
@inject
def trappers_add(
    catalog: FromDishka[CatalogService],
    username: Annotated[str, typer.Argument(help="What they are called in the app — no spaces, unique.")],
    name: Annotated[str, typer.Argument(help="The full name, as it should be on a visit.")],
    affiliation: Annotated[Optional[str], typer.Option(help="Where they work.")] = None,
    email: Annotated[Optional[str], typer.Option(help="Their email address.")] = None,
) -> None:
    """Add a person who goes to the field."""
    try:
        added = catalog.add_trappers([Trapper(username=username, name=name, affiliation=affiliation, email=email)])
    except CatalogError as exc:
        raise fail(f"Invalid {exc.field}: {exc.message}.") from exc
    if added.skipped:
        raise fail(f"There is already a trapper with the username {username}.")
    console.print(f"[green]✔[/green] {name} added as {username}.")


# ── the research projects ──

def _status(record) -> str:
    return f"[{_STATUS.get(record.status, '')}]{record.status}[/]" + (" [red](removed)[/red]" if record.deleted else "")


@projects_app.command("list")
@inject
def projects_list(catalog: FromDishka[CatalogService],
                  all_: Annotated[bool, typer.Option("--all", help="The removed ones too.")] = False) -> None:
    """The research projects."""
    projects = catalog.projects(include_deleted=all_)
    table = Table(show_header=True, box=None, padding=(0, 2))
    for column in ("Acronym", "Name", "Status", "Created"):
        table.add_column(column)
    for p in sorted(projects, key=lambda p: p.acronym.lower()):
        table.add_row(p.acronym, p.name, _status(p), (p.audit.created_at or "—")[:10])
    console.print(table)
    console.print(f"[dim]{len(projects)} research project{'s' if len(projects) != 1 else ''}[/dim]")


@projects_app.command("show")
@inject
def projects_show(catalog: FromDishka[CatalogService], acronym: Annotated[str, typer.Argument(help="Its acronym.")]) -> None:
    """One research project, with all it says."""
    try:
        p = catalog.project(acronym)
    except UnknownProject as exc:
        raise fail(str(exc)) from None
    table = Table(title=f"{p.acronym} — {p.name}", title_justify="left", show_header=False, box=None, padding=(0, 2))
    for label, value in (("Status", _status(p)), ("Sampling design", p.sampling_design), ("Sensor method", p.sensor_method),
                         ("Animal types", p.animal_types), ("Bait use", p.bait_use), ("Event interval", p.event_interval),
                         ("Keywords", p.keywords or "—"), ("Abstract", p.abstract or "—"), ("Methods", p.methods or "—"),
                         ("Description", p.description or "—"), ("TRAPPER id", p.trapper_pk if p.trapper_pk is not None else "—"),
                         ("Created", p.audit.created_at or "—"), ("Changed", p.audit.updated_at or "—")):
        table.add_row(label, str(value))
    console.print(table)


@projects_app.command("add")
@inject
def projects_add(
    catalog: FromDishka[CatalogService],
    acronym: Annotated[str, typer.Argument(help="3 to 10 letters, digits, dots, hyphens or underscores: it names its folder, and never changes.")],
    name: Annotated[str, typer.Argument(help="Its name.")],
    status: Annotated[str, typer.Option(help=f"One of {', '.join(PROJECT_STATUSES)}.")] = "active",
    description: Annotated[Optional[str], typer.Option(help="What it is about.")] = None,
) -> None:
    """Add a research project, and its folder in the collections folder."""
    try:
        catalog.add_project(ResearchProject(acronym=acronym, name=name, status=status, description=description or ""))
    except CatalogError as exc:
        raise fail(exc.message if exc.message.endswith(".") else f"Invalid {exc.field}: {exc.message}.") from exc
    console.print(f"[green]✔[/green] {acronym} — {name} added.")


@projects_app.command("set-status")
@inject
def projects_set_status(
    catalog: FromDishka[CatalogService],
    acronym: Annotated[str, typer.Argument(help="Its acronym.")],
    status: Annotated[str, typer.Argument(help=f"One of {', '.join(PROJECT_STATUSES)}.")],
) -> None:
    """Change the status of a research project. An archived one can no longer be changed."""
    try:
        catalog.update_project(acronym, {"status": status})
    except UnknownProject as exc:
        raise fail(str(exc)) from None
    except CatalogError as exc:
        raise fail(exc.message if exc.message.endswith(".") else f"Invalid {exc.field}: {exc.message}.") from exc
    console.print(f"[green]✔[/green] {acronym} is {status}.")


@projects_app.command("delete")
@inject
def projects_delete(catalog: FromDishka[CatalogService], acronym: Annotated[str, typer.Argument(help="Its acronym.")],
                    yes: Annotated[bool, typer.Option("--yes", "-y", help="Don't ask.")] = False) -> None:
    """Remove a research project — logically: it is no longer listed, and everything it has is kept. Not one that holds collections."""
    if not yes and not typer.confirm(f"Remove the research project {acronym}?"):
        raise typer.Exit()
    try:
        catalog.delete_project(acronym)
    except UnknownProject as exc:
        raise fail(str(exc)) from None
    except CatalogError as exc:
        raise fail(exc.message) from exc
    console.print(f"[green]✔[/green] {acronym} removed.")


# ── where the catalog is kept ──

@catalog_app.command("where")
@inject
def where(settings: FromDishka[SettingsService]) -> None:
    """Where the catalog is kept: the JSON files of the collections folder, or a SQLite database."""
    places = settings.places()
    # a path as it is, on one line, to be copied
    console.print(f"SQLite database: {places.catalog_database}" if places.catalog_storage == "sqlite" else f"JSON files of {places.collections}",
                  soft_wrap=True)


@catalog_app.command("migrate")
@inject
def migrate(
    settings: FromDishka[SettingsService],
    to: Annotated[str, typer.Option("--to", help="json — the files of the collections folder — or sqlite — a database.")],
    database: Annotated[Optional[Path], typer.Option(help="The SQLite database — else catalog.sqlite3 in the data folder.")] = None,
    replace: Annotated[bool, typer.Option("--replace", help="Overwrite a catalog that is there already.")] = False,
) -> None:
    """Move the catalog — the people and the research projects — to another place, and keep it there from now on. What is left where it was is not
    deleted."""
    if to not in ("json", "sqlite"):
        raise fail("--to is json or sqlite.")
    try:
        copied = move_catalog(settings, to, database=database, replace=replace)
    except TargetNotEmpty as exc:
        raise fail(f"{exc.message} (--replace)") from exc
    except CatalogError as exc:
        raise fail(exc.message) from exc
    console.print(f"[green]✔[/green] {copied.trappers} people and {copied.projects} research projects moved to {to}: the catalog is kept there now.")


# ── the locations ──

def _refused(exc: Exception) -> typer.Exit:
    message = getattr(exc, "message", None) or str(exc)
    return fail(message if message.endswith(".") else f"Invalid {getattr(exc, 'field', 'value')}: {message}.")


@locations_app.command("list")
@inject
def locations_list(catalog: FromDishka[CatalogService], project: Annotated[str, typer.Argument(help="The research project.")],
                   all_: Annotated[bool, typer.Option("--all", help="The removed ones too.")] = False) -> None:
    """The locations of a research project."""
    locations = catalog.locations(project, include_deleted=all_)
    table = Table(show_header=True, box=None, padding=(0, 2))
    for column in ("Location", "Name", "Status", "Timezone", "Latitude", "Longitude"):
        table.add_column(column)
    for loc in sorted(locations, key=lambda loc: loc.location_id.lower()):
        zone = (loc.timezone or "—") + (" (no summer time)" if loc.ignore_dst else "")
        table.add_row(loc.location_id, loc.name or "—", _status(loc), zone, "—" if loc.latitude is None else f"{loc.latitude:.5f}",
                      "—" if loc.longitude is None else f"{loc.longitude:.5f}")
    console.print(table)
    console.print(f"[dim]{len(locations)} location{'s' if len(locations) != 1 else ''} of {project}[/dim]")


@locations_app.command("add")
@inject
def locations_add(
    catalog: FromDishka[CatalogService],
    project: Annotated[str, typer.Argument(help="The research project.")],
    location_id: Annotated[str, typer.Argument(help="Its id, as the field files name it (DONA_01).")],
    latitude: Annotated[float, typer.Option(help="WGS84 decimal degrees.")],
    longitude: Annotated[float, typer.Option(help="WGS84 decimal degrees.")],
    timezone: Annotated[str, typer.Option(help="The IANA timezone of its visits (Europe/Madrid). Fixed once it is made.")] = "UTC",
    ignore_dst: Annotated[bool, typer.Option("--ignore-dst", help="Its cameras never change to summer time. Fixed once it is made.")] = False,
    name: Annotated[Optional[str], typer.Option(help="Its name.")] = None,
    planned: Annotated[bool, typer.Option("--planned", help="Planned, not pending: not offered for a visit yet.")] = False,
) -> None:
    """Add a location to a research project. It starts pending — its first visit starts it — or planned."""
    try:
        location = Location(location_id=location_id, timezone=timezone, ignore_dst=ignore_dst, latitude=latitude, longitude=longitude, name=name,
                            status="planned" if planned else "pending")
        catalog.add_location(project, location, by_hand=True)
    except (CatalogError, UnknownProject) as exc:
        raise _refused(exc) from exc
    console.print(f"[green]✔[/green] {location_id} added to {project}.")


@locations_app.command("set-status")
@inject
def locations_set_status(
    catalog: FromDishka[CatalogService],
    project: Annotated[str, typer.Argument(help="The research project.")],
    location_id: Annotated[str, typer.Argument(help="The location.")],
    status: Annotated[str, typer.Argument(help=f"One of {', '.join(LOCATION_STATUSES)} — as the visits allow.")],
) -> None:
    """Change the status of a location by hand — as far as its visits allow: a camera up there, a revision still to finish…"""
    try:
        catalog.update_location(project, location_id, {"status": status})
    except (CatalogError, UnknownLocation) as exc:
        raise _refused(exc) from exc
    console.print(f"[green]✔[/green] {location_id} is {status}.")


@locations_app.command("delete")
@inject
def locations_delete(catalog: FromDishka[CatalogService], project: Annotated[str, typer.Argument(help="The research project.")],
                     location_id: Annotated[str, typer.Argument(help="The location.")],
                     yes: Annotated[bool, typer.Option("--yes", "-y", help="Don't ask.")] = False) -> None:
    """Remove a location — logically: it is kept, its visits still need its timezone. Not one with visits, nor one from TRAPPER."""
    if not yes and not typer.confirm(f"Remove the location {location_id} of {project}?"):
        raise typer.Exit()
    try:
        catalog.delete_location(project, location_id)
    except (CatalogError, UnknownLocation) as exc:
        raise _refused(exc) from exc
    console.print(f"[green]✔[/green] {location_id} removed.")
