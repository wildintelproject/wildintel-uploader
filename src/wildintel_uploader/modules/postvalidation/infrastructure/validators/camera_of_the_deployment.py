"""The images are of the camera of the deployment, as the catalog records it.

What it compares
----------------
The deployment names its camera by its label (`camera_id` of the deployment: "7B", "P800"…); the catalog has a record of it — its serial number
(`camera_id` of the record), its make (`camera_make`) and its model (`camera_model`) —, given in `context.camera`. Each image says, in its
metadata, its Make, its Model and, when ExifTool reads it, its serial number.

How a camera is told is said by the settings (VALIDATION.camera_levels), from the surest to the least: by default

    [["SerialNumber"], ["Make", "Model"], ["Model"]]

The images are compared by the first level the record has every field of. A field of the record that is empty never counts: a level that needs
it is skipped. An image that does not say a field of the level is not compared (it says nothing against the camera).

With no level the record can be compared by — no record, or a record with nothing in it —, the images are compared with the model the deployment
says (`camera_model` of the deployment), as "<make> <model>".

Examples, with the default levels
---------------------------------
1. The record has everything — serial "BR5071", make "Browning", model "BTC-8A":
   compared by SerialNumber. An image of serial "BR5071" is the camera; one of serial "BR9999" is not (a mismatch), whatever its make and model.

2. The record has no serial number, only make "Browning" and model "BTC-8A":
   SerialNumber is skipped; compared by Make + Model. An image "Browning BTC-8A" is the camera (case and spaces do not matter: "browning  btc-8a"
   too); one "Reconyx HC600" is not.

3. The record has only the model "BTC-8A":
   compared by Model. Two cameras of the same model are not told apart at this level.

4. The record is empty — no serial, make or model — and the deployment says camera_model "Browning BTC-8A":
   no level; the images are compared with "Browning BTC-8A". The page says the record has nothing to compare with, and offers to keep in it the
   make and model the images say.

5. The record is empty and the deployment says no model:
   nothing is compared, and there is no mismatch — the check finds nothing wrong, though it compared nothing. What still shows is images of more
   than one model (`camera_models_found`), which the page does not take as passed.

What it gives
-------------
- camera_mismatches: the images of another camera — {"path", "detected"}: what they say, by the fields compared.
- camera_models_found: every "<make> <model>" the images say.
- camera_by: the fields of the level compared by — empty when none could be (examples 4 and 5).
- camera_expected: what was expected of each of those fields — or {"Model": <the deployment's>} when compared with the deployment.
- camera_found: the make and the model most of the images say.
- camera_label: the label of the camera of the deployment; camera_record: its make and model as the record has them (None with no record) — what
  the page offers to complete."""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from wildintel_uploader.modules.fileinfo.domain.models import SERIAL_FIELDS, model_name
from wildintel_uploader.modules.postvalidation.domain.validators import DeploymentValidator
from wildintel_uploader.modules.fileinfo.domain.folder import MediaFolder
from wildintel_uploader.modules.postvalidation.domain.models import DeploymentContext, same_text

class CameraOfTheDeployment(DeploymentValidator):
    """Whether the images are of the camera of the deployment: by the first level of VALIDATION.camera_levels the camera's record has every
    field of, else by the model the deployment says (see the module, with examples)."""

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
