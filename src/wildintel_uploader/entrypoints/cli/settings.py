"""The commands of the settings (module `modules.settings`): `config show`, `config set`, `config path` and `config configs …` — the same settings
files as the web app's settings page, through the same contract (`domain.ports.SettingsService`). Only the asking and the showing are here: Rich
tables, prompts, messages."""
from __future__ import annotations

from typing import Annotated, Optional

import typer
from rich.table import Table

from wildintel_uploader.cli.common import console, fail
from dishka import FromDishka

from wildintel_uploader.entrypoints.cli.injection import inject
from wildintel_uploader.modules.settings.domain.models import SettingsError
from wildintel_uploader.modules.settings.domain.ports import SettingsService, ShownSetting, UnknownConfig, UnknownSetting

settings_app = typer.Typer(help="Show or change the settings — the same settings.toml as the web app's ⚙️ page.", no_args_is_help=True)
configs_app = typer.Typer(help="The configs — sets of settings — the app can switch between.", no_args_is_help=True)
settings_app.add_typer(configs_app, name="configs")


def _shown(setting: ShownSetting) -> str:
    if setting.secret:
        return "(saved)" if setting.saved else "(not set)"
    if setting.value is None:
        return "—"
    if isinstance(setting.value, tuple):
        return ", ".join(" + ".join(v) if isinstance(v, tuple) else str(v) for v in setting.value) or "—"
    if isinstance(setting.value, dict):
        return ", ".join(f"{k}: {v}" for k, v in setting.value.items()) or "—"
    return str(setting.value)


@settings_app.command("show")
@inject
def show(service: FromDishka[SettingsService]) -> None:
    """Show every setting (the passwords and the secrets never shown)."""
    for section, settings in service.shown_settings().items():
        table = Table(title=section, title_justify="left", show_header=False, box=None, padding=(0, 2))
        for setting in settings:
            table.add_row(setting.key, _shown(setting))
        console.print(table)
    console.print(f"[dim]{service.places().settings_file}[/dim]")


@settings_app.command("path")
@inject
def path(service: FromDishka[SettingsService]) -> None:
    """Where settings.toml, the log and the app's folders are."""
    from wildintel_uploader.core import logging_setup

    places = service.places()
    console.print(f"Settings:    {places.settings_file}")
    console.print(f"Log:         {logging_setup.log_file()}")
    console.print(f"Data:        {places.data}")
    console.print(f"Collections: {places.collections}")
    console.print(f"Reports:     {places.reports}")
    console.print(f"Packages:    {places.packages}")


@settings_app.command("set")
@inject
def set_(
    service: FromDishka[SettingsService],
    key: Annotated[str, typer.Argument(help="SECTION.field — e.g. TRAPPER.base_url, TRAPPER.user_password, DATA.dir.")],
    value: Annotated[Optional[str], typer.Argument(help="The new value — asked for (hidden for a password or a secret) if left out.")] = None,
) -> None:
    """Change one setting."""
    if value is None:
        value = typer.prompt(key, hide_input=service.is_secret(key))
    try:
        service.change_setting(key, value)
    except UnknownSetting:
        raise fail(f"No setting {key}. See: wildintel-uploader config show") from None
    except SettingsError as exc:
        raise fail(f"Invalid {key}: {exc.message}.") from exc
    console.print(f"[green]✔[/green] {key} saved.")


# ── the configs ──

def _configs_table(configs) -> None:
    table = Table(show_header=True, box=None, padding=(0, 2))
    for column in ("", "Id", "Name", "File"):
        table.add_column(column)
    for c in configs:
        table.add_row("[green]●[/green]" if c.active else "", c.id, c.name, f"[dim]{c.path}[/dim]")
    console.print(table)


@configs_app.command("list")
@inject
def configs_list(service: FromDishka[SettingsService]) -> None:
    """The configs, the one in use marked."""
    _configs_table(service.list_configs())


@configs_app.command("create")
@inject
def configs_create(service: FromDishka[SettingsService], name: Annotated[str, typer.Argument(help="Its name — its id is made from it.")]) -> None:
    """A new config with the default settings. It doesn't become the one in use."""
    try:
        _configs_table(service.create_config(name))
    except ValueError as exc:
        raise fail(str(exc)) from exc


@configs_app.command("use")
@inject
def configs_use(service: FromDishka[SettingsService], config_id: Annotated[str, typer.Argument(help="The id of the config, as `config configs list` shows it.")]) -> None:
    """From now on the app — web and command line — reads and saves that config."""
    try:
        _configs_table(service.activate_config(config_id))
    except UnknownConfig:
        raise fail(f"There's no config {config_id!r}. See: wildintel-uploader config configs list") from None
