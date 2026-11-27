"""Copying a memory card as the tests of before call it — by the card's path — over the use case the app uses
(modules.deployments.application.cards.CardCopying), raising what the copy refuses (CardCopyError)."""
from wildintel_uploader.modules.deployments.application.cards import CardCopying
from wildintel_uploader.modules.deployments.domain.cards import CardCopyError  # noqa: F401
from wildintel_uploader.modules.deployments.infrastructure.memory_cards import CardOnDisk, CopiesInTemp, base_dir  # noqa: F401


def _cards() -> CardCopying:
    return CardCopying(CardOnDisk(), CopiesInTemp())


def copy_card(card: str):
    return _cards().copy(card)


def discard(copy: str) -> bool:
    return _cards().discard(copy)


def eject(card: str) -> dict:
    return _cards().eject(card)
