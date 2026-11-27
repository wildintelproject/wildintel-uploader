"""The statistical checks: this revision against the previous ones of its location in the research project — the number of images, of sequences,
and how long the sequences are —, as statistics_service works them out. Without a research project, or with too few revisions, they say so and
pass."""
from __future__ import annotations

from datetime import timezone

from wildintel_uploader.modules.fileinfo.domain.folder import MediaFolder
from wildintel_uploader.modules.postvalidation.domain.models import DeploymentContext
from wildintel_uploader.modules.postvalidation.domain.validators import DeploymentValidator

# What the statistical checks mean by a sequence and by similar, as the page sends them (StatisticsParams).
_DEFAULTS = {"sequence_gap_seconds": 60.0, "min_revisions": 2, "method": "median", "image_count_tolerance": 50.0, "sequence_count_tolerance": 50.0,
             "sequence_length_tolerance": 50.0}


class _Statistic(DeploymentValidator):
    statistical = True

    def run(self, folder: MediaFolder, context: DeploymentContext) -> dict:
        from wildintel_uploader.core import config
        from wildintel_uploader.core.services import statistics_service
        params = {**_DEFAULTS, **(context.statistics or {})}
        stamps = sorted(t.replace(tzinfo=timezone.utc).timestamp() for t in folder.dates().values() if t is not None)
        current = statistics_service.DeploymentTimes(len(folder.images), stamps)
        return statistics_service.statistical_checks(
            current, config.collections_dir(), context.research_project_id, context.deployment.deployment_id, frozenset({self.key}),
            sequence_gap_seconds=params["sequence_gap_seconds"], min_revisions=params["min_revisions"], method=params["method"],
            tolerances={key: params[f"{key}_tolerance"] for key in ("image_count", "sequence_count", "sequence_length")})


class ImageCount(_Statistic):
    key = "image_count"
    label = "Number of images"
    description = "The number of images is like the previous revisions' of the location."


class SequenceCount(_Statistic):
    key = "sequence_count"
    label = "Number of sequences"
    description = "The number of sequences is like the previous revisions' of the location."


class SequenceLength(_Statistic):
    key = "sequence_length"
    label = "Length of the sequences"
    description = "How many images a sequence has is like in the previous revisions of the location."
