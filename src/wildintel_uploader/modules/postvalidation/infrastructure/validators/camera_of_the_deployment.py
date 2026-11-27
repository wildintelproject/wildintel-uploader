"""The images are of the camera of the deployment, as the catalog records it."""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from wildintel_uploader.modules.fileinfo.domain.models import SERIAL_FIELDS, model_name
from wildintel_uploader.modules.postvalidation.domain.validators import DeploymentValidator
from wildintel_uploader.modules.fileinfo.domain.folder import MediaFolder
from wildintel_uploader.modules.postvalidation.domain.models import DeploymentContext, same_text

class CameraOfTheDeployment(DeploymentValidator):
    key = "camera"
    label = "Camera of the deployment"
    description = ("Whether the images are of the camera of the deployment, as its record in the catalog says (serial number, make, model), by "
                   "the first level that tells a camera the record has every field of; with no record, by the model of the deployment.")

    def run(self, folder: MediaFolder, context: DeploymentContext) -> dict:
        images, camera, deployment = folder.images, context.camera, context.deployment
        read = folder.tags(images, ["Make", "Model"])
        record = {"make": (camera or {}).get("camera_make"), "model": (camera or {}).get("camera_model"), "serial": (camera or {}).get("camera_id")}

        def of_record(field: str) -> str | None:
            key = field.lower()
            return record["serial"] if key in SERIAL_FIELDS else record["make"] if key == "make" else record["model"] if key == "model" else None

        chosen = next((level for level in context.camera_levels if all(f.lower() in SERIAL_FIELDS | {"make", "model"} for f in level)
                       and all(of_record(f) for f in level)), None) if camera else None
        serial_of = folder.cameras() if chosen and any(f.lower() in SERIAL_FIELDS for f in chosen) else {}

        def of_image(path: Path, field: str) -> str | None:
            return serial_of[path].camera_id if field.lower() in SERIAL_FIELDS else read[path].get("Make" if field.lower() == "make" else "Model")

        mismatches: list[dict] = []
        for path in images:
            if chosen:
                found = [of_image(path, f) for f in chosen]
                if not all(found):
                    continue   # it does not say: nothing to compare
                if not all(same_text(v, of_record(f)) for v, f in zip(found, chosen)):
                    mismatches.append({"path": folder.relative(path), "detected": " ".join(str(v) for v in found)})
            else:
                model = model_name(read[path].get("Make"), read[path].get("Model"))
                if model and deployment.camera_model and not same_text(model, deployment.camera_model):
                    mismatches.append({"path": folder.relative(path), "detected": model})
        pairs = Counter((read[p].get("Make"), read[p].get("Model")) for p in images if read[p].get("Model"))
        make, model = pairs.most_common(1)[0][0] if pairs else (None, None)
        return {
            "camera_mismatches": mismatches,
            "camera_models_found": sorted({m for m in (model_name(read[p].get("Make"), read[p].get("Model")) for p in images) if m}),
            "camera_by": list(chosen) if chosen else [],
            "camera_expected": {f: of_record(f) for f in chosen} if chosen else ({"Model": deployment.camera_model} if deployment.camera_model else {}),
            "camera_found": {"make": make, "model": model},
            "camera_label": (camera or {}).get("label"),
            "camera_record": {"make": record["make"], "model": record["model"]} if camera else None,
        }
