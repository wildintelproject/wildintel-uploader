"""The commands of the uploaders (module `modules.uploaders`): testing the account, looking up what TRAPPER has, and importing a deployment into it —
the wizard of the command line, which scans and guesses through the deployments."""
from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

import typer
from dishka import FromDishka
from pydantic import ValidationError
from rich.panel import Panel
from rich.prompt import Confirm, FloatPrompt, IntPrompt, Prompt
from rich.table import Table

from wildintel_uploader.entrypoints.cli.common import call, console, fail
from wildintel_uploader.entrypoints.cli.injection import inject
from wildintel_uploader.modules.deployments.domain.ports import DeploymentsService
from wildintel_uploader.modules.uploaders.domain.models import Account, UploaderError
from wildintel_uploader.modules.uploaders.domain.ports import UploadersService
from wildintel_uploader.shared.camtrap import DeploymentFields

trapper_app = typer.Typer(help="Find the TRAPPER ids the other commands take.", no_args_is_help=True)
SETTINGS_HINT = "Set it with: wildintel-uploader config set TRAPPER.<field> …"


def _checked(call_it):
    try:
        return call_it()
    except UploaderError as exc:
        hint = f" {SETTINGS_HINT}" if exc.message.startswith("Missing TRAPPER") else ""
        raise fail(f"{exc.message}{hint}") from exc


def _cell(value) -> str:
    return "—" if value is None else str(value)


def table(title: str, columns: list[str], rows: list[list]) -> None:
    out = Table(*columns, title=title, title_justify="left")
    for row in rows:
        out.add_row(*[_cell(c) for c in row])
    console.print(out)


@inject
def test_connection(uploaders: FromDishka[UploadersService]) -> None:
    """Test the connection to TRAPPER (settings.toml's account)."""
    defaults = uploaders.account_defaults()
    result = _checked(lambda: uploaders.test_connection(Account()))
    console.print(f"[green]✔[/green] TRAPPER {defaults['base_url']} as {defaults['user_name']} — {result['research_projects_count']} research project(s)")


@trapper_app.command("research-projects")
@inject
def trapper_research_projects(uploaders: FromDishka[UploadersService]) -> None:
    """The research projects you can access."""
    rows = _checked(lambda: uploaders.research_projects(Account()))
    table("Research projects", ["pk", "Name", "Acronym"], [[r["pk"], r["name"], r["acronym"]] for r in rows])


@trapper_app.command("classification-projects")
@inject
def trapper_classification_projects(rp: Annotated[int, typer.Option("--rp", "--research-project", help="Research project pk.")],
                                    uploaders: FromDishka[UploadersService]) -> None:
    """A research project's classification projects."""
    rows = _checked(lambda: uploaders.classification_projects(Account(), rp))
    table("Classification projects", ["pk", "Name", "Active"], [[r["pk"], r["name"], r["is_active"]] for r in rows])


@trapper_app.command("locations")
@inject
def trapper_locations(rp: Annotated[int, typer.Option("--rp", "--research-project", help="Research project pk.")],
                      uploaders: FromDishka[UploadersService]) -> None:
    """A research project's locations."""
    rows = _checked(lambda: uploaders.locations(Account(), rp))
    table("Locations", ["pk", "Location id", "Name", "Timezone"], [[r["pk"], r["location_id"], r["name"], r["timezone"]] for r in rows])


def _pick(prompt: str, items: list[dict], label_fn) -> dict:
    if not items:
        raise fail("Nothing to choose from.")
    table(prompt, ["#", "Choice"], [[i + 1, label_fn(item)] for i, item in enumerate(items)])
    choice = typer.prompt(f"{prompt} — number", type=int)
    if not 1 <= choice <= len(items):
        raise fail("Invalid choice.")
    return items[choice - 1]


def _optional_prompt(label: str, default: str | None = None) -> Optional[str]:
    value = Prompt.ask(label, default=default or "")
    return value or None


