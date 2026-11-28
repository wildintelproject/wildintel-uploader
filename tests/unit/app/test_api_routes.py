"""#248: the web API, put together from the entry points of the modules, still answers every address the frontend calls — and describes itself
(OpenAPI, what /docs shows)."""
import re
from pathlib import Path

from wildintel_uploader.web.main import app

FRONTEND_API = Path(__file__).resolve().parents[3] / "frontend" / "src" / "api.ts"


def test_the_api_describes_itself():
    assert len(app.openapi()["paths"]) > 100


def test_every_address_the_frontend_calls_is_answered():
    paths = app.openapi()["paths"]
    called = sorted({re.sub(r"\$\{[^}]+\}", "x", m) for m in re.findall(r"['`](/api/[^'`?]+)", FRONTEND_API.read_text(encoding="utf-8"))})
    answered = [re.compile("^" + re.sub(r"\{[^}]+\}", "[^/]+", p) + "$") for p in paths]
    assert called and [c for c in called if not any(a.match(c) for a in answered)] == []
