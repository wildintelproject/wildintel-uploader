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
        """Whether the dates of the images fit the deployment, with a leeway (#208).

        Args:
            folder: The folder of the deployment's images.
            context: ``deployment.start_date`` and ``end_date`` (ISO 8601, read as the camera's wall clock),
                ``tolerance_hours``, the leeway, and ``visit`` (whether it found the card full or the batteries flat, said
                when the camera stopped early).

        Returns:
            ``{"tolerance_hours": float, ...}`` — the leeway, and what ``_dates`` found.

        Example:
            The deployment ran from 2026-09-01 12:00 to 2026-10-19 10:00; one image has the date of a clock never set,
            and the last one is of two weeks before the collection — the visit found the card full::

                {
                    "tolerance_hours": 1.0,
                    "out_of_range": [{"path": "IMG_0001.JPG", "date": "2026-08-02T09:14:00", "rule": "before_start",
                                      "expected": "2026-09-01T12:00:00 – 2026-10-19T10:00:00 ± 1h"}],
                    "images_span": {"first": "2026-08-02T09:14:00", "last": "2026-10-05T18:40:00", "dated": 1203},
                    "stopped_early": {"path": "IMG_1203.JPG", "date": "2026-10-05T18:40:00",
                                      "collected": "2026-10-19T10:00:00", "days": 13.6, "reason": "card_full"},
                }
        """
        return {"tolerance_hours": context.tolerance_hours, **self._dates(folder, context)}

    @staticmethod
    def _dates(folder: MediaFolder, context: DeploymentContext) -> dict:
        """The images dated out of the deployment, and how their dates span.

        The images with no date are not compared. Nothing is compared when the deployment has no start or no end date:
        then only ``out_of_range``, empty.

        Args:
            folder: The folder of the deployment's images.
            context: As ``run`` reads it.

        Returns:
            A dict with:

            - ``out_of_range``, always: the images that do not fit, each ``{"path", "date", "rule", "expected"}`` — its
              path relative to the folder, its date, why and the window it should be in. ``rule`` is ``before_start``
              (taken before the start, less the leeway), ``after_end`` (after the collection, plus the leeway) or
              ``first`` (the first image, taken after the start plus the leeway: the camera began late; it goes first).
            - ``images_span``, when an image has a date: ``{"first", "last", "dated"}`` — the date of the first image
              and of the last, and how many have one.
            - ``stopped_early``, when the last image is before the collection, less the leeway (and not before the
              start): ``{"path", "date", "collected", "days", "reason"}`` — the last image, its date, the collection, how
              many days before it the camera stopped, and why, if the visit says it: ``card_full``, ``no_batteries`` or
              None. It is only said: it is not wrong.

        Example:
            See ``run``, without its ``tolerance_hours``.
        """
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