@inject
def import_deployment(uploaders: FromDishka[UploadersService], deployments: FromDishka[DeploymentsService]) -> None:
    """Import a deployment: organize a folder of camera-trap images locally, then register the deployment in TRAPPER. Does not upload the images
    to TRAPPER yet — that's a separate step this app doesn't have."""
    from wildintel_uploader.modules.deployments.infrastructure import deployment_import_service
    account = Account()
    _checked(lambda: uploaders.research_projects(account) and None)   # the account, before anything is asked

    console.print(Panel(
        "This copies your images to this app's own data folder before doing anything else — nothing in the source folder is changed or moved.\n\n"
        "[yellow]Copy the images from the camera's SD card to a local folder first — don't point this at the card itself.[/yellow]",
        title="Import deployment",
    ))
    if not Confirm.ask("Continue?", default=True):
        raise typer.Exit()

    rp = _pick("Research project", _checked(lambda: uploaders.research_projects(account)),
               lambda p: f"{p['acronym'] + ' — ' if p['acronym'] else ''}{p['name']}")
    cps = _checked(lambda: uploaders.classification_projects(account, rp["pk"]))
    cp = _pick("Classification project (optional)", [{"pk": None, "name": "(none)"}] + cps, lambda p: p["name"]) if cps else None
    location = _pick("Location", _checked(lambda: uploaders.locations(account, rp["pk"])), lambda loc: f"{loc['location_id']} — {loc['name'] or ''}")

    source_dir = Prompt.ask("Source images folder")
    scan = call(lambda: deployments.scan_folder(Path(source_dir).expanduser()))
    console.print(f"  {scan['file_count']} file(s), {scan['image_count']} image(s)")
    for warning in scan["warnings"]:
        console.print(f"  [yellow]⚠ {warning}[/yellow]")
    # what the form starts from — the images' date range and camera
    guess = call(lambda: deployments.guess_details(Path(source_dir).expanduser()))
    console.print(f"  Capture dates: {guess['start_date'] or '—'} → {guess['end_date'] or '—'}")
    for warning in guess["warnings"]:
        console.print(f"  [yellow]⚠ {warning}[/yellow]")

    revision = IntPrompt.ask("Revision number (1, 2, 3…)")
    deployment_id = call(lambda: deployment_import_service.deployment_id_for(revision, location["location_id"]))
    console.print(f"  Deployment id: [bold]{deployment_id}[/bold]")
    timezone = Prompt.ask("Timezone (IANA, e.g. Europe/Madrid)", default=location["timezone"] or "")
    latitude = FloatPrompt.ask("Latitude (decimal degrees, WGS84, -90..90)")
    longitude = FloatPrompt.ask("Longitude (decimal degrees, WGS84, -180..180)")
    start_date = Prompt.ask("Start date (local time, YYYY-MM-DDThh:mm:ss)", default=guess["start_date"] or "")
    end_date = Prompt.ask("End date (local time, YYYY-MM-DDThh:mm:ss)", default=guess["end_date"] or "")
    camera_model = _optional_prompt("Camera model", guess["camera_model"])
    # Camtrap DP wants the dates with a timezone designator (±hh:mm)
    start_date = call(lambda: deployment_import_service.with_timezone(start_date, timezone))
    end_date = call(lambda: deployment_import_service.with_timezone(end_date, timezone))

    fields: dict = {"deployment_id": deployment_id, "location_id": location["location_id"], "location_name": location["name"], "latitude": latitude,
                    "longitude": longitude, "start_date": start_date, "end_date": end_date, "camera_model": camera_model}
    if Confirm.ask("Fill in the rest of the deployment fields now (camera setup, habitat, bait, comments...)?", default=False):
        for key, label in [
            ("setup_by", "Set up by"), ("camera_id", "Camera id"), ("coordinate_uncertainty", "Coordinate uncertainty (m)"),
            ("camera_interval", "Camera delay (seconds)"), ("camera_height", "Camera height (m)"), ("camera_depth", "Camera depth (m)"),
            ("camera_tilt", "Camera tilt (degrees)"), ("camera_heading", "Camera heading (degrees)"), ("detection_distance", "Detection distance (m)"),
            ("bait_use", "Bait used (true/false)"), ("feature_type", "Feature type"), ("habitat", "Habitat"),
            ("deployment_groups", "Deployment groups"), ("comments", "Comments"),
        ]:
            fields[key] = _optional_prompt(label)
    try:
        deployment = DeploymentFields.model_validate(fields)
    except ValidationError as exc:
        raise fail(exc.errors()[0]["msg"]) from exc

    console.print(Panel(f"[bold]{deployment.deployment_id}[/bold] at {deployment.location_id} — {deployment.start_date} → {deployment.end_date or '?'}",
                        title="Ready to import"))
    if not Confirm.ask("Proceed?", default=True):
        raise typer.Exit()

    def run():
        # the timezone typed is the one the images are read in
        for event in uploaders.import_deployment(account, rp["pk"], cp["pk"] if cp else None, source_dir, deployment,
                                                 str(rp.get("acronym") or rp["pk"]), True, timezone=timezone):
            if event["type"] == "copy":
                console.print(f"  [{event['index']}/{event['total']}] {event['name']}")
            elif event["type"] == "registering":
                console.print("  Registering the deployment in TRAPPER…")
            elif event["type"] == "done":
                console.print(f"[green]✔  Imported — images organized in {event['dest_dir']}[/green]")
    call(run)
