"""The settings of the uploaders — the sections TRAPPER and AGOUTI of settings.toml: where a deployment can be sent, and with what account —,
registered with the module of the settings."""
from __future__ import annotations

from dataclasses import dataclass

from wildintel_uploader.modules.settings.domain.registry import Section
from wildintel_uploader.modules.settings.domain.rules import blank_is_none, in_range, tidy_field, secret


@dataclass(frozen=True)
class TrapperSettings:
    enabled: bool = True                                 # whether TRAPPER is a place to upload deployments to
    base_url: str | None = None
    user_name: str | None = None                         # its email: the import form only accepts that
    user_password: str | None = secret(default=None)
    max_zip_mb: int = 500                                # the images of a deployment go in packages of at most this many megabytes

    def __post_init__(self) -> None:
        in_range("TRAPPER.max_zip_mb", self.max_zip_mb, 1, 5000)
        # where to connect and as whom: blank is none
        tidy_field(self, "base_url", blank_is_none(self.base_url))
        tidy_field(self, "user_name", blank_is_none(self.user_name))


@dataclass(frozen=True)
class AgoutiSettings:
    """What an upload to Agouti needs (https://docs.agouti.eu/api/endpoints.html) — kept; nothing is uploaded to Agouti yet."""
    enabled: bool = False
    base_url: str | None = None                          # the address of its API, https://api.agouti.eu
    api_key: str | None = secret(default=None)           # sent as X-API-KEY
    project_id: str | None = None

    def __post_init__(self) -> None:
        tidy_field(self, "base_url", blank_is_none(self.base_url))
        tidy_field(self, "project_id", blank_is_none(self.project_id))


# The sections of settings.toml this module owns — put together with the others by the module of the settings (domain.models).
SECTIONS = (
    Section("TRAPPER", "trapper", 20, TrapperSettings),
    Section("AGOUTI", "agouti", 40, AgoutiSettings),
)
