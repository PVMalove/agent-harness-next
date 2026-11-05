"""Dependency boundaries of the console. The layers of `harness/console/backend` (domain,
application, api, infrastructure) depend inwards, only `backend/composition.py` wires the
infrastructure adapters, the TUI and the kernel never import the server, only `backend/api`
imports the web framework, and the retired h11 transport and Jinja2 are imported nowhere."""

from __future__ import annotations

import ast
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / "harness"
CONSOLE = HARNESS / "console"
BACKEND = CONSOLE / "backend"
API = BACKEND / "api"

FRAMEWORK = frozenset({"fastapi", "starlette", "uvicorn", "pydantic"})
RETIRED = frozenset({"h11", "jinja2"})
ROUTE_MODULES = ("app.py", "websocket.py", "static.py")
# Routes reach the services only through the request router.
SERVICE_INTERNALS = frozenset(
    {
        "harness.console.backend.application.jobs",
        "harness.console.kernel.runner",
        "harness.console.kernel.process_tree",
        "harness.console.tui.ledger_lock",
        "harness.console.backend.infrastructure.event_journal",
        "harness.orchestration.coordinator",
    }
)

B = "harness.console.backend"
TUI = "harness.console.tui"
KERNEL = "harness.console.kernel"


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


def _within(module: str, prefix: str) -> bool:
    return module == prefix or module.startswith(prefix + ".")


@dataclass(frozen=True)
class Rule:
    """Modules the files a rule covers must not import (each prefix with its submodules); with
    `only_console`, every `harness.console` import of those files must lie in one of them."""

    covers: Callable[[Path], bool]
    forbidden: frozenset[str]
    only_console: frozenset[str] | None = None

    def violations(self, source: str, package: str) -> list[str]:
        found = imported_modules(source, package)
        bad = {
            module
            for module in found
            if any(_within(module, prefix) for prefix in self.forbidden)
        }
        if self.only_console is not None:
            bad |= {
                module
                for module in found
                if _within(module, "harness.console")
                and not any(
                    _within(module, allowed) or allowed.startswith(module + ".")
                    for allowed in self.only_console
                )
            }
        return sorted(bad)


def _under(*parts: str) -> Callable[[Path], bool]:
    directory = CONSOLE.joinpath(*parts)
    return lambda path: directory in path.parents


RULES = {
    "domain": Rule(
        _under("backend", "domain"),
        frozenset(
            {
                f"{B}.application",
                f"{B}.api",
                f"{B}.infrastructure",
                f"{B}.server",
                f"{B}.composition",
                TUI,
                *FRAMEWORK,
                "websockets",
                "subprocess",
                "socket",
                "http",
                "urllib",
                "asyncio.subprocess",
            }
        ),
        only_console=frozenset(
            {f"{B}.domain", f"{KERNEL}.protocol", f"{KERNEL}.json_fields"}
        ),
    ),
    "application": Rule(
        _under("backend", "application"),
        frozenset(
            {
                *FRAMEWORK,
                f"{B}.api",
                f"{B}.infrastructure",
                f"{B}.server",
                f"{B}.composition",
                TUI,
            }
        ),
    ),
    "api": Rule(
        _under("backend", "api"),
        frozenset(
            {
                f"{B}.infrastructure",
                f"{B}.composition",
                TUI,
                f"{KERNEL}.runner",
                f"{KERNEL}.process_tree",
                f"{KERNEL}.data",
                f"{KERNEL}.repo_map",
                f"{KERNEL}.repo_map_settings",
                f"{KERNEL}.configuration",
                "harness.orchestration.coordinator",
            }
        ),
    ),
    "infrastructure": Rule(
        _under("backend", "infrastructure"),
        frozenset({f"{B}.api", TUI, *FRAMEWORK}),
    ),
    "composition-root": Rule(
        lambda path: (BACKEND / "infrastructure") not in path.parents
        and path != BACKEND / "composition.py",
        frozenset({f"{B}.infrastructure"}),
    ),
    "tui": Rule(_under("tui"), frozenset({B})),
    "kernel": Rule(
        _under("kernel"),
        frozenset(
            {
                B,
                TUI,
                "harness.console.frontend",
                "harness.console.launcher",
                "harness.console.pin",
            }
        ),
    ),
}

# One import per rule that the rule must refuse, resolved against a module of the layer.
FAILING_SAMPLES = {
    "domain": ("from ..infrastructure.clock import monotonic", f"{B}.domain"),
    "application": ("from ..api.protocol import encode", f"{B}.application"),
    "api": ("from ...kernel.runner import capturing_runner", f"{B}.api"),
    "infrastructure": ("from ..api import HEADER_LIMIT", f"{B}.infrastructure"),
    "composition-root": ("from .infrastructure.ids import new_id", B),
    "tui": ("from ..backend.application.snapshots import Served", TUI),
    "kernel": ("from .. import launcher", KERNEL),
}


