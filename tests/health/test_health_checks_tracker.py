"""Сквозные тесты сетевых проверок GitHub/GitLab трекера группы 'tracker'."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HARNESS = Path(__file__).resolve().parents[2] / "harness" / "bin" / "harness.py"
REAL_GIT = shutil.which("git")

_FAKE_TOOL = """
import json, os, subprocess, sys
from pathlib import Path

spec = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
args = sys.argv[2:]
if spec["glab"] and args[:1] == ["api"]:
    # Like glab 1.120.0: a port in --hostname is rejected before any request, while GITLAB_HOST
    # names the host (with its port) and is recorded as the shell prefix it stands for.
    hostname = args[args.index("--hostname") + 1:][:1] if "--hostname" in args else []
    if hostname and ":" in hostname[0]:
        sys.stderr.write("ERROR Error parsing --hostname: invalid hostname.\\n")
        sys.exit(1)
    if os.environ.get("GITLAB_HOST"):
        args = ["GITLAB_HOST=" + os.environ["GITLAB_HOST"], *args]
with open(spec["log"], "a", encoding="utf-8") as log:
    log.write(json.dumps(args) + "\\n")
key = list(args)
while len(key) >= 2 and key[0] in ("-c", "-C"):
    key = key[2:]
response = spec["responses"].get(" ".join(key))
if response is not None:
    code, out, err = response
    sys.stdout.write(out)
    sys.stderr.write(err)
    sys.exit(code)
if spec["passthrough"]:
    sys.exit(subprocess.run([spec["passthrough"], *args]).returncode)
