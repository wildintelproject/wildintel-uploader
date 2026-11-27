"""The sources of visits — each a class in a file of its own —, and their registry."""
from __future__ import annotations

from wildintel_uploader.modules.sources.domain.ports import VisitSource
from wildintel_uploader.modules.sources.infrastructure.sources.epicollect_api import EpicollectApi
from wildintel_uploader.modules.sources.infrastructure.sources.epicollect_csv import EpicollectFormCsv

SOURCES: tuple[type[VisitSource], ...] = (EpicollectApi, EpicollectFormCsv)
