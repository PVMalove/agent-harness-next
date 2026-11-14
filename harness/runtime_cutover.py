# Copyright (c) 2026 Malov Pavel (p.malove@yandex.ru)
# SPDX-License-Identifier: BUSL-1.1
# Licensed under the Business Source License 1.1 (BSL-1.1).
# Commercial use, sale, or use in commercial application development is strictly
# prohibited without prior written permission from the copyright holder.
# Removing or altering this header is prohibited and voids all license rights.

"""Переход state проекта на runtime store при `harness update` до 2.0.0 (ADR 0020, раздел 6; #814).

Coordinator 2.0.0 не работает на файловом ledger. Поэтому `harness update` на state с `ledger.json`
версии 3 до установки файлов проверяет предусловия `harness-runtime migrate --check`, а после
установки запускает `harness-runtime migrate` с human approval из своих флагов. Проект без state и
проект, уже переведённый на store, обновляются как раньше: store нового проекта создаёт первый
`harness-runtime serve`.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from harness.errors import HarnessError

STATE_REL = Path(".harness/orchestration/state")
#: The release build in a harness checkout, as `runtime-autostart` looks for it first.
CHECKOUT_BINARY = Path("native/harness-runtime/target/release/harness-runtime")
BUILD = "cargo build --release --manifest-path native/harness-runtime/Cargo.toml"
APPROVAL_FLAGS = ("approved_by", "approved_at", "reason")
#: The pointer version of the runtime-store epoch.
STORE_VERSION = 4


@dataclass(frozen=True)
class Cutover:
    """The migrate that `harness update` runs after it installed the files."""

    binary: Path
    approval: tuple[str, str, str]


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """The approval flags of `harness update`: the human approval of the cutover."""
    parser.add_argument(
        "--approved-by",
        help="the human who approves the cutover of a version-3 ledger to the runtime store",
    )
    parser.add_argument("--approved-at", help="the time of that approval (RFC 3339)")
    parser.add_argument("--reason", help="why the state is cut over now")


def _ledger_version(repo: Path) -> int | None:
    pointer = repo / STATE_REL / "ledger.json"
    if not pointer.is_file():
        return None
    try:
        version = json.loads(pointer.read_text(encoding="utf-8")).get("version")
    except (OSError, ValueError, AttributeError) as exc:
        raise HarnessError(
            f"{pointer} is not a readable ledger pointer",
            remedy=f"restore {pointer} from the backup of the state directory, then repeat",
        ) from exc
    return version if isinstance(version, int) else None


def _binary(repo: Path) -> Path | None:
    """`harness-runtime`: the release build of the checkout, then the one on PATH."""
    for root in (repo, Path(__file__).resolve().parents[1]):
        built = root / CHECKOUT_BINARY
        if built.is_file():
            return built
    found = shutil.which("harness-runtime")
    return Path(found) if found else None


def _command(repo: Path, approval: tuple[str, str, str] | None = None) -> str:
    by, at, reason = approval or ("<human>", "<RFC 3339 time>", "<reason>")
    return (
        f"harness update {repo} --approved-by {by} --approved-at {at} --reason {reason!r}"
        if approval is None
        else f"harness-runtime migrate --repo {repo} --approved-by {by} --approved-at {at} "
        f"--reason {reason!r}"
    )


def _refusal(result: subprocess.CompletedProcess[str], step: str) -> HarnessError:
    lines = result.stderr.strip().splitlines()
    remedy = next((line.removeprefix("REMEDY: ") for line in lines if line.startswith("REMEDY:")), "")
    message = next((line.removeprefix("ERROR: ") for line in lines if line.startswith("ERROR:")), "")
    return HarnessError(
        f"{step} refused (exit {result.returncode}): {message or result.stderr.strip()}",
        remedy=remedy or "read the output of harness-runtime above",
    )


def prepare(repo: Path, args: argparse.Namespace) -> Cutover | None:
    """Before any file is installed: the migrate this update owes, or `None`.

    Raises `HarnessError` (the update installs nothing) when the approval is partial or missing
    for a version-3 ledger, the ledger is older than version 3, the runtime is not found or
    `harness-runtime migrate --check` refuses."""
    supplied = tuple(getattr(args, name, None) for name in APPROVAL_FLAGS)
    if any(supplied) and not all(supplied):
        raise HarnessError(
            "--approved-by, --approved-at and --reason come together",
            remedy="pass all three approval flags of the cutover, or none",
        )
    version = _ledger_version(repo)
    if version is None or version == STORE_VERSION:
        return None
    if version in (1, 2):
        raise HarnessError(
            f"the ledger of {repo} is version {version}; harness 2.0.0 cuts over only version 3",
            remedy="run 'coordinator.py ledger migrate' of the last 1.x release first, then "
            f"repeat {_command(repo)}",
        )
    if not all(supplied):
        raise HarnessError(
            "harness 2.0.0 runs only on the runtime store, and the ledger of this project is "
            "version 3: the update cuts it over, which needs the approval of a human",
            remedy=f"repeat {_command(repo)}",
        )
    binary = _binary(repo)
    if binary is None:
        raise HarnessError(
            "harness-runtime is not found: neither a release build in the checkout nor on PATH",
            remedy=f"build it with `{BUILD}` or put harness-runtime on PATH, then repeat the update",
        )
    checked = subprocess.run(
        [str(binary), "migrate", "--check", "--repo", str(repo)],
        capture_output=True,
        text=True,
        check=False,
    )
    if checked.returncode != 0:
        raise _refusal(checked, "harness-runtime migrate --check")
    by, at, reason = (str(value) for value in supplied)
    return Cutover(binary=binary, approval=(by, at, reason))


def run(repo: Path, cutover: Cutover) -> None:
    """After the files are installed: `harness-runtime migrate` with the approval of the update.

    A refusal or an interrupted migrate leaves the file ledger the authority; coordinator 2.0.0
    then refuses until a repeated migrate or the return to 1.x (ADR 0020, section 6)."""
    by, at, reason = cutover.approval
    migrated = subprocess.run(
        [
            str(cutover.binary),
            "migrate",
            "--repo",
            str(repo),
            "--approved-by",
            by,
            "--approved-at",
            at,
            "--reason",
            reason,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if migrated.returncode != 0:
        error = _refusal(migrated, "harness-runtime migrate")
        raise HarnessError(
            f"the files are installed, but {error.message}",
            remedy=f"{error.remedy}; repeat {_command(repo, cutover.approval)} or return the "
            "project to the last 1.x release",
        )
    print(migrated.stdout.strip())
