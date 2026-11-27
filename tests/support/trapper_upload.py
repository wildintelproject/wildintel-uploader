"""The upload to TRAPPER as the tests of before call it — function by function — over the use cases and the adapters the app uses
(modules.uploaders: TrapperUploads, put together by entrypoints.wiring)."""
from pathlib import Path

from wildintel_uploader.entrypoints.wiring import trapper_uploads
from wildintel_uploader.modules.uploaders.domain import trapper as rules
from wildintel_uploader.modules.uploaders.domain.models import UploaderError as TrapperUploadError  # noqa: F401
from wildintel_uploader.modules.uploaders.infrastructure import trapper_service  # noqa: F401
from wildintel_uploader.modules.uploaders.infrastructure.packages import PackagesOnDisk
from wildintel_uploader.modules.uploaders.infrastructure.trapper import list_collections  # noqa: F401
from wildintel_uploader.modules.uploaders.infrastructure.trapper_site import uploader_class as _uploader_class  # noqa: F401

trapper_collection_name = rules.collection_name
location_access_problem = rules.location_access_problem


def find_research_project(credentials, record: dict) -> int:
    return trapper_uploads().research_project_pk(credentials, record)


def resolve_classification_project(credentials, research_project_pk: int, chosen: int | None = None) -> dict:
    return trapper_uploads().classification_project(credentials, research_project_pk, chosen)


def ensure_location(credentials, research_project_pk: int, deployment, *, timezone_name: str, ignore_dst: bool, work_dir: Path) -> bool:
    return trapper_uploads().ensure_location(credentials, research_project_pk, deployment, timezone_name, ignore_dst)


def ensure_deployment(credentials, research_project_pk: int, deployment, *, timezone_name: str, ignore_dst: bool, work_dir: Path) -> bool:
    return trapper_uploads().ensure_deployment(credentials, research_project_pk, deployment, timezone_name, ignore_dst)


def build_packages(deployment_dir: Path, collection: str, deployment_id: str, log: dict, **kw) -> list[dict]:
    return [{"yaml": p.yaml, "zip": p.zip, "files": p.files} for p in trapper_uploads().build(deployment_dir, collection, deployment_id, log, **kw)]


def upsert_deployments_csv(path: Path, deployment, log: dict) -> dict:
    return PackagesOnDisk().upsert_csv(path, rules.csv_row(deployment, log))


def upload_stream(*args, **kwargs):
    return trapper_uploads().upload(*args, **kwargs)


def check_access(credentials, research_project: dict, location_ids=None, **kwargs) -> list[dict]:
    return trapper_uploads().check_access(credentials, research_project, location_ids, **kwargs)


def check_selection(credentials, research_project: dict, collection: str | None = None, **kwargs) -> list[dict]:
    return trapper_uploads().check_selection(credentials, research_project, collection, **kwargs)
