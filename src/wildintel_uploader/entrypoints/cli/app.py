"""WildINTEL Uploader — the command-line app, on the same modules (and the same settings.toml) as the web app: each module's commands are its
entry point here, put together under one app.

    wildintel-uploader --help
"""
from __future__ import annotations

from typing import Annotated

import typer

from wildintel_uploader.core.version import current_version
from wildintel_uploader.entrypoints.cli.catalog import catalog_app
from wildintel_uploader.entrypoints.cli.common import console
from wildintel_uploader.entrypoints.cli.deployments import statistics_app
from wildintel_uploader.entrypoints.cli.settings import settings_app
from wildintel_uploader.entrypoints.cli.uploaders import import_deployment, test_connection, trapper_app

app = typer.Typer(
    name="wildintel-uploader",
    help="WildINTEL Uploader — import camera-trap deployments into TRAPPER.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


def _show_version(value: bool) -> None:
    if value:
        console.print(current_version())
        raise typer.Exit()


@app.callback()
def main(
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Show the log's messages as it works.")] = False,
    version: Annotated[bool, typer.Option("--version", help="Show the version and exit.", is_eager=True, callback=_show_version)] = False,
) -> None:
    from wildintel_uploader.core import logging_setup

    logging_setup.configure(console_level="DEBUG" if verbose else "WARNING")


app.command("test-connection")(test_connection)
app.command("tc", hidden=True, help="Alias for test-connection.")(test_connection)
app.add_typer(settings_app, name="config")              # the module of the settings
app.add_typer(catalog_app, name="catalog")              # the module of the catalog
app.add_typer(trapper_app, name="trapper")              # the uploaders: what TRAPPER has
app.command("import-deployment")(import_deployment)     # the uploaders: a deployment into TRAPPER
app.add_typer(statistics_app, name="statistics")        # the deployments


def run() -> None:
    app()
