"""#248: the contract of the web API — what a route answers is said by a schema of its module's api_schemas, never a view or a record of a domain
as it is. The routes that do not say it yet are listed (routes_still_undeclared.txt), and the list only shrinks."""
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
STILL_UNDECLARED = Path(__file__).with_name("routes_still_undeclared.txt")


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


def _listed() -> set[str]:
    return {line.strip() for line in STILL_UNDECLARED.read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")}


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
    new = sorted(_undeclared() - _listed())
    assert not new, f"Routes that answer without a schema of their api_schemas: {new}"


def test_the_list_of_the_routes_still_undeclared_only_shrinks():
    """A route listed is one there is, and one that still does not say what it answers: once it does, it is taken off the list."""
    stale = sorted(_listed() - _undeclared())
    assert not stale, f"Take these off routes_still_undeclared.txt — they say what they answer now, or are gone: {stale}"
