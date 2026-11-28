"""The commands of the deployments (module `modules.deployments`): the statistics of a collection, and two deployments side by side."""
from __future__ import annotations

from typing import Annotated

import typer
from dishka import FromDishka
from rich.table import Table

from wildintel_uploader.entrypoints.cli.common import call, console
from wildintel_uploader.entrypoints.cli.injection import inject
from wildintel_uploader.modules.deployments.domain.ports import DeploymentsStatistics

statistics_app = typer.Typer(help="Compare the deployments with the previous revisions of their location.", no_args_is_help=True)


def _num(value, digits: int = 1) -> str:
    return "—" if value is None else (str(int(value)) if float(value) == int(value) else f"{value:.{digits}f}")


@statistics_app.command("collection")
@inject
def statistics_collection(
    research_project: Annotated[str, typer.Argument(help="The research project's id (its folder in the collections folder).")],
    collection: Annotated[str, typer.Argument(help="The collection, e.g. R0028.")],
    deployments: FromDishka[DeploymentsStatistics],
) -> None:
    """Each deployment of a collection against the previous revisions of its location, with the thresholds of POSTVALIDATION."""
    rows = call(lambda: deployments.revision_statistics(research_project, collection))
    table = Table(title=f"{research_project} / {collection}", title_justify="left")
    for column in ("Deployment", "Images", "Per day", "Sequences", "Seq. length", "Longest", "Previous", "Status"):
        table.add_column(column, justify="left" if column in ("Deployment", "Status") else "right")
    styles = {"ok": "green", "review": "red", "insufficient_history": "yellow"}
    for row in rows:
        m = row["metrics"]
        previous = row["checks"]["image_count"]["previous"]
        table.add_row(row["deployment_id"], _num(m["image_count"]), _num(m["images_per_day"]), _num(m["sequence_count"]), _num(m["sequence_length"]),
                      _num(m["sequence_max"]), str(previous), f"[{styles[row['status']]}]{row['status']}[/]")
    console.print(table)
    for row in rows:
        for check in row["checks"].values():
            if not check["skipped"] and not check["ok"]:
                console.print(f"  [red]✘[/red] {row['deployment_id']}: {check['message']}")
    if not rows:
        console.print("[yellow]No deployments in that collection.[/yellow]")


@statistics_app.command("compare")
@inject
def statistics_compare(
    research_project: Annotated[str, typer.Argument(help="The research project's id.")],
    first: Annotated[str, typer.Argument(help="The deployment to compare from, e.g. R0002-DONA_0006.")],
    second: Annotated[str, typer.Argument(help="The deployment to compare to, e.g. R0003-DONA_0006.")],
    deployments: FromDishka[DeploymentsStatistics],
) -> None:
    """Two deployments side by side — for the same location in two revisions."""
    result = call(lambda: deployments.compare(research_project, first, second))
    table = Table(title=f"{first} → {second}", title_justify="left")
    for column in ("Metric", first, second, "Change"):
        table.add_column(column, justify="left" if column == "Metric" else "right")
    for key, values in result["metrics"].items():
        change = values["change_percent"]
        table.add_row(key, _num(values["first"]), _num(values["second"]), "—" if change is None else f"{change:+.0f}%")
    console.print(table)
