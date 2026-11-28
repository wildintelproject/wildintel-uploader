"""The deployments: the memory cards, the collections folder, the import, the seal, the repair and the statistics."""
from __future__ import annotations

from dishka import Provider, Scope, alias, provide

from wildintel_uploader.entrypoints import config
from wildintel_uploader.modules.deployments.application.cards import CardCopying
from wildintel_uploader.modules.deployments.application.imports import Importing
from wildintel_uploader.modules.deployments.application.photos import DeploymentPhotos
from wildintel_uploader.modules.deployments.application.repair import Repairing
from wildintel_uploader.modules.deployments.application.seal import Sealing
from wildintel_uploader.modules.deployments.application.sessions import WizardSessions
from wildintel_uploader.modules.deployments.application.statistics import RevisionStatistics
from wildintel_uploader.modules.deployments.application.use_cases import DeploymentsUseCases
from wildintel_uploader.modules.deployments.domain.ports import (
    DeploymentsCards, DeploymentsCollections, DeploymentsImporting, DeploymentsPhotos, DeploymentsRepairing, DeploymentsScanning, DeploymentsService,
    DeploymentsSessions, DeploymentsStatistics,
)
from wildintel_uploader.modules.deployments.infrastructure.collection_layout import LayoutOfTheCollections
from wildintel_uploader.modules.deployments.infrastructure.collections_folder import CollectionFolders as DeploymentFolders
from wildintel_uploader.modules.deployments.infrastructure.import_folder import ImportFolderOnDisk
from wildintel_uploader.modules.deployments.infrastructure.memory_cards import CardOnDisk, CopiesInTemp
from wildintel_uploader.modules.deployments.infrastructure.photo_folder import PhotosOnDisk
from wildintel_uploader.modules.deployments.infrastructure.repair_folder import RepairFolderOnDisk
from wildintel_uploader.modules.deployments.infrastructure.revision_folders import RevisionFoldersOnDisk, StatisticsInUse
from wildintel_uploader.modules.deployments.infrastructure.sealed_folder import ChecksInUse, DeploymentSealFolder
from wildintel_uploader.modules.deployments.infrastructure.session_folder import SessionsOnDisk
from wildintel_uploader.modules.settings.domain.ports import SettingsService
from wildintel_uploader.entrypoints import wiring as w   # the other factories, asked when called


def build_deployments(settings: SettingsService | None = None) -> DeploymentsService:
    """The deployments: the memory cards, the collections folder, the import, the revisions, the photos and the wizard's sessions over their
    adapters, with the visits and the preprocessing through their contracts."""
    settings = settings or w.build_settings()
    return DeploymentsUseCases(CardCopying(CardOnDisk(), CopiesInTemp()), DeploymentFolders(lambda: config.collections_dir(), w.catalog_of, sealing), revision_statistics(),
                               DeploymentPhotos(PhotosOnDisk(lambda: config.collections_dir())), visits=w.build_visits(settings=settings),
                               preprocessing=w.build_preprocessing(), repairs=repairing(), statistics=revision_statistics(),
                               sessions=WizardSessions(SessionsOnDisk(lambda: config.get_sessions_dir(), lambda: config.legacy_sessions_dir())), layout=LayoutOfTheCollections(importing), imports=importing())


def importing() -> Importing:
    """Bringing a folder of images into a collection of the collections folder of the settings: the images through modules.fileinfo, then sealed."""
    return Importing(ImportFolderOnDisk(lambda: config.collections_dir()), w.file_info, sealing,
                     exif_fields=lambda: config.load_settings().VALIDATION.exif_fields)


def sealing() -> Sealing:
    """The seal of the deployments: the checks the settings turn on, the prevalidation's and the postvalidation's through their contracts."""
    return Sealing(DeploymentSealFolder(), ChecksInUse(w.section("VALIDATION"), w.section("POSTVALIDATION")), prevalidation=w.build_prevalidation, postvalidation=w.build_postvalidation,
                   catalog_of=w.catalog_of, revisions_of=lambda root: RevisionStatistics(RevisionFoldersOnDisk(lambda: root, w.file_info), StatisticsInUse(w.section("POSTVALIDATION"))))


def repairing() -> Repairing:
    """Repairing the deployments kept in the collections folder of the settings: sealed again, reported, the catalog through its contract."""
    return Repairing(RepairFolderOnDisk(lambda: config.collections_dir(), w.file_info), sealing, w.build_reports, lambda: w.catalog_of(config.collections_dir()),
                     lambda: config.load_settings().PREPROCESSING.model_dump())


def revision_statistics() -> RevisionStatistics:
    """The statistics of the deployments kept in the collections folder of the settings, as POSTVALIDATION says."""
    return RevisionStatistics(RevisionFoldersOnDisk(lambda: config.collections_dir(), w.file_info), StatisticsInUse(w.section("POSTVALIDATION")))


class DeploymentsProvider(Provider):
    """The deployments."""

    @provide(scope=Scope.REQUEST)
    def service(self, settings: SettingsService) -> DeploymentsService:
        return build_deployments(settings)

    # each part of the contract, for whoever needs only that one: the same service of the request
    cards = alias(source=DeploymentsService, provides=DeploymentsCards)
    scanning = alias(source=DeploymentsService, provides=DeploymentsScanning)
    collections = alias(source=DeploymentsService, provides=DeploymentsCollections)
    importing = alias(source=DeploymentsService, provides=DeploymentsImporting)
    repairing = alias(source=DeploymentsService, provides=DeploymentsRepairing)
    statistics = alias(source=DeploymentsService, provides=DeploymentsStatistics)
    sessions = alias(source=DeploymentsService, provides=DeploymentsSessions)
    photos = alias(source=DeploymentsService, provides=DeploymentsPhotos)
