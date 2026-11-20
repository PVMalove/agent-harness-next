"""Установка, discovery и предусловия first-party скилла developer."""

import contextlib
import io
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "harness" / "bin" / "harness.py"
SOURCE = ROOT / "skills" / "first-party" / "engineering" / "developer"
SKILL = SOURCE / "SKILL.md"
INSTALLED = ".harness/skills/developer/"


def _normalized(path: Path) -> str:
    """Текст файла с пробелами, сжатыми до одного."""
    return " ".join(path.read_text(encoding="utf-8").split())


def _frontmatter(path: Path) -> dict[str, str]:
    """Простые пары ключ-значение из frontmatter SKILL.md."""
    text = path.read_text(encoding="utf-8")
    match = re.match(r"---\n(.*?)\n---\n", text, re.DOTALL)
    assert match, f"{path} has no frontmatter"
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields


def _section(path: Path, heading: str) -> str:
    """Нормализованный текст раздела второго уровня до следующего заголовка."""
    text = path.read_text(encoding="utf-8")
    match = re.search(rf"^## {heading}\n(.*?)(?=^## |\Z)", text, re.DOTALL | re.MULTILINE)
    assert match, f"{path.name} has no section {heading}"
    return " ".join(match.group(1).split())


def _harness(*args: str) -> subprocess.CompletedProcess[str]:
    """Вызвать CLI packager в процессе и вернуть код и вывод."""
    from harness.bin import harness as cli

    stdout, stderr = io.StringIO(), io.StringIO()
    with (
        mock.patch.object(sys, "argv", [str(CLI), *args]),
        mock.patch.object(sys, "stdin", io.StringIO()),
        contextlib.redirect_stdout(stdout),
        contextlib.redirect_stderr(stderr),
    ):
        try:
            code = cli.main()
        except SystemExit as exc:
            code = int(exc.code or 0)
    return subprocess.CompletedProcess(
        [str(CLI), *args], code, stdout.getvalue(), stderr.getvalue()
    )


class DeveloperSkillPackageTests(unittest.TestCase):
    """Скилл developer ставится только с engineering-suite."""

    def test_engineering_suite_installs_the_skill_byte_for_byte(self) -> None:
        """Проверить, что engineering-suite ставит SKILL.md и openai.yaml без изменений."""
        from harness.bin.harness import package_files

        for names in (["engineering-suite"], ["engineering-suite", "backend-orchestration"]):
            with self.subTest(names=names):
                files = package_files(names)
                for relative in ("SKILL.md", "agents/openai.yaml"):
                    self.assertEqual(
                        files[INSTALLED + relative], (SOURCE / relative).read_bytes()
                    )

    def test_other_capabilities_do_not_install_the_skill(self) -> None:
        """Проверить, что без engineering-suite скилл не ставится."""
        from harness.bin.harness import package_files

        for names in (["project-foundation"], ["mattpocock-suite"]):
            with self.subTest(names=names):
                self.assertFalse(
                    [path for path in package_files(names) if path.startswith(INSTALLED)]
                )


