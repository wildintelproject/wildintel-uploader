"""The packages of an upload on disk — a zip of the images and the yaml that describes them, as TRAPPER reads them —, the deployments csv of a
collection, and a deployment kept in its collection's folder as an upload reads and marks it."""
from __future__ import annotations

import csv
import json
import zipfile
from collections.abc import Callable
from pathlib import Path

from wildintel_uploader.modules.deployments.domain.naming import DEPLOYMENT_METADATA_FILE
from wildintel_uploader.modules.preprocessing.domain.models import PREPROCESSING_LOG_FILE
from wildintel_uploader.modules.uploaders.domain import trapper as rules
from wildintel_uploader.modules.uploaders.domain.ports import Deployment, KeptDeployment, Package, PackagePart, Packages

UPLOAD_LOG_FILE = "upload.json"


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def size_of(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _resource(path: Path, name: str, date: str) -> dict:
    from PIL import Image
    try:
        with Image.open(path) as img:
            width, height, mime = img.width, img.height, Image.MIME.get(img.format or "", "application/octet-stream")
    except Exception:
        width, height, mime = None, None, "application/octet-stream"
    return rules.resource(name, date, mime, width, height, path.stat().st_size)


class PackagesOnDisk(Packages):
    def build(self, output_dir: Path, parts: list[PackagePart], progress: Callable[[int, int], None]) -> list[Package]:
        import yaml

        output_dir.mkdir(parents=True, exist_ok=True)
        total = sum(len(p.entries) for p in parts)
        packed = 0
        out = []
        for part in parts:
            files = [(part.deployment_dir / e["name"], e) for e in part.entries]
            definition = rules.package_definition(part.collection, part.project_id, part.timezone, part.ignore_dst, part.named,
                                                  [_resource(path, e["name"], e["date"]) for path, e in files])
            yaml_path, zip_path = output_dir / f"{part.base}.yaml", output_dir / f"{part.base}.zip"
            yaml_path.write_text(yaml.dump(definition, sort_keys=False, allow_unicode=True), encoding="utf-8")
            with zipfile.ZipFile(zip_path, "w", allowZip64=True) as z:
                for path, _ in files:
                    z.write(path, f"{part.collection}/{part.named}/{path.name}")
                    packed += 1
                    progress(packed, total)
            out.append(Package(yaml_path, zip_path, len(files)))
        return out

    def size(self, paths: list[Path]) -> int:
        return sum(size_of(p) for p in paths)

    def file_sizes(self, paths: list[Path]) -> dict[str, int]:
        return {p.name: p.stat().st_size for p in paths}

    def upsert_csv(self, path: Path, row: dict) -> dict:
        rows: dict[str, dict] = {}
        if path.is_file():
            with path.open(newline="", encoding="utf-8") as f:
                for existing in csv.DictReader(f):
                    if existing.get("deploymentID"):
                        rows[existing["deploymentID"]] = existing
        action = "added" if row["deploymentID"] not in rows else "updated"
        rows[row["deploymentID"]] = row
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=rules.CSV_FIELDS, extrasaction="ignore")
            writer.writeheader()
            for key in sorted(rows):
                writer.writerow(rows[key])
        return {"path": str(path), "action": action, "rows": len(rows)}

    def remove_from_csv(self, path: Path, deployment_id: str) -> None:
        if not path.is_file():
            return
        with path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fields = reader.fieldnames or []
            rows = [row for row in reader if row.get("deploymentID") and row["deploymentID"] != deployment_id]
        if not rows:
            path.unlink()
            return
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)

    def remove(self, packages: list[Package], output_dir: Path) -> None:
        for package in packages:
            package.zip.unlink(missing_ok=True)
            package.yaml.unlink(missing_ok=True)
        try:
            output_dir.rmdir()   # only if nothing else is left in it
        except OSError:
            pass


class DeploymentFolder(KeptDeployment):
    def metadata(self, deployment_dir: Path) -> object:
        return read_json(deployment_dir / DEPLOYMENT_METADATA_FILE)

    def preprocessing(self, deployment_dir: Path) -> object:
        return read_json(deployment_dir / PREPROCESSING_LOG_FILE)

    def as_deployment(self, metadata: dict) -> Deployment:
        from wildintel_uploader.shared.camtrap import DeploymentFields
        return DeploymentFields.model_validate(metadata)

    def missing(self, deployment_dir: Path, names: list[str]) -> list[str]:
        return [n for n in names if not (deployment_dir / n).is_file()]

    def sizes(self, deployment_dir: Path, names: list[str]) -> list[int]:
        return [(deployment_dir / n).stat().st_size for n in names]

    def mark_uploaded(self, deployment_dir: Path, record: dict) -> None:
        (deployment_dir / UPLOAD_LOG_FILE).write_text(json.dumps(record, indent=2), encoding="utf-8")