sys.stderr.write("fake tool: unexpected arguments " + " ".join(args) + "\\n")
sys.exit(2)
"""

Responses = dict[str, tuple[int, str, str]]


def _fake_tool(
    bin_dir: Path, name: str, responses: Responses, *, passthrough: str | None = None
) -> Path:
    """Создать фиктивную утилиту с имитацией ответов и логированием вызовов."""
    bin_dir.mkdir(parents=True, exist_ok=True)
    log = bin_dir / f"{name}.log"
    spec = bin_dir / f"{name}.json"
    spec.write_text(
        json.dumps(
            {
                "responses": responses,
                "passthrough": passthrough,
                "log": str(log),
                "glab": name == "glab",
            }
        ),
        encoding="utf-8",
    )
    script = bin_dir / f"{name}_fake.py"
    script.write_text(_FAKE_TOOL, encoding="utf-8")
    if os.name == "nt":
        (bin_dir / f"{name}.cmd").write_text(
            f'@"{sys.executable}" "{script}" "{spec}" %*\r\n', encoding="utf-8"
        )
    else:
        launcher = bin_dir / name
        launcher.write_text(
            f'#!/bin/sh\nexec "{sys.executable}" "{script}" "{spec}" "$@"\n',
            encoding="utf-8",
        )
        launcher.chmod(0o755)
    return log


def _invocations(log: Path) -> list[list[str]]:
    """Прочитать список зарегистрированных вызовов фиктивной утилиты из лога."""
    if not log.is_file():
        return []
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]


def _fake_git(bin_dir: Path, responses: Responses | None = None) -> Path:
    """Создать фиктивную утилиту git с заданными ответами."""
    canned: Responses = {"--version": (0, "git version 9.9.9\n", "")}
    canned.update(responses or {})
    assert REAL_GIT is not None
    return _fake_tool(bin_dir, "git", canned, passthrough=REAL_GIT)


def _fake_gh(bin_dir: Path, responses: Responses | None = None) -> Path:
    """Создать фиктивную утилиту gh с заданными ответами."""
    canned: Responses = {"auth status --hostname github.com": (0, "", "")}
    canned.update(responses or {})
    return _fake_tool(bin_dir, "gh", canned)


def _fake_glab(
    bin_dir: Path,
    responses: Responses | None = None,
    *,
    host: str = "gitlab.example.com",
) -> Path:
    """Создать фиктивную утилиту glab, аутентифицированную только на host, с заданными ответами."""
    canned: Responses = {f"auth status --hostname {host}": (0, "", "")}
    canned.update(responses or {})
    return _fake_tool(bin_dir, "glab", canned)


def _gitlab_access(host: str, encoded_project: str, access_level: int) -> Responses:
    """Ответы glab api: текущий пользователь и его эффективный уровень доступа в проекте."""
    return {
        f"GITLAB_HOST={host} api user": (
            0,
            json.dumps({"id": 7, "username": "dev"}),
            "",
        ),
        f"GITLAB_HOST={host} api projects/{encoded_project}/members/all/7": (
            0,
            json.dumps({"id": 7, "username": "dev", "access_level": access_level}),
            "",
        ),
    }


def _repo(path: Path, *, remote: str | None = None) -> Path:
    """Создать и инициализировать git-репозиторий с опциональным remote."""
    path.mkdir(parents=True, exist_ok=True)
    assert REAL_GIT is not None
    subprocess.run([REAL_GIT, "init", "-q"], cwd=path, check=True)
    if remote:
        subprocess.run(
            [REAL_GIT, "remote", "add", "origin", remote], cwd=path, check=True
        )
    return path


def _health(
    repo: Path, *bin_dirs: Path, online: bool = False, fix: bool = False
) -> tuple[int, dict[str, dict[str, object]]]:
    """Выполнить health --json с указанными каталогами утилит и вернуть код и словарь проверок."""
    _exit_code, _checks, _data = _health_full(repo, *bin_dirs, online=online, fix=fix)
    return _exit_code, _checks


def _health_full(
    repo: Path, *bin_dirs: Path, online: bool = False, fix: bool = False
) -> tuple[int, dict[str, dict[str, object]], dict[str, object]]:
    """Выполнить health --json с полным возвратом кода завершения, словаря проверок и сырых данных."""
    env = {
        key: value
        for key, value in os.environ.items()
        if key
        not in (
            "PYTHONIOENCODING",
            "PYTHONUTF8",
            "GIT_DIR",
            "GIT_WORK_TREE",
            "GITLAB_HOST",
        )
    }
    env["PATH"] = os.pathsep.join(str(path) for path in bin_dirs)
    env["PYTHONUTF8"] = "1"
    argv = [sys.executable, str(HARNESS), "health", str(repo), "--json"]
    if online:
        argv.append("--online")
    if fix:
        argv.append("--fix")
    result = subprocess.run(argv, env=env, capture_output=True, check=False)
    data = json.loads(result.stdout.decode("utf-8"))
    return (
        result.returncode,
        {check["id"]: check for check in data["checks"]},
        data,
    )


TRACKER_IDS = (
    "tracker.auth",
    "tracker.reachability",
    "tracker.permissions",
    "tracker.labels",
    "tracker.git_base",
)


# --- offline (default) ---------------------------------------------------------------------------


def test_without_online_every_tracker_check_is_skipped_offline(tmp_path: Path) -> None:
    """Проверить, что без флага online все проверки трекера пропускаются со статусом офлайн."""
    repo = _repo(tmp_path / "repo", remote="git@github.com:acme/widgets.git")
    bin_dir = tmp_path / "bin"
    _fake_git(bin_dir)

    _, checks = _health(repo, bin_dir, online=False)

    for check_id in TRACKER_IDS:
        assert checks[check_id]["status"] == "skipped"
        assert "офлайн" in str(checks[check_id]["message"])


# --- local tracker ---------------------------------------------------------------------------------


# --- missing gh ------------------------------------------------------------------------------------


# --- gh auth status ---------------------------------------------------------------------------------


def test_online_github_authenticated_reports_ok(tmp_path: Path) -> None:
    """Проверить, что успешно аутентифицированный GitHub сообщает статус ok."""
    repo = _repo(tmp_path / "repo", remote="git@github.com:acme/widgets.git")
    bin_dir = tmp_path / "bin"
    _fake_git(bin_dir, {"ls-remote origin": (0, "abc\tHEAD\n", "")})
    _fake_gh(
        bin_dir,
        {
            "api --hostname github.com repos/acme/widgets --jq .permissions": (
                0,
                json.dumps({"admin": True, "push": True, "triage": True}),
                "",
            ),
            "api --hostname github.com --paginate repos/acme/widgets/labels": (
                0,
                "[]",
                "",
            ),
        },
    )

    _, checks = _health(repo, bin_dir, online=True)

    assert checks["tracker.auth"]["status"] == "ok"
    assert checks["tracker.reachability"]["status"] == "ok"


# --- reachability: the cause of a failed git ls-remote -------------------------------------------


# --- permissions -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("remote", "host", "encoded_project"),
    [
        (
            "https://gitlab.example.test:4443/group/sub/project.git",
            "gitlab.example.test:4443",
            "group%2Fsub%2Fproject",
        )
    ],
)


def test_online_gitlab_origin_forms_address_the_full_project_path(
    tmp_path: Path, remote: str, host: str, encoded_project: str
) -> None:
    """Проверить, что HTTPS с портом, ssh:// с портом, SCP-форма, точка в имени и userinfo дают
    GitLab, glab api с хостом трекера в GITLAB_HOST и полный путь проекта с подгруппами."""
    repo = _repo(tmp_path / "repo", remote=remote)
    bin_dir = tmp_path / "bin"
    _fake_git(bin_dir, {"ls-remote origin": (0, "abc\tHEAD\n", "")})
    glab_log = _fake_glab(bin_dir, _gitlab_access(host, encoded_project, 30), host=host)

    _, checks, data = _health_full(repo, bin_dir, online=True)

    assert checks["tracker.auth"]["status"] == "ok"
    assert checks["tracker.permissions"]["status"] == "ok"
    invocations = _invocations(glab_log)
    assert ["auth", "status", "--hostname", host] in invocations
    assert [
        f"GITLAB_HOST={host}",
        "api",
        f"projects/{encoded_project}/members/all/7",
    ] in invocations
    assert "ci-user" not in json.dumps(data, ensure_ascii=False)


# --- tracker.project (offline) ---------------------------------------------------------------------


# --- labels ------------------------------------------------------------------------------------------


# --- reachability ------------------------------------------------------------------------------------


# --- tracker.git_base ----------------------------------------------------------------------------
