"""#248: the contract of the web API — what a route answers is said by a schema of its module's api_schemas, never a view or a record of a domain
as it is; and the OpenAPI of the app, which says it, is made."""
import ast
import importlib
import inspect
import pkgutil
import typing
from pathlib import Path

import pytest
from fastapi import APIRouter
from fastapi.routing import APIRoute
from pydantic import BaseModel

import wildintel_uploader.entrypoints.api as api

API = Path(api.__file__).parent


def _routes() -> list[tuple[str, APIRoute]]:
    """Every route of the web API, with the module of entrypoints/api it is in."""
    found = []
    for module in pkgutil.iter_modules(api.__path__):
        loaded = importlib.import_module(f"{api.__name__}.{module.name}")
        for router in {id(v): v for v in vars(loaded).values() if isinstance(v, APIRouter)}.values():
            found += [(module.name, route) for route in router.routes if isinstance(route, APIRoute)]
    return found


def _types_in(kind) -> list:
    """A type and those it is made of: list[ConfigShown] is list and ConfigShown."""
    return [kind, *(t for arg in typing.get_args(kind) for t in _types_in(arg))]


def _said_by_a_schema(kind) -> bool:
    if isinstance(kind, type) and issubclass(kind, BaseModel):
        return kind.__module__.endswith(".api_schemas")
    args = typing.get_args(kind)
    return bool(args) and typing.get_origin(kind) in (list, tuple) and all(_said_by_a_schema(a) for a in args if a is not Ellipsis)


def _no_body(route: APIRoute) -> bool:
    """A file, a stream or nothing: what it answers is not JSON."""
    answer = str(inspect.unwrap(route.endpoint).__annotations__.get("return"))
    return route.response_model is None and any(kind in answer for kind in ("Response", "None"))


def _undeclared() -> set[str]:
    return {f"{method} {route.path}" for _, route in _routes() if not _no_body(route) and not _said_by_a_schema(route.response_model)
            for method in route.methods}


@pytest.mark.parametrize("path", sorted(API.glob("*.py")), ids=lambda p: p.name)
def test_no_route_turns_a_domain_object_into_its_answer_by_hand(path: Path):
    """A record or a view of a domain becomes an answer in its module's api_schemas (ConfigShown.of, record_shown…), not with asdict in a router."""
    calls = [n for n in ast.walk(ast.parse(path.read_text(encoding="utf-8"))) if isinstance(n, ast.Call)
             and (getattr(n.func, "id", None) == "asdict" or getattr(n.func, "attr", None) == "asdict")]
    assert not calls, f"{path.name} calls asdict at line {calls[0].lineno}"


def test_no_route_answers_with_a_type_of_a_domain():
    wrong = sorted(f"{route.path}: {kind.__module__}.{kind.__name__}" for _, route in _routes() for kind in _types_in(route.response_model)
                   if isinstance(kind, type) and ".domain." in kind.__module__)
    assert not wrong, wrong


def test_every_json_route_says_what_it_answers_with_a_schema():
    undeclared = sorted(_undeclared())
    assert not undeclared, f"Routes that answer without a schema of their api_schemas: {undeclared}"


def test_the_openapi_of_the_app_is_made_and_says_what_each_route_answers():
    from wildintel_uploader.web.main import app

    paths = app.openapi()["paths"]
    answered = [op for item in paths.values() for op in item.values() if isinstance(op, dict) and "responses" in op]
    assert len(answered) >= 130 and all("200" in op["responses"] or "201" in op["responses"] or "204" in op["responses"] for op in answered)
