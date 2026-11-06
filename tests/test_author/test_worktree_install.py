"""An author worktree needs its own installed guard, runner and project config."""

from pathlib import Path

from tests.core.test_uninstall import git, harness


def test_installing_into_a_linked_worker_does_not_write_main_checkout(
    tmp_path: Path,
) -> None:
    main, worker = tmp_path / "main", tmp_path / "worker"
    main.mkdir()
    git(main, "init", "-b", "main")
    git(
        main,
        "-c",
        "user.name=test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "--allow-empty",
        "-m",
        "fixture",
    )
    git(main, "worktree", "add", "-b", "feature/issue-1-worker", str(worker))
    before = git(main, "status", "--porcelain")

    result = harness(
        "init",
        str(worker),
        "--capability",
        "engineering-suite",
        "--test-path",
        "tests/**",
        "--test-runner-command",
        "python3 -m unittest {test_id}",
    )

    assert result.returncode == 0, result.stderr
    assert (worker / ".claude/hooks/test-author-preflight.sh").is_file()
    assert (worker / ".claude/hooks/run-test.sh").is_file()
    assert (worker / ".harness/health/isolated_runner.py").is_file()
    assert git(main, "status", "--porcelain") == before
    assert not (main / ".claude").exists()
