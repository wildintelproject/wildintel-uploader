"""Epicollect5 through pyepicollect: the definition of a project and its entries, a page at a time, with the token of the client kept while it is
valid — every read would ask for a new one, and Epicollect5 limits how many it gives."""
from __future__ import annotations

import logging
import time as monotonic
from collections.abc import Callable
from typing import Any

import pyepicollect
from pyepicollect import auth

from wildintel_uploader.modules.sources.domain.models import SourceError, Unreachable
from wildintel_uploader.modules.sources.domain.ports import Epicollect5

logger = logging.getLogger(__name__)

_TOKEN_MARGIN = 60  # seconds before it expires that it is no longer used
_TOKEN_LIFETIME = 3600  # when Epicollect5 doesn't say how long it lasts
_PAGE_SIZE = 1000
_tokens: dict[tuple[str, str], tuple[str, float]] = {}


def forget_tokens() -> None:
    _tokens.clear()


def _token(client_id: str | None, client_secret: str | None) -> tuple[str | None, bool]:
    """(token, whether it was already kept). No client, no token: a public project needs none."""
    if not (client_id and client_secret):
        return None, False
    key = (client_id, client_secret)
    kept = _tokens.get(key)
    if kept and kept[1] > monotonic.monotonic():
        return kept[0], True
    data = auth.request_token(client_id, client_secret)
    token = data.get("access_token")
    if not token:
        errors = data.get("errors") or []
        detail = errors[0].get("title") if errors and isinstance(errors[0], dict) else None
        if detail and "too many" in detail.lower():  # not a wrong client: Epicollect5 asks to wait
            raise SourceError(f"Epicollect5 says: {detail} Your client id and secret may be fine.")
        raise SourceError("Epicollect5 refused the client id and secret.")
    lifetime = data.get("expires_in")
    lifetime = lifetime if isinstance(lifetime, (int, float)) and lifetime > 0 else _TOKEN_LIFETIME
    _tokens[key] = (token, monotonic.monotonic() + max(lifetime - _TOKEN_MARGIN, 0))
    return token, False


def _ask(client_id: str | None, client_secret: str | None, request: Callable[[str | None], Any]) -> Any:
    """request(token)'s answer. A kept token that Epicollect5 no longer takes — it answers with errors — is replaced once."""
    token, kept = _token(client_id, client_secret)
    answer = request(token)
    if kept and isinstance(answer, dict) and answer.get("errors"):
        _tokens.pop((client_id or "", client_secret or ""), None)
        token, _ = _token(client_id, client_secret)
        answer = request(token)
    return answer


class PyEpicollect5(Epicollect5):
    def project(self, slug: str, client_id: str | None, client_secret: str | None) -> dict[str, Any]:
        try:
            return _ask(client_id, client_secret, lambda token: pyepicollect.api.get_project(slug, token))
        except SourceError:
            raise
        except Exception as exc:  # the network, or an answer that is not JSON
            logger.warning("Reading the Epicollect5 project %s failed: %s", slug, exc)
            raise Unreachable(str(exc)) from exc

    def entries(self, slug: str, client_id: str | None, client_secret: str | None) -> list[dict[str, Any]]:
        try:
            return self._entries(slug, client_id, client_secret)
        except SourceError:
            raise
        except Exception as exc:  # the network, or an answer that is not JSON
            logger.warning("Reading the entries of the Epicollect5 project %s failed: %s", slug, exc)
            raise Unreachable(str(exc)) from exc

    @staticmethod
    def _entries(slug: str, client_id: str | None, client_secret: str | None) -> list[dict[str, Any]]:
        entries: list[dict] = []
        page = 1
        while True:
            answer = _ask(client_id, client_secret, lambda token: pyepicollect.api.get_entries(slug, token, per_page=_PAGE_SIZE, page=page))
            if not isinstance(answer, dict) or "errors" in answer:
                errors = (answer or {}).get("errors") if isinstance(answer, dict) else None
                detail = errors[0].get("title") if errors and isinstance(errors[0], dict) else None
                raise SourceError(detail or "Epicollect5 did not answer with the entries.")
            entries += (answer.get("data") or {}).get("entries") or []
            last = int(((answer.get("meta") or {}).get("last_page")) or 1)
            if page >= last:
                return entries
            page += 1

    def forget_tokens(self) -> None:
        forget_tokens()
