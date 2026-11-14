"""Claude Code runtime adapter: starts the worker in the selected checkout, never in the repo root."""

from __future__ import annotations

import importlib.util
import json
import os
import stat
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path, PurePosixPath, PureWindowsPath
from unittest import mock

ADAPTER = Path(__file__).resolve().parents[2] / "harness/adapters/claude_worker.py"
SPEC = importlib.util.spec_from_file_location("claude_worker", ADAPTER)
assert SPEC and SPEC.loader
claude_worker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(claude_worker)


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
    ).stdout.strip()


POSIX_ONLY = unittest.skipIf(
    os.name == "nt",
    "the fake claude is a POSIX shell script and the adapter starts a POSIX session",
)


class ClaudeWorkerAdapterTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name).resolve()
        self.repo = root / "repo"
        self.worktree = root / "issue-worktree"
        self.repo.mkdir()
        git(self.repo, "init", "-q", "-b", "main")
        git(
            self.repo,
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@example.com",
            "commit",
            "-q",
            "--allow-empty",
            "-m",
            "init",
        )
        git(self.repo, "worktree", "add", "-q", "-b", "issue", str(self.worktree))
        self.sha = git(self.worktree, "rev-parse", "HEAD")
        inbox = self.repo / ".harness/.sandboxes/scratch/inbox"
        inbox.mkdir(parents=True)
        self.brief = self.repo / "brief.json"
        self.brief.write_text(
            json.dumps(
                {
                    "dispatch_id": "dispatch-1",
                    "role": "developer",
                    "purpose": "work",
                    "resolved_transport": "external",
                    "resolved_model": "claude-sonnet-5-5",
                    "resolved_effort": "medium",
                    "allowed_tools": ["Read", "Bash", "Edit"],
                    "report_staging_path": str(inbox / "dispatch-1.json"),
                    "context_package_id": "context-package-1",
                    "liveness": {"heartbeat_every_seconds": 300},
                }
            )
        )
        self.bin = root / "bin"
        self.bin.mkdir()
        self.prompt_dump = root / "prompt.txt"
        self.cwd_dump = root / "cwd.txt"

    def fake_claude(self, exit_code: int) -> None:
        script = self.bin / "claude"
        script.write_text(
            "#!/bin/sh\n"
            f'pwd > "{self.cwd_dump}"\n'
            f'cat > "{self.prompt_dump}"\n'
            f"exit {exit_code}\n"
        )
        script.chmod(script.stat().st_mode | stat.S_IEXEC)

    def run_adapter(self, *extra: str) -> int:
        argv = [
            "dispatch",
            *extra,
            "--repo",
            str(self.repo),
            "--brief",
            str(self.brief),
        ]
        env = {**os.environ, "PATH": f"{self.bin}{os.pathsep}{os.environ['PATH']}"}
        cwd = Path.cwd()
        os.chdir(self.worktree)
        try:
            with (
                mock.patch.dict(os.environ, env, clear=True),
                mock.patch.object(claude_worker, "STARTUP_CHECK_SECONDS", 0.5),
            ):
                return int(claude_worker.main(argv))
        finally:
            os.chdir(cwd)

    def test_help_documents_the_flags_dispatch_send_probes(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ADAPTER), "dispatch", "--help"],
            capture_output=True,
            text=True,
            check=True,
        )
        for flag in ("--repo", "--brief", "--extra-prompt-file", "--dry-run"):
            self.assertIn(flag, result.stdout)

    def test_author_permission_exposes_shared_runner_evidence_without_widening_tools(
        self,
    ) -> None:
        brief = json.loads(self.brief.read_text())
        brief["allowed_tools"] = ["Read", "Bash", "Agent(test-author)"]

        command = claude_worker.worker_command(brief)

        self.assertIn(str(self.repo / ".harness/.sandboxes/runs"), command)
        self.assertEqual(
            command[command.index("--allowedTools") + 1], "Read,Bash,Agent(test-author)"
        )
        prompt = claude_worker.build_prompt(
            brief, self.brief, self.repo, self.worktree, self.sha
        )
        self.assertIn(
            str(Path(self.worktree) / ".claude" / "hooks" / "test-author-preflight.sh"), prompt
        )
        self.assertIn(f"--worktree {shlex.quote(str(self.worktree))}", prompt)
        self.assertIn(f"--brief {shlex.quote(str(self.brief))}", prompt)
        self.assertIn("without model or effort overrides", prompt)
        self.assertIn(str(self.repo / ".harness/.sandboxes/runs"), prompt)

    def test_another_role_keeps_its_original_directory_scope(self) -> None:
        brief = json.loads(self.brief.read_text())
        brief["role"] = "architect"
        brief["allowed_tools"] = ["Read", "Agent"]

        command = claude_worker.worker_command(brief)

        self.assertNotIn(str(self.repo / ".harness/.sandboxes/runs"), command)

    def test_read_only_role_may_write_only_its_report_file(self) -> None:
        brief = json.loads(self.brief.read_text())
        staging = Path(brief["report_staging_path"])
        for role in ("architect", "code-review"):
            with self.subTest(role=role):
                brief["role"] = role
                brief["allowed_tools"] = ["Read", "Grep", "Bash(git diff:*)"]

                command = claude_worker.worker_command(brief)

                self.assertEqual(
                    command[command.index("--allowedTools") + 1],
                    "Read,Grep,Bash(git diff:*),"
                    + claude_worker.report_write_rule(staging),
                )

    def test_report_write_rule_is_one_absolute_path(self) -> None:
        self.assertEqual(
            claude_worker.report_write_rule(PurePosixPath("/repo/inbox/d-1.json")),
            "Edit(//repo/inbox/d-1.json)",
        )
        self.assertEqual(
            claude_worker.report_write_rule(PureWindowsPath(r"C:\repo\inbox\d-1.json")),
            "Edit(//c/repo/inbox/d-1.json)",
        )

    def test_developer_and_writing_roles_keep_their_tools(self) -> None:
        brief = json.loads(self.brief.read_text())
        cases = (
            ("developer", ["Read", "Bash"]),
            ("architect", ["Read", "Write"]),
            ("code-review", ["Read", "Edit(//repo/docs/**)"]),
        )
        for role, tools in cases:
            with self.subTest(role=role, tools=tools):
                brief["role"] = role
                brief["allowed_tools"] = tools

                command = claude_worker.worker_command(brief)

                self.assertEqual(
                    command[command.index("--allowedTools") + 1], ",".join(tools)
                )

    @POSIX_ONLY
    def test_claude_outside_path_is_found_in_user_local_bin(self) -> None:
        brief = json.loads(self.brief.read_text())
        brief["execution"] = {"kind": "process"}
        self.brief.write_text(json.dumps(brief))
        home = self.repo.parent / "home"
        local_bin = home / ".local" / "bin"
        local_bin.mkdir(parents=True)
        script = local_bin / "claude"
        script.write_text(f'#!/bin/sh\npwd > "{self.cwd_dump}"\nexit 7\n')
        script.chmod(script.stat().st_mode | stat.S_IEXEC)
        git_dir = str(Path(shutil.which("git") or "git").parent)
        self.assertIsNone(shutil.which("claude", path=git_dir))
        cwd = Path.cwd()
        os.chdir(self.worktree)
        try:
            with mock.patch.dict(
                os.environ, {"PATH": git_dir, "HOME": str(home)}, clear=True
            ):
                code = claude_worker.main(
                    ["dispatch", "--repo", str(self.repo), "--brief", str(self.brief)]
                )
        finally:
            os.chdir(cwd)

        self.assertEqual(code, 7)
        self.assertEqual(self.cwd_dump.read_text().strip(), str(self.worktree))

    def test_dry_run_starts_nothing_and_targets_the_selected_checkout(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(ADAPTER),
                "dispatch",
                "--dry-run",
                "--repo",
                str(self.repo),
                "--brief",
                str(self.brief),
            ],
            cwd=self.worktree,
            capture_output=True,
            text=True,
            check=True,
        )
        plan = json.loads(result.stdout)
        self.assertEqual(plan["cwd"], str(self.worktree))
        self.assertIn(f"Expected worker checkout: {self.worktree}", plan["prompt"])
        self.assertIn(f"Expected startup SHA: {self.sha}", plan["prompt"])
        command = plan["command"]
        self.assertEqual(command[command.index("--model") + 1], "claude-sonnet-5-5")
        self.assertEqual(command[command.index("--effort") + 1], "medium")
        self.assertEqual(command[command.index("--permission-mode") + 1], "dontAsk")
        self.assertEqual(command[command.index("--allowedTools") + 1], "Read,Bash,Edit")

    def test_container_worker_is_asked_only_for_the_staged_report(self) -> None:
        brief = json.loads(self.brief.read_text())
        brief["execution"] = {"kind": "container"}
        self.brief.write_text(json.dumps(brief))
        env = {**os.environ, "HARNESS_EXECUTOR": "docker"}

        result = subprocess.run(
            [
                sys.executable,
                str(ADAPTER),
                "dispatch",
                "--dry-run",
                "--repo",
                str(self.repo),
                "--brief",
                str(self.brief),
            ],
            cwd=self.worktree,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )

        plan = json.loads(result.stdout)
        prompt = plan["prompt"]
        self.assertIn("running in a container", prompt)
        self.assertIn(f"Report staging path: {brief['report_staging_path']}", prompt)
        self.assertIn("never run dispatch self-report", prompt)
        self.assertNotIn("coordinator.py", prompt)
        self.assertNotIn("report submit --file", prompt)
        command = plan["command"]
        self.assertEqual(command[2], prompt)
        self.assertEqual(
            command[command.index("--output-format") + 1 :][:2],
            ["stream-json", "--verbose"],
        )

    @POSIX_ONLY
    def test_worker_runs_in_the_worktree_and_receives_the_prompt(self) -> None:
        self.fake_claude(0)
        extra = self.repo / "retry.txt"
        extra.write_text("Retry handoff: {}")
        # This fake exits immediately; even a zero exit is now a startup failure.
        self.assertEqual(self.run_adapter("--extra-prompt-file", str(extra)), 1)
        self.assertEqual(self.cwd_dump.read_text().strip(), str(self.worktree))
        prompt = self.prompt_dump.read_text()
        self.assertIn("worker for dispatch dispatch-1", prompt)
        self.assertIn("Retry handoff: {}", prompt)
        self.assertTrue(
            (
                self.repo / ".harness/.sandboxes/scratch/worker-logs/dispatch-1.log"
            ).exists()
        )

    @POSIX_ONLY
    def test_supervised_worker_gets_the_prompt_as_an_argument_and_its_code_is_returned(
        self,
    ) -> None:
        brief = json.loads(self.brief.read_text())
        brief["execution"] = {"kind": "process"}
        self.brief.write_text(json.dumps(brief))
        script = self.bin / "claude"
        script.write_text(
            "#!/bin/sh\n"
            f'pwd > "{self.cwd_dump}"\n'
            f'printf "%s" "$2" > "{self.prompt_dump}"\n'
            "exit 5\n"
        )
        script.chmod(script.stat().st_mode | stat.S_IEXEC)
        extra = self.repo / "retry.txt"
        extra.write_text("Retry handoff: {}")

        self.assertEqual(self.run_adapter("--extra-prompt-file", str(extra)), 5)

        self.assertEqual(self.cwd_dump.read_text().strip(), str(self.worktree))
        prompt = self.prompt_dump.read_text()
        self.assertIn("worker for dispatch dispatch-1", prompt)
        self.assertIn("Retry handoff: {}", prompt)
        self.assertFalse(
            (self.repo / ".harness/.sandboxes/scratch/worker-logs").exists()
        )

    @POSIX_ONLY
    def test_worker_that_dies_at_startup_is_rejected(self) -> None:
        self.fake_claude(3)
        self.assertEqual(self.run_adapter(), 1)


if __name__ == "__main__":
    unittest.main()
