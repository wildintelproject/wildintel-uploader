"""What the adapters of this module that are still functions of the code of before need from outside it — another module through its
contract, the settings —, plugged in where the app is put together (entrypoints.wiring; see shared.plugs)."""
from __future__ import annotations

from wildintel_uploader.modules.settings.domain.ports import StoredSettings
from wildintel_uploader.shared.plugs import Plug


config: Plug[StoredSettings] = Plug("the settings as settings.toml keeps them")
