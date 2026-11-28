# settings — the settings of the app

What the settings are and the rules they follow, how the settings page and the command line use them, and where they are kept: the TOML files of
the user's config folder — `settings.toml` (the default config) and one more for each config —, read with Dynaconf so that a
`WILDINTEL_UPLOADER_*` variable of the environment overrides a setting.

## Its contract

| Contract | What it is | Operations |
|---|---|---|
| `SettingsReading` | What the settings are, for whoever only reads them: the settings of the config in use, each section, what is shown of them and where the app keeps its files | `shown_settings`, `places`, `current`, `section`, `is_secret`, `general`, `log_file` |
| `SettingsEditing` | How the settings of the config in use are changed: all at once, a section, one setting by its name, or what the app changes on its own. Besides the errors each method names, a value that cannot be is the domain's SettingsError | `set_show_welcome`, `set_data_dir`, `change_setting`, `check_settings`, `save_settings`, `save_section`, `save_general`, `clear_log` |
| `SettingsConfigs` | The configs — the sets of settings the user keeps, one in use at a time | `list_configs`, `create_config`, `activate_config`, `config_file` |
| `SettingsOfBefore` | What the settings still hold of the field work, as versions before kept it there — for the catalog, which takes it in | `legacy_fieldwork`, `forget_legacy_fieldwork`, `keep_legacy_fieldwork` |
| `SettingsService` | All of them: what the module offers | — |

## How it is used

```python
settings.current().general.workers                           # what they are
settings.change_setting("TRAPPER.base_url", "https://…")      # one, typed as text
settings.save_section("VALIDATION", {"duplicates": False})    # a section
```

The web app has `/api/settings/…`; the command line, `wucli config …`.

Each section is a frozen dataclass that **checks itself** when it is made (`SettingsError`, naming the setting). The sections of the other
modules are theirs: each says them in its `domain/settings.py` (`SECTIONS`) and its format in `infrastructure/settings.py` (`SCHEMAS`), and this
module puts them together (`domain/registry.py`). The format of the file says only the shape; the rules are checked on every read and write.

A password or a key is a **`Secret`**: it prints as `********`, and says what it holds only with `reveal()`.

## What it refuses

`SettingsError` (a value that cannot be, naming the setting), `UnknownSetting`, `UnknownConfig`, `BadConfigName`, `NoSettingsFile`,
`UnreadableSettings` (a file that is not TOML or not settings), `NoLogFile`.

## How it is made

- `domain/` — the sections (`models.py`), the rules every section follows (`rules.py`: `Secret`, ranges, choices), how the sections are put
  together (`registry.py`), the folders of the app (`folders.py`), the ports.
- `application/use_cases.py` — the contract over the ports.
- `infrastructure/` — the TOML files (`toml_files.py`, with what was read kept in `file_cache.py`), the format of the file (`schema.py`) and how
  it turns into the domain (`mapping.py`), the folders of the user (`app_dirs.py`), the log (`activity_log.py`), the machine (`system.py`),
  `api_schemas.py`.
