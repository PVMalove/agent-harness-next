"""Dependency boundary of the console: only harness/console/backend/api imports the web framework, and
the retired h11 transport and Jinja2 are imported nowhere."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / "harness"
CONSOLE = HARNESS / "console"
API = CONSOLE / "backend" / "api"

FRAMEWORK = frozenset({"fastapi", "starlette", "uvicorn", "pydantic"})
RETIRED = frozenset({"h11", "jinja2"})
ROUTE_MODULES = ("app.py", "websocket.py", "static.py")
# Routes reach the services only through the request router.
SERVICE_INTERNALS = frozenset(
    {
        "harness.console.backend.application.jobs",
        "harness.console.kernel.runner",
        "harness.console.kernel.process_tree",
        "harness.console.ledger_lock",
        "harness.console.backend.infrastructure.event_journal",
        "harness.orchestration.coordinator",
    }
)


def imported_modules(source: str, package: str = "") -> set[str]:
    """Every module the source imports at any nesting level, relative imports resolved
    against `package`; `from a import b` also yields `a.b`, and a literal
    importlib.import_module / __import__ argument counts as an import."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                parts = package.split(".")
                anchor = ".".join(parts[: len(parts) - node.level + 1])
                base = f"{anchor}.{base}" if base else anchor
            found.add(base)
            found.update(f"{base}.{alias.name}" for alias in node.names)
        elif isinstance(node, ast.Call) and node.args:
            function = node.func
            name = (
                function.attr
                if isinstance(function, ast.Attribute)
                else function.id
                if isinstance(function, ast.Name)
                else ""
            )
            argument = node.args[0]
            if (
                name in {"import_module", "__import__"}
                and isinstance(argument, ast.Constant)
                and isinstance(argument.value, str)
            ):
                found.add(argument.value)
    return found


def _roots(modules: set[str]) -> set[str]:
    return {module.split(".")[0] for module in modules}


def _package(path: Path) -> str:
    return ".".join(path.relative_to(ROOT).with_suffix("").parts[:-1])


def _scan(paths: list[Path], forbidden: frozenset[str]) -> list[str]:
    violations = []
    for path in paths:
        found = imported_modules(path.read_text(encoding="utf-8"), _package(path))
        for root in sorted(_roots(found) & forbidden):
            violations.append(f"{path.relative_to(ROOT)} imports {root}")
    return violations


@pytest.mark.parametrize(
    "source",
    [
        "import fastapi",
        "def later():\n    import uvicorn.server\n",
        "from starlette.responses import Response",
        "class Lazy:\n    def load(self):\n        from pydantic import BaseModel\n",
        "import importlib\nimportlib.import_module('fastapi.routing')",
        "__import__('starlette')",
    ],
    ids=[
        "top-level",
        "nested-function",
        "from-submodule",
        "method",
        "importlib",
        "dunder-import",
    ],
)
def test_the_scanner_finds_framework_imports_wherever_they_are(source: str) -> None:
    assert _roots(imported_modules(source)) & FRAMEWORK


def test_the_scanner_resolves_relative_imports() -> None:
    found = imported_modules(
        "from ..application import jobs\nfrom ...kernel.runner import run", "harness.console.backend.api"
    )
    assert {"harness.console.backend.application.jobs", "harness.console.kernel.runner"} <= found
    assert (
        not _roots(imported_modules("import json\nfrom pathlib import Path"))
        & FRAMEWORK
    )


def test_console_modules_outside_api_never_import_the_web_framework() -> None:
    paths = [path for path in CONSOLE.rglob("*.py") if API not in path.parents]
    assert len(paths) > 20
    assert _scan(paths, FRAMEWORK) == []


def test_no_harness_module_imports_h11_or_jinja2() -> None:
    paths = list(HARNESS.rglob("*.py"))
    assert _scan(paths, RETIRED) == []


def test_api_routes_reach_services_only_through_the_router() -> None:
    for name in ROUTE_MODULES:
        path = API / name
        found = imported_modules(path.read_text(encoding="utf-8"), _package(path))
        assert not found & SERVICE_INTERNALS, (name, sorted(found & SERVICE_INTERNALS))
