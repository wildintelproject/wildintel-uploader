"""The commands of the settings (module `modules.settings`): `config show`, `config set`, `config path`, `config general`, `config log …` and
`config configs …` — the same settings
files as the web app's settings page, through the same contract (`domain.ports.SettingsService`). Only the asking and the showing are here: Rich
tables, prompts, messages."""
from __future__ import annotations

from typing import Annotated, Optional

import typer
from rich.table import Table

from wildintel_uploader.entrypoints.cli.common import console, fail
from dishka import FromDishka

from wildintel_uploader.entrypoints.cli.injection import inject
from wildintel_uploader.modules.settings.domain.models import SettingsError
from wildintel_uploader.modules.settings.domain.ports import NoLogFile, SettingsService, ShownSetting, UnknownConfig, UnknownSetting

settings_app = typer.Typer(help="Show or change the settings — the same settings.toml as the web app's ⚙️ page.", no_args_is_help=True)
configs_app = typer.Typer(help="The configs — sets of settings — the app can switch between.", no_args_is_help=True)
settings_app.add_typer(configs_app, name="configs")
log_app = typer.Typer(help="The log of the app: where it is, and clearing it.", no_args_is_help=True)
settings_app.add_typer(log_app, name="log")


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
def show(service: FromDishka[SettingsService],
         section: Annotated[Optional[str], typer.Argument(help="Only this section — GENERAL, TRAPPER, AGOUTI, EPICOLLECT5, VALIDATION…")] = None) -> None:
    """Show the settings (the passwords and the secrets never shown)."""
    shown = service.shown_settings()
    if section is not None:
        wanted = section.upper()
        if wanted not in shown:
            raise fail(f"No section {section}. The sections: {', '.join(shown)}.")
        shown = {wanted: shown[wanted]}
    for name, settings in shown.items():
        table = Table(title=name, title_justify="left", show_header=False, box=None, padding=(0, 2))
        for setting in settings:
            table.add_row(setting.key, _shown(setting))
        console.print(table)
    console.print(f"[dim]{service.places().settings_file}[/dim]")


@settings_app.command("path")
@inject
def path(service: FromDishka[SettingsService]) -> None:
    """Where settings.toml, the log and the app's folders are."""
    from wildintel_uploader.modules.settings.infrastructure import activity_log as logging_setup

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


# ── the General section ──

@settings_app.command("general")
@inject
def general(service: FromDishka[SettingsService]) -> None:
    """The General section, as the settings page shows it — change one with `config set GENERAL.…` or `config set DATA.…`."""
    view = service.general()
    g, f, system = view.general, view.folders, view.system
    table = Table(title="GENERAL", title_justify="left", show_header=False, box=None, padding=(0, 2))
    table.add_row("Log level", g.log_level + (f"  [yellow](the environment forces {system.log_level_override})[/yellow]" if system.log_level_override else ""))
    table.add_row("Images at once", f"{g.workers}  [dim](this computer has {system.cpu_count} CPU{'s' if system.cpu_count != 1 else ''}; at most {system.max_workers})[/dim]")
    table.add_row("Default research project", g.default_research_project or "—")
    table.add_row("Welcome page", "shown" if g.show_welcome else "not shown")
    console.print(table)
    folders = Table(title="Folders", title_justify="left", show_header=False, box=None, padding=(0, 2))
    for label, own, default in (("Data", f.dir, f.default_dir), ("Collections", f.collections_dir, f.default_collections_dir),
                                ("Reports", f.reports_dir, f.default_reports_dir), ("Packages", f.packages_dir, f.default_packages_dir)):
        folders.add_row(label, own if own else f"{default}  [dim](default)[/dim]")
    console.print(folders)
    console.print(f"[dim]Log file: {system.log_file}[/dim]")


@log_app.command("path")
@inject
def log_path(service: FromDishka[SettingsService]) -> None:
    """Where the log file is — to attach it to a bug report."""
    try:
        console.print(str(service.log_file()))
    except NoLogFile:
        raise fail("There's no log file yet.") from None


@log_app.command("clear")
@inject
def log_clear(service: FromDishka[SettingsService], yes: Annotated[bool, typer.Option("--yes", "-y", help="Don't ask.")] = False) -> None:
    """Deletes the log file and its older copies. Logging goes on, into a new one."""
    if not yes and not typer.confirm("Delete the log file and its older copies? This can't be undone"):
        raise typer.Exit()
    deleted = service.clear_log()
    console.print(f"[green]✔[/green] {deleted} file{'s' if deleted != 1 else ''} deleted.")
