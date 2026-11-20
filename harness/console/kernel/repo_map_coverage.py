"""What the Repo Map screen derives from a schema v1 map beyond its own fields: the kind of each
signature and the coverage of the map by file class. The Repo Map schema is not changed; symbol
line numbers, symbol-level edges and summaries are not in it and stay unknown.

Symbol kind, from the text `harness/repo_map/tree_sitter_worker.py` renders (an `async ` prefix is
ignored):

- `function`: `def f(...)`, `function f(...)`, `const f(...)` (an arrow function), `func f(...)`;
- `method`: `def C.m(...)`, `method C.m(...)`, `static method C.m(...)`, `constructor C.C(...)`,
  `func (r R) m(...)`;
- `class`: `class X`, `class X(Base)`, `class X extends Y`;
- `struct` and `interface`: Go's `type X struct` and `type X interface`;
- `other`: any other text.

File class, by path (the first rule that matches wins):

- `tests`: a directory named `tests`, `test`, `__tests__`, `spec` or `specs`, or a file named
  `test_*`, `*_test.*`, `*.test.*` or `*.spec.*`;
- `docs`: a directory named `docs` or `doc`, or a `.md`, `.rst`, `.adoc` or `.txt` file;
- `source`: everything else.

`excluded` is the number of files tracked at the map's commit (`git ls-tree -r --name-only`,
read-only, with a timeout) that the map does not list; None when Git cannot answer. Standard
library only."""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath

from .repo_map import RepoMapView

SYMBOL_KINDS = ("function", "method", "class", "struct", "interface", "other")
FILE_CLASSES = ("source", "docs", "tests")
_TEST_DIRS = frozenset({"tests", "test", "__tests__", "spec", "specs"})
_DOC_DIRS = frozenset({"docs", "doc"})
_DOC_SUFFIXES = frozenset({".md", ".rst", ".adoc", ".txt"})
_GIT_TIMEOUT_SECONDS = 10.0

# (exit code, standard output); None when Git cannot run or times out.
type GitRun = Callable[[Sequence[str]], tuple[int, str] | None]


def symbol_kind(signature: str) -> str:
    """The kind of one rendered signature, by the rules of the module docstring."""
    text = signature.removeprefix("async ")
    if text.startswith(("method ", "static method ", "constructor ", "func (")):
        return "method"
    for keyword in ("def ", "function ", "const ", "func "):
        if text.startswith(keyword):
            name = text.removeprefix(keyword).partition("(")[0]
            return "method" if keyword == "def " and "." in name else "function"
    if text.startswith("class "):
        return "class"
    if text.startswith("type "):
        last = text.rsplit(" ", 1)[-1]
        if last in ("struct", "interface"):
            return last
    return "other"


def symbol_kinds(view: RepoMapView) -> dict[str, list[str]]:
    """The kind of every signature, by file path, in the map's signature order."""
    return {
        item.path: [symbol_kind(signature) for signature in item.signatures]
        for item in view.files
    }


def file_class(path: str) -> str:
    """`source`, `docs` or `tests` for one repository path, by the rules of the module docstring."""
    pure = PurePosixPath(path)
    directories = {part.lower() for part in pure.parts[:-1]}
    name = pure.name.lower()
    if (
        directories & _TEST_DIRS
        or name.startswith("test_")
        or pure.stem.lower().endswith("_test")
        or ".test." in name
        or ".spec." in name
    ):
        return "tests"
    if directories & _DOC_DIRS or pure.suffix.lower() in _DOC_SUFFIXES:
        return "docs"
    return "source"


@dataclass(frozen=True)
class MapCoverage:
    """The map's files by class, and the tracked files it leaves out (None: unknown)."""

    source: int
    docs: int
    tests: int
    excluded: int | None

    def to_payload(self) -> dict[str, int | None]:
        return asdict(self)


def coverage(view: RepoMapView, excluded: int | None) -> MapCoverage:
    counts = {name: 0 for name in FILE_CLASSES}
    for item in view.files:
        counts[file_class(item.path)] += 1
    return MapCoverage(counts["source"], counts["docs"], counts["tests"], excluded)


def _run_git(argv: Sequence[str]) -> tuple[int, str] | None:
    try:
        found = subprocess.run(
            list(argv),
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_SECONDS,
            stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return found.returncode, found.stdout


def excluded_files(repo: Path, view: RepoMapView, run: GitRun = _run_git) -> int | None:
    """The files tracked at the map's commit that the map does not list; None when Git cannot
    list them."""
    if not view.commit or view.commit.startswith("-"):
        return None
    found = run(["git", "-C", str(repo), "ls-tree", "-r", "-z", "--name-only", view.commit])
    if found is None or found[0] != 0:
        return None
    tracked = {path for path in found[1].split("\0") if path}
    return len(tracked - {item.path for item in view.files})
