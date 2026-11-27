"""The settings of the uploaders — the sections TRAPPER and AGOUTI of settings.toml: where a deployment can be sent, and with what account —,
registered with the module of the settings."""
from __future__ import annotations

from dataclasses import dataclass

from wildintel_uploader.modules.settings.domain.registry import settings_registry
from wildintel_uploader.modules.settings.domain.rules import _blank_is_none, _in_range, _set, secret


@settings_registry.section("TRAPPER", "trapper", order=20)
@dataclass(frozen=True)
class TrapperSettings:
    enabled: bool = True                                 # whether TRAPPER is a place to upload deployments to
    base_url: str | None = None
    user_name: str | None = None                         # its email: the import form only accepts that
    user_password: str | None = secret(default=None)
    max_zip_mb: int = 500                                # the images of a deployment go in packages of at most this many megabytes

    def __post_init__(self) -> None:
        _in_range("TRAPPER.max_zip_mb", self.max_zip_mb, 1, 5000)
        # where to connect and as whom: blank is none
        _set(self, "base_url", _blank_is_none(self.base_url))
        _set(self, "user_name", _blank_is_none(self.user_name))


@settings_registry.section("AGOUTI", "agouti", order=40)
@dataclass(frozen=True)
class AgoutiSettings:
    """What an upload to Agouti needs (https://docs.agouti.eu/api/endpoints.html) — kept; nothing is uploaded to Agouti yet."""
    enabled: bool = False
    base_url: str | None = None                          # the address of its API, https://api.agouti.eu
    api_key: str | None = secret(default=None)           # sent as X-API-KEY
    project_id: str | None = None

    def __post_init__(self) -> None:
        _set(self, "base_url", _blank_is_none(self.base_url))
        _set(self, "project_id", _blank_is_none(self.project_id))
