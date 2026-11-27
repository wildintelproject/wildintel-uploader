"""The use cases of the sources: the visits of a source, the form of the Epicollect5 project, whether one can be read, and the entries that say the
details of the deployments of some locations."""
from __future__ import annotations

from wildintel_uploader.modules.sources.domain.models import SourceError, entry_fields, parse_project, unmapped_notes
from wildintel_uploader.modules.sources.domain.ports import Epicollect5, SourceSettings, SourcesService, VisitRows, VisitSource
from wildintel_uploader.modules.sources.domain.settings import Epicollect5Settings


class SourcesUseCases(SourcesService):
    """Over the sources it is given (infrastructure/sources, put together in wiring)."""

    def __init__(self, epicollect: Epicollect5, settings: SourceSettings, sources: tuple[type[VisitSource], ...], *, form_columns, form_error) -> None:
        self._epicollect, self._settings, self._sources = epicollect, settings, sources
        self._form_columns, self._form_error = form_columns, form_error

    def _epicollect5(self, settings: Epicollect5Settings | None) -> Epicollect5Settings:
        return settings if settings is not None else self._settings.epicollect5()

    def sources(self) -> list[VisitSource]:
        return [s() for s in self._sources]

    def visits(self, key: str, text: str | None = None, settings: Epicollect5Settings | None = None) -> VisitRows:
        source = next((s() for s in self._sources if s.key == key), None)
        if source is None:
            raise SourceError(f"There is no source of visits called {key!r}.")
        return source.visits(text, self._epicollect, self._epicollect5(settings))

    def project_form(self, settings: Epicollect5Settings | None = None) -> dict:
        cfg = self._epicollect5(settings)
        if not cfg.project_slug:
            raise SourceError("There is no Epicollect5 project saved yet — set its slug in Settings › Epicollect5.")
        return parse_project(self._epicollect.project(cfg.project_slug, cfg.client_id, cfg.client_secret))

    def test_connection(self, slug: str | None, client_id: str | None, client_secret: str | None, settings: Epicollect5Settings | None = None) -> dict:
        saved = self._epicollect5(settings)
        slug, client_id, client_secret = (slug or "").strip(), (client_id or "").strip() or None, client_secret or None
        if not slug:
            raise SourceError("Type the project's slug first.")
        if client_secret is None and client_id and client_id == saved.client_id:
            client_secret = saved.client_secret   # the settings page leaves it blank to keep it
        if client_id and not client_secret:
            raise SourceError("A client id needs its secret too.")
        parsed = parse_project(self._epicollect.project(slug, client_id, client_secret))
        return {"ok": True, "project": parsed["project"]["name"], "slug": parsed["project"]["slug"],
                "forms": len({i["form"] for i in parsed["inputs"]}), "inputs": len(parsed["inputs"])}

    def deployment_entries(self, location_ids: list[str], revision: int | None, settings: Epicollect5Settings | None = None) -> dict[str, list[dict]]:
        cfg = self._epicollect5(settings)
        if not cfg.enabled:
            raise SourceError("Epicollect5 is turned off — turn it on in Settings › Epicollect5.")
        if not cfg.project_slug:
            raise SourceError("There is no Epicollect5 project saved yet — set its slug in Settings › Epicollect5.")
        mapping = {k: v for k, v in cfg.mapping.items() if v}
        if "location_id" not in mapping:
            raise SourceError("The location id is not mapped yet — relate it to an input of the form in Settings › Epicollect5 › Mapping.")
        found: dict[str, list[dict]] = {w: [] for w in (loc.strip().lower() for loc in location_ids) if w}
        entries = self._epicollect.entries(cfg.project_slug, cfg.client_id, cfg.client_secret)
        inputs = parse_project(self._epicollect.project(cfg.project_slug, cfg.client_id, cfg.client_secret))["inputs"] if cfg.unmapped_to_comments else []
        for entry in entries:
            fields = entry_fields(entry, mapping)
            location = (fields.get("location_id") or "").lower()
            if location not in found:
                continue
            if revision is not None and "revision" in mapping and fields.get("revision") != revision:
                continue
            if cfg.unmapped_to_comments and (notes := unmapped_notes(entry, inputs, mapping)):
                fields["comments"] = "\n".join(filter(None, [fields.get("comments"), notes]))
            found[location].append({"uuid": entry.get("ec5_uuid"), "title": entry.get("title") or "", "created_at": entry.get("created_at") or "",
                                    "fields": fields})
        return {location: sorted(items, key=lambda e: e["created_at"], reverse=True) for location, items in found.items()}

    def form_columns(self, text: str) -> dict[str, str]:
        return self._form_columns(text)

    def form_error(self, text: str) -> str | None:
        return self._form_error(text)

    def forget_tokens(self) -> None:
        self._epicollect.forget_tokens()