def _python_files(root: Path) -> list[Path]:
    """Python modules under `root`; npm packages in a `node_modules` are not ours."""
    return sorted(
        path for path in root.rglob("*.py") if "node_modules" not in path.parts
    )


def _console_files() -> list[Path]:
    return _python_files(CONSOLE)


def layout_violations(console: Path) -> list[str]:
    """The top level holds exactly `__init__.py`, `launcher.py` and `pin.py`; the old `api/` and
    `screens/` packages hold no module; `frontend/` holds no Python; the launcher starts the
    server only as a subprocess, so it imports no backend module."""
    problems = []
    top = sorted(path.name for path in console.glob("*.py"))
    if top != ["__init__.py", "launcher.py", "pin.py"]:
        problems.append(f"top-level modules: {top}")
    for old in ("api", "screens"):
        problems.extend(
            f"old module {path.relative_to(console)}"
            for path in (console / old).rglob("*.py")
        )
    problems.extend(
        f"Python in frontend: {path.relative_to(console)}"
        for path in _python_files(console / "frontend")
    )
    launcher = console / "launcher.py"
    if launcher.is_file():
        found = imported_modules(
            launcher.read_text(encoding="utf-8"), "harness.console"
        )
        backend = sorted(module for module in found if _within(module, B))
        if backend:
            problems.append(f"launcher imports {backend[0]}")
    return problems


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
        "from ..application import jobs\nfrom ...kernel.runner import run",
        "harness.console.backend.api",
    )
    assert {
        "harness.console.backend.application.jobs",
        "harness.console.kernel.runner",
    } <= found
    assert (
        not _roots(imported_modules("import json\nfrom pathlib import Path"))
        & FRAMEWORK
    )


def test_harness_modules_outside_api_never_import_the_web_framework() -> None:
    paths = [path for path in _python_files(HARNESS) if API not in path.parents]
    assert len(paths) > 20
    assert _scan(paths, FRAMEWORK) == []


def test_no_harness_module_imports_h11_or_jinja2() -> None:
    paths = _python_files(HARNESS)
    assert _scan(paths, RETIRED) == []


def test_api_routes_reach_services_only_through_the_router() -> None:
    for name in ROUTE_MODULES:
        path = API / name
        found = imported_modules(path.read_text(encoding="utf-8"), _package(path))
        assert not found & SERVICE_INTERNALS, (name, sorted(found & SERVICE_INTERNALS))


@pytest.mark.parametrize("name", sorted(FAILING_SAMPLES))
def test_every_layer_rule_refuses_its_sample(name: str) -> None:
    source, package = FAILING_SAMPLES[name]
    assert RULES[name].violations(source, package)


def test_the_domain_imports_only_itself_and_the_wire_kernel_from_the_console() -> None:
    rule = RULES["domain"]
    package = f"{B}.domain"
    assert rule.violations("from ...kernel.home_snapshot import HomeSnapshot", package)
    assert rule.violations("import asyncio.subprocess", package)
    allowed = (
        "import asyncio\nfrom ...kernel.protocol import _clip\n"
        "from ...kernel import json_fields\nfrom .jobs import Job\n"
        "from harness.configuration import SECRET_MASK"
    )
    assert rule.violations(allowed, package) == []


@pytest.mark.parametrize("name", sorted(RULES))
def test_console_modules_keep_their_layer_rule(name: str) -> None:
    rule = RULES[name]
    paths = [path for path in _console_files() if rule.covers(path)]
    assert paths, name
    violations = {
        str(path.relative_to(ROOT)): found
        for path in paths
        if (found := rule.violations(path.read_text(encoding="utf-8"), _package(path)))
    }
    assert violations == {}


def test_the_layout_check_refuses_a_left_over_module(tmp_path: Path) -> None:
    console = tmp_path / "console"
    (console / "screens").mkdir(parents=True)
    (console / "frontend").mkdir()
    for name in ("__init__.py", "launcher.py", "pin.py", "server.py"):
        (console / name).write_text("", encoding="utf-8")
    (console / "screens" / "home.py").write_text("", encoding="utf-8")
    (console / "frontend" / "build.py").write_text("", encoding="utf-8")
    # An npm package may ship Python; node_modules is never part of the console.
    (console / "frontend" / "node_modules" / "pkg").mkdir(parents=True)
    (console / "frontend" / "node_modules" / "pkg" / "gyp.py").write_text(
        "", encoding="utf-8"
    )
    (console / "launcher.py").write_text(
        "from .backend.server import run\n", encoding="utf-8"
    )
    assert len(layout_violations(console)) == 4


def test_the_console_package_has_the_layered_layout() -> None:
    assert layout_violations(CONSOLE) == []
