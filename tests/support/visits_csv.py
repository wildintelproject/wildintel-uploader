"""A file of visits as the tests of before call it — by functions — over the use case the app uses (modules.visits.application.visit_file)
with the CSV file (infrastructure.csv_file), and the rules of its domain (domain.visit_file)."""
from wildintel_uploader.modules.visits.application import visit_file
from wildintel_uploader.modules.visits.application.visit_file import VisitFiles
from wildintel_uploader.modules.visits.domain.visit_file import (  # noqa: F401
    ACTIONS, CREATABLE, ERROR_LABELS, FIELDS, REQUIRED, RowError, VisitsCsvError, archived_by as _archived_by, card_code, error_label,
)
from wildintel_uploader.modules.visits.infrastructure.csv_file import CsvVisitFile


def parse_visits(text: str, locations: list[dict], kept: list[dict], mapping: dict | None = None, options: dict | None = None) -> dict:
    return visit_file.parse_visits(CsvVisitFile(), text, locations, kept, mapping, options)   # looked up when called: a test may patch it


def suggest_mapping(text: str) -> dict:
    columns = VisitFiles(CsvVisitFile()).columns(text)
    return {"columns": columns["columns"], "sample": columns["sample"], "mapping": columns["mapping"]}


def export_visits(visits: list[dict]) -> str:
    return VisitFiles(CsvVisitFile()).export(visits)
