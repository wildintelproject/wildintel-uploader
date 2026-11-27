"""The dates of the images against those of the deployment (#208)."""
from __future__ import annotations

from datetime import timedelta

from wildintel_uploader.modules.postvalidation.domain.validators import DeploymentValidator
from wildintel_uploader.modules.fileinfo.domain.folder import MediaFolder
from wildintel_uploader.modules.postvalidation.domain.models import DeploymentContext, natural_key, parse_iso

class TimeRange(DeploymentValidator):
    key = "time_range"
    label = "Dates of the images"
    description = ("Whether the dates of the images fit the deployment, with a leeway (#208): an image before the start or after the collection, "
                   "and a first image long after the start, are wrong; a last image long before the collection is only said (stopped early).")

    def run(self, folder: MediaFolder, context: DeploymentContext) -> dict:
        return {"tolerance_hours": context.tolerance_hours, **self._dates(folder, context)}

    @staticmethod
    def _dates(folder: MediaFolder, context: DeploymentContext) -> dict:
        deployment, tolerance_hours = context.deployment, context.tolerance_hours
        start, end = parse_iso(deployment.start_date), parse_iso(deployment.end_date)
        tolerance, label = timedelta(hours=tolerance_hours), f"{tolerance_hours:g}h"
        if start is None or end is None:
            return {"out_of_range": []}
        read = folder.dates()
        dated = sorted(((dt, p) for p in folder.images if (dt := read[p]) is not None), key=lambda item: (item[0], natural_key(item[1].relative_to(folder.root))))
        out: list[dict] = []
        window = f"{start.isoformat()} – {end.isoformat()} ± {label}"
        for dt, path in dated:
            if dt < start - tolerance:
                out.append({"path": folder.relative(path), "date": dt.isoformat(), "rule": "before_start", "expected": window})
            elif dt > end + tolerance:
                out.append({"path": folder.relative(path), "date": dt.isoformat(), "rule": "after_end", "expected": window})
        result: dict = {"out_of_range": out}
        if dated:   # when the images say they were taken, all of them: for the dates of the deployment to be compared with at a glance
            result["images_span"] = {"first": dated[0][0].isoformat(), "last": dated[-1][0].isoformat(), "dated": len(dated)}
        if dated and start - tolerance <= dated[0][0] and dated[0][0] > start + tolerance:
            first_dt, first = dated[0]
            out.insert(0, {"path": folder.relative(first), "date": first_dt.isoformat(), "rule": "first", "expected": f"{start.isoformat()} ± {label}"})
        if dated and end - tolerance > dated[-1][0] >= start - tolerance:
            last_dt, last = dated[-1]
            visit = context.visit or {}
            reason = ("card_full" if str(visit.get("collected_card_status") or "").lower() in ("cardfull", "carfull")
                      else "no_batteries" if str(visit.get("collected_battery_status") or "").lower() == "nobatteries" else None)
            result["stopped_early"] = {"path": folder.relative(last), "date": last_dt.isoformat(), "collected": end.isoformat(),
                                       "days": round((end - last_dt).total_seconds() / 86400, 1), "reason": reason}
        return result