class DeveloperSkillDiscoveryTests(unittest.TestCase):
    """Реестр и runtime discovery находят скилл developer."""

    def test_registry_lists_the_skill_with_its_frontmatter_description(self) -> None:
        """Проверить строку реестра и метаданные frontmatter."""
        fields = _frontmatter(SKILL)
        self.assertEqual(fields["name"], SOURCE.name)
        self.assertNotIn("disable-model-invocation", fields)
        registry = (ROOT / "skills" / "REGISTRY.md").read_text(encoding="utf-8")
        self.assertIn(
            f"| `developer` | `skills/first-party/engineering/developer` | {fields['description']} |",
            registry,
        )

    def test_codex_metadata_allows_implicit_invocation(self) -> None:
        """Проверить, что Codex может выбрать скилл без явной команды."""
        metadata = (SOURCE / "agents" / "openai.yaml").read_text(encoding="utf-8")
        self.assertIn("allow_implicit_invocation: true", metadata)

    def _init(self, capability: str) -> Path:
        """Установить харнесс с одной capability во временный git-репозиторий."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        repo = Path(temporary.name) / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
        installed = _harness("init", str(repo), "--capability", capability)
        self.assertEqual(installed.returncode, 0, installed.stderr)
        return repo

    def test_engineering_suite_project_discovers_the_skill(self) -> None:
        """Проверить, что ссылки .claude/skills и .agents/skills резолвят скилл."""
        repo = self._init("engineering-suite")
        for discovery in (".claude", ".agents"):
            with self.subTest(discovery=discovery):
                self.assertEqual(
                    (repo / discovery / "skills" / "developer" / "SKILL.md").read_bytes(),
                    SKILL.read_bytes(),
                )

    def test_mattpocock_suite_project_does_not_discover_the_skill(self) -> None:
        """Проверить, что без engineering-suite discovery скилла нет."""
        repo = self._init("mattpocock-suite")
        for discovery in (".claude", ".agents"):
            with self.subTest(discovery=discovery):
                self.assertFalse((repo / discovery / "skills" / "developer").exists())


class DeveloperSkillContractTests(unittest.TestCase):
    """Текст скилла задаёт предусловия, границы и evidence без контракта роли."""

    def test_missing_prerequisite_stops_before_any_edit_with_a_blocker(self) -> None:
        """Проверить, что каждое предусловие названо и его отсутствие останавливает работу."""
        prerequisites = _section(SKILL, "Prerequisites")
        for marker in (
            "before editing any file",
            "If one is missing, stop: make no change",
            "an empty Changes section and a blocker that names the missing prerequisite",
            "acceptance criteria",
            '"Issue First"',
            "`.harness/project.json` is readable",
            "`branch_pattern`",
            "neither `base_branch` nor an `integration/*` branch",
        ):
            self.assertIn(marker, prerequisites)

    def test_evidence_has_five_sections_in_order(self) -> None:
        """Проверить пять разделов evidence в фиксированном порядке."""
        evidence = _section(SKILL, "Evidence")
        positions = [
            evidence.index(f"**{name}:**")
            for name in ("Changes", "Checks", "Unverified", "Risks", "Blockers")
        ]
        self.assertEqual(positions, sorted(positions))

    def test_delivery_steps_stay_with_the_caller(self) -> None:
        """Проверить, что скилл не коммитит, не пушит и не открывает PR."""
        completion = _section(SKILL, "Completion")
        for marker in ("never commits", "never pushes", "never opens a pull request"):
            self.assertIn(marker, completion)

    def test_skill_does_not_duplicate_the_role_contract(self) -> None:
        """Проверить, что термины протокола роли coordinator отсутствуют."""
        text = _normalized(SKILL)
        for term in (
            "self-report",
            "heartbeat",
            "report submit",
            "commit_plan",
            "carried_item_closure",
            "report_staging_path",
            "checkpoint",
        ):
            self.assertNotIn(term, text)
        self.assertIn("`harness/orchestration/roles/developer.md`", text)


class DeveloperDispatchReadsTheSkillTests(unittest.TestCase):
    """Developer dispatch читает скилл, а бриф и контракт роли остаются старше."""

    ROLE = ROOT / "harness" / "orchestration" / "roles" / "developer.md"
    IMPLEMENT = (
        ROOT / "skills" / "first-party" / "engineering" / "implement" / "SKILL.md"
    )

    def test_skill_states_the_precedence_of_brief_and_role_contract(self) -> None:
        """Проверить раздел dispatch в скилле и старшинство брифа и контракта роли."""
        section = _section(SKILL, "Inside a coordinator dispatch")
        for marker in (
            "immutable brief and `harness/orchestration/roles/developer.md` stay authoritative",
            "grants no path, tool or approval",
            "replaces the Evidence report",
        ):
            self.assertIn(marker, section)
        self.assertNotIn(
            "follow `harness/orchestration/roles/developer.md` and the brief instead",
            _normalized(SKILL),
        )

    def test_role_contract_names_the_installed_skill_and_the_missing_file_path(
        self,
    ) -> None:
        """Проверить, что роль ссылается на установленный скилл и блокирует без файла."""
        section = _section(self.ROLE, "Developer skill")
        for marker in (
            "`.harness/skills/developer/SKILL.md`",
            "The immutable brief and this contract stay authoritative",
            "`outcome: blocked`",
        ):
            self.assertIn(marker, section)

    def test_implement_worker_prompt_carries_the_dispatch_instruction(self) -> None:
        """Проверить, что шаблон промпта implement передаёт developer_skill.instruction."""
        text = _normalized(self.IMPLEMENT)
        self.assertIn(
            "<developer_skill.instruction from dispatch send or dispatch resume, verbatim>",
            text,
        )
        self.assertIn("do not start the worker", text)


class FastImplementUsesDeveloperSkillTests(unittest.TestCase):
    """fast-implement отдаёт реализацию скиллу developer и сохраняет поставку."""

    FAST = ROOT / "skills" / "first-party" / "engineering" / "fast-implement" / "SKILL.md"

    def test_coding_phase_references_the_developer_skill_and_its_evidence(self) -> None:
        """Проверить ссылку на скилл и показ его evidence до вопроса о review."""
        text = _normalized(self.FAST)
        self.assertIn("Run steps 1–4 under the `developer` skill", text)
        self.assertIn(
            "evidence (changes, checks, unverified items, risks, blockers) before asking about review",
            text,
        )

    def test_review_commit_push_and_handoff_stay_with_fast_implement(self) -> None:
        """Проверить, что review, commit, push и handoff остались в fast-implement."""
        text = _normalized(self.FAST)
        for marker in (
            "Провести code review?",
            "explicit permission to commit and push",
            "offer `/to-pull-requests <ticket>`",
            "the `developer` skill never performs them",
        ):
            self.assertIn(marker, text)


if __name__ == "__main__":
    unittest.main()
