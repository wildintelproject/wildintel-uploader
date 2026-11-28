"""The statistical checks: this revision against the previous ones of its location in the research project — the number of images, of sequences,
and how long the sequences are (domain.statistics) —, the previous revisions given in the context. Without a research project, or with too few revisions, they say so and
pass."""
from __future__ import annotations

from datetime import timezone

from wildintel_uploader.modules.fileinfo.domain.folder import MediaFolder
from wildintel_uploader.modules.postvalidation.domain.models import DeploymentContext
from wildintel_uploader.modules.postvalidation.domain.statistics import DeploymentTimes, judge
from wildintel_uploader.modules.postvalidation.domain.validators import DeploymentValidator

class _Statistic(DeploymentValidator):
    statistical = True

    def run(self, folder: MediaFolder, context: DeploymentContext) -> dict:
        """This revision against the previous ones of its location, for the statistic of the class (its ``key``).

        The images that have a date are cut into sequences — images at most ``sequence_gap_seconds`` apart —, and the
        value of this revision (the number of images, of sequences, or the mean images per sequence) is compared with
        those of the previous revisions that have images, by ``method`` and the tolerance of the statistic. With fewer
        than ``min_revisions`` of them it is not judged, and passes.

        Args:
            folder: The folder of the deployment's images.
            context: ``previous``, the previous revisions of the location; ``statistics``, what a sequence and similar
                mean; and ``deployment.deployment_id``.

        Returns:
            ``{key: {"ok", "skipped", "value", "reference", "lower", "upper", "previous", "message", "history"}}``:
            whether it is similar, whether it was not judged (too few revisions — then ``ok``), the value of this
            revision, the reference of the previous ones (by the method) and the bounds allowed (None when not judged),
            how many previous revisions there are, what the page says, and the value of each previous revision —
            ``{"revision", "deployment_id", "value"}``.

        Example:
            The number of images, by the median and ±50%, against three revisions::

                {"image_count": {
                    "ok": False, "skipped": False, "value": 312.0, "reference": 1200.0, "lower": 600.0, "upper": 1800.0,
                    "previous": 3,
                    "message": "The number of images (312) is not similar to the median of the 3 previous revision(s) of "
                               "DONA_01 (allowed 600–1800, ±50%).",
                    "history": [{"revision": 10, "deployment_id": "R0010-DONA_01", "value": 1150.0},
                                {"revision": 11, "deployment_id": "R0011-DONA_01", "value": 1200.0},
                                {"revision": 12, "deployment_id": "R0012-DONA_01", "value": 1310.0}],
                }}
        """
        params = context.statistics
        stamps = sorted(t.replace(tzinfo=timezone.utc).timestamp() for t in folder.dates().values() if t is not None)
        return judge(DeploymentTimes(len(folder.images), stamps), list(context.previous), context.deployment.deployment_id, frozenset({self.key}),
                     sequence_gap_seconds=params.sequence_gap_seconds, min_revisions=params.min_revisions, method=params.method,
                     tolerances={key: params.tolerance(key) for key in ("image_count", "sequence_count", "sequence_length")})

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
