"""The visits of the Epicollect5 project of the settings, read through its API: each entry of the form of the field flow is a visit, its inputs
found by their labels (VISIT_QUESTIONS)."""
from __future__ import annotations

import csv
import io

from wildintel_uploader.modules.sources.domain.models import VISIT_COLUMNS, VISIT_QUESTIONS, SourceError, Unreachable, label_key, parse_project, visit_row
from wildintel_uploader.modules.sources.domain.ports import Epicollect5, VisitRows, VisitSource
from wildintel_uploader.modules.sources.domain.settings import Epicollect5Settings
from wildintel_uploader.modules.settings.domain.rules import revealed


def project_form(epicollect: Epicollect5, settings: Epicollect5Settings) -> dict:
    """The inputs of the project of the settings."""
    if not settings.project_slug:
        raise SourceError("There is no Epicollect5 project saved yet — set its slug in Settings › Epicollect5.")
    return parse_project(epicollect.project(settings.project_slug, settings.client_id, revealed(settings.client_secret)))


class EpicollectApi(VisitSource):
    key = "epicollect-api"
    label = "Epicollect5 (the project of the settings)"

    def visits(self, text: str | None, epicollect: Epicollect5, settings: Epicollect5Settings) -> VisitRows:
        form = project_form(epicollect, settings)
        labels = {label_key(i.get("label", "")) for i in form["inputs"]}
        refs = {VISIT_QUESTIONS[label_key(i["label"])]: i["ref"] for i in form["inputs"] if label_key(i.get("label", "")) in VISIT_QUESTIONS}
        missing = [name for name in ("locationID", "Date", "Status of the camera") if label_key(name) not in labels]
        if missing:
            raise SourceError(f"The form of the project does not have the questions of a visit: {', '.join(missing)}.")
        try:
            entries = epicollect.entries(settings.project_slug or "", settings.client_id, revealed(settings.client_secret))
        except Unreachable as exc:
            raise SourceError(f"Could not read the entries from Epicollect5: {exc.detail}") from exc
        out = io.StringIO()
        writer = csv.DictWriter(out, fieldnames=list(VISIT_COLUMNS), lineterminator="\n")
        writer.writeheader()
        for entry in entries:
            writer.writerow(visit_row(entry, refs))
        # the entries have a date and a time typed and when they were created: the settings of the field log choose (FIELDLOG.time_source)
        return VisitRows(csv=out.getvalue(), time_source=None, from_form=True)
