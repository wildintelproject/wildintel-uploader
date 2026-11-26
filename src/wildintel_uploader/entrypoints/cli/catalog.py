"""The commands of the catalog (module `modules.catalog`): `catalog trappers list` and `catalog trappers add` — the same people as the settings page,
through the same contract (`domain.ports.CatalogService`). Only the asking and the showing are here."""
from __future__ import annotations

from typing import Annotated, Optional

import typer
from dishka import FromDishka
from rich.table import Table

from wildintel_uploader.cli.common import console, fail
from wildintel_uploader.entrypoints.cli.injection import inject
from wildintel_uploader.modules.catalog.domain.models import CatalogError, Trapper
from wildintel_uploader.modules.catalog.domain.ports import CatalogService

catalog_app = typer.Typer(help="The catalog: the research projects, their locations, cameras and SD cards, and the people who go to the field.",
                          no_args_is_help=True)
trappers_app = typer.Typer(help="The people who go to the field — whatever the research project.", no_args_is_help=True)
catalog_app.add_typer(trappers_app, name="trappers")

_STATUS = {"active": "green", "inactive": "yellow", "archived": "dim"}


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
