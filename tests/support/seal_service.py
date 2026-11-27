"""The seal of a deployment as the tests of before call it, over the use case the app uses (modules.deployments.application.seal.Sealing)."""
from pathlib import Path

from wildintel_uploader.modules.deployments.domain.seal import SEAL_FILE, VERSION  # noqa: F401
from wildintel_uploader.modules.deployments.infrastructure.sealed_folder import images_of as _images_of  # noqa: F401


def _sealing():
    from wildintel_uploader.entrypoints.wiring import sealing
    return sealing()


def seal(source: Path, dest: Path, deployment, **kwargs) -> dict:
    return _sealing().seal(source, dest, deployment, **kwargs)


def run_checks(source: Path, dest: Path, deployment) -> dict:
    return _sealing().run_checks(source, dest, deployment)


def verify(dest: Path) -> dict:
    return _sealing().verify(dest)
