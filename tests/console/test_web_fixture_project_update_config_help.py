"""The fixture snapshots of the Web Open Project, Update Harness, Configuration and Help pages are
the kernel payloads of one served project, they decode with the TUI codecs, and each facts file
lists what the TUI renders for its fixture. A drift on either side fails here.
`python -m tests.console.test_web_fixture_project_update_config_help` rewrites them."""

from __future__ import annotations

import json
import re
import shlex
import sys
import tempfile
from pathlib import Path

import pytest

from harness.console.kernel.configuration_snapshot import (
    AdapterFacts,
    ConfigFile,
    ConfigurationFacts,
)
from harness.console.kernel.configuration import RuntimeAdapterPreview
from harness.console.kernel.configuration_wizard import wizard_parameters
from harness.console.kernel.harness_facts import HarnessState
from harness.console.kernel.help_text import HelpSections, help_sections
from harness.console.kernel.open_project_snapshot import Candidate, OpenProjectFacts
from harness.console.kernel.project_target import ProjectTarget, installation_entry
from harness.console.kernel.home_snapshot import StoreFacts
from harness.console.kernel.update_harness_snapshot import (
    UpdateHarnessFacts,
    diff_paths,
)
from harness.console.tui.screens import project_setup, update_harness
from harness.console.tui.screens.configuration import _ADAPTER_STATUS
from harness.json_types import JsonObject

from ._posix import posix

FIXTURES = Path(__file__).resolve().parents[1] / "web" / "fixtures"
REPO = "/work/project"
MASK = "••••••"


def open_project() -> OpenProjectFacts:
    """The served project has the harness installed; one capability is blocked."""
    return OpenProjectFacts(
        repo=REPO,
        target=ProjectTarget(
            Path(REPO), "update", ("engineering-suite",), (), ()
        ),
        error="",
        blockers={
            "engineering-suite": (),
            "backend-orchestration": (".harness/orchestration/roles/developer.md",),
        },
        candidates=(
            Candidate(REPO, installed=True, current=True),
            Candidate("/work/billing", installed=True, current=False),
            Candidate("/work/new service", installed=False, current=False),
        ),
    )


STATE = HarnessState(
    True, "1.5.1", ("engineering-suite",), 32, 259, "2026-11-05 10:00 UTC", True
)
DRIFT: dict[str, object] = {
    "state": "drift",
    "conflict": ["AGENTS.md"],
    "package_changed": [
        ".agents/skills/tdd/SKILL.md",
        ".harness/orchestration/roles/developer.md",
    ],
    "added": [".agents/skills/research/SKILL.md"],
    "missing": [],
    "retired": [],
    "local_changed": [".harness/docs/technical-english.md"],
    "seed_differing": [".harness/project.json", "docs/agents/git-workflow.md"],
    "unchanged": 240,
    "seed_link_proposals": [],
}
DIFF_PATH = "AGENTS.md"
DIFF_TEXT = (
    "--- проект/AGENTS.md\n"
    "+++ после обновления/AGENTS.md\n"
    "@@ -1,3 +1,3 @@\n"
    " # Project\n"
    "-Local rule.\n"
    "+Package rule.\n"
)


def update() -> UpdateHarnessFacts:
    """A file-ledger project (schema 3) the update migrates to the runtime-store schema."""
    store = StoreFacts("file-ledger", 3, "generation-0007", 128)
    return UpdateHarnessFacts(STATE, "2.0.0", DRIFT, store=store, store_target_schema=4)


def configuration() -> ConfigurationFacts:
    """A project.json with a masked secret, a missing orchestration.json and an adapter plan."""
    return ConfigurationFacts(
        schema_installed=True,
        orchestration_installed=True,
        transaction_pending=False,
        store_root=f"{REPO}/.harness/config_versions",
        files={
            "project.json": ConfigFile(
                True,
                "d" * 64,
                {
                    "tracker": {"kind": "github", "token": MASK},
                    "qa_gate_commands": ["make lint"],
                    "branch_pattern": "feature/issue-{id}-{slug}",
                },
                "",
            ),
            "orchestration.json": ConfigFile(
                False, "", {"roles": {"developer": {"model": "opus"}}}, ""
            ),
        },
        adapters=AdapterFacts(
            RuntimeAdapterPreview(
                [
                    {"path": ".harness/adapters/claude.json", "status": "current", "problem": None},
                    {
                        "path": ".harness/adapters/codex.json",
                        "status": "outdated",
                        "problem": "локальная правка",
                    },
                    {"path": ".harness/adapters/opencode.json", "status": "missing", "problem": None},
                ],
                ["engineering-suite"],
                "f" * 64,
                "Будут обновлены: .harness/adapters/codex.json\nБудут добавлены: .harness/adapters/opencode.json",
                False,
                "",
            ),
            "",
        ),
    )


def _cells(text: str) -> list[str]:
    """The lines of a rendered TUI text, each split at its column gap."""
    return [
        cell.strip()
        for line in text.split("\n")
        for cell in re.split(r" {2,}", line)
        if cell.strip()
    ]


def open_project_facts(payload: JsonObject) -> list[str]:
    """What the TUI «Открыть проект» shows: the stages, the plan summary and command of the
    served project, and every candidate row with its open command."""
    facts = OpenProjectFacts.from_payload(payload)
    target = facts.target
    assert target is not None
    facts_list = list(project_setup._STAGES)
    _, summary, _ = project_setup._target_summary(target)
    facts_list += _cells(summary)
    capability = target.capabilities[0]
    facts_list.append(
        shlex.join(installation_entry(target, capability).cli_argv(target.repo))
    )
    for item in facts.candidates:
        facts_list += _cells(
            project_setup.ProjectSetupScreen._candidate_row(item, "ru").plain
        )
        facts_list.append(item.command)
    return list(dict.fromkeys(facts_list))


def update_facts(payload: JsonObject) -> list[str]:
    """What the TUI «Обновить Harness» shows: the versions, the drift counters, the modes, the
    stop warning of the normal mode and every listed file with its tag."""
    facts = UpdateHarnessFacts.from_payload(payload)
    found = _cells(update_harness.render_versions(facts.state, facts.package_version).plain)
    found += _cells(update_harness.render_drift(facts.drift).plain)
    found += [label for _, label in update_harness.MODES]
    found.append(update_harness._MODE_CONSEQUENCES["update"][0])
    conflicts = update_harness._count((facts.drift or {}).get("conflict"))
    found.append(
        f"⚠ Обычное обновление остановится: {update_harness._conflicts(conflicts, 'ru')}"
    )
    seeds = (facts.drift or {}).get("seed_differing")
    assert isinstance(seeds, list)
    found.append(f"отмечено 0 из {len(seeds)}")
    listed = diff_paths(facts.drift)
    seen: set[str] = set()
    for field, tag, _meaning, status in update_harness._DIFF_KINDS:
        paths = (facts.drift or {}).get(field)
        for path in sorted(paths) if isinstance(paths, list) else []:
            if path in seen:
                continue
            seen.add(path)
            found += [f"{_icon(status)} {tag}", path]
    assert seen == listed
    return list(dict.fromkeys(found))


def _icon(status: str) -> str:
    from harness.console.kernel.brand import STATUS_ICONS

    return STATUS_ICONS[status]


def diff_facts(diff: JsonObject) -> list[str]:
    """What the TUI diff pane shows for the fixture file: why it changes and its lines."""
    meaning = next(m for field, _t, m, _s in update_harness._DIFF_KINDS if field == "conflict")
    return [meaning, *[line for line in str(diff["text"]).split("\n") if line]]


def configuration_facts(payload: JsonObject) -> list[str]:
    """What the TUI «Настройка» shows: the version store, each runtime adapter with its status
    and problem, and the adapter plan."""
    facts = ConfigurationFacts.from_payload(payload)
    found = [facts.store_root]
    preview = facts.adapters.preview
    assert preview is not None
    for item in preview.adapters:
        found += [Path(item["path"]).stem, _ADAPTER_STATUS[item["status"]].render("ru"), item["path"]]
        if item["problem"]:
            found.append(f"⚠ {item['problem']}")
    found += _cells(preview.text)
    return list(dict.fromkeys(found))


def help_facts(ru: JsonObject, en: JsonObject) -> dict[str, list[str]]:
    """The section titles the TUI «Справка» lists in each language."""
    return {
        language: [title for title, _ in HelpSections.from_payload(payload).sections]
        for language, payload in (("ru", ru), ("en", en))
    }


def catalog(section: str) -> JsonObject:
    """The `job.catalog` reply body of `section`, as the composed job service lists it."""
    from harness.console.backend import composition
    from harness.console.backend.domain.approvals import CANCEL_REASON

    async def idle(*args: object, **kwargs: object) -> int:
        return 0

    with tempfile.TemporaryDirectory() as root:
        served = composition.job_service(Path(root), executor=idle)
        return {"commands": served.commands(section), "cancel_reason": CANCEL_REASON}


def fixtures() -> JsonObject:
    """Every fixture file name with its content."""
    opened = open_project().to_payload()
    updated = update().to_payload()
    diff: JsonObject = {"path": DIFF_PATH, "text": DIFF_TEXT}
    configured = configuration().to_payload()
    ru, en = help_sections("ru").to_payload(), help_sections("en").to_payload()
    return {
        "open-project.json": opened,
        "open-project-facts.json": open_project_facts(opened),
        "update-harness.json": updated,
        "update-harness-diff.json": diff,
        "update-harness-facts.json": {"page": update_facts(updated), "diff": diff_facts(diff)},
        # The server adds the wizard catalog of the shipped schemas (screen_facts).
        "configuration.json": {**configured, "wizard": wizard_parameters(Path(REPO))},
        "configuration-facts.json": configuration_facts(configured),
        "help-ru.json": ru,
        "help-en.json": en,
        "help-facts.json": help_facts(ru, en),
        "setup-catalog.json": catalog("setup"),
        "update-catalog.json": catalog("update"),
        "configuration-catalog.json": catalog("configuration"),
    }


def _text(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _committed(name: str) -> JsonObject:
    found = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    assert isinstance(found, dict)
    return found


def test_every_committed_fixture_and_facts_file_equals_the_rendered_one() -> None:
    for name, value in fixtures().items():
        expected = (FIXTURES / name).read_text(encoding="utf-8")
        if sys.platform == "win32" and name in {"open-project.json", "open-project-facts.json"}:
            expected = expected.replace("'/work/new service'", '\\"/work/new service\\"')
        assert expected == _text(posix(value)), (
            f"{name} is out of date: run "
            "`python -m tests.console.test_web_fixture_project_update_config_help`"
        )


def test_the_fixtures_decode_with_the_tui_codecs() -> None:
    assert OpenProjectFacts.from_payload(_committed("open-project.json")) == open_project()
    assert UpdateHarnessFacts.from_payload(_committed("update-harness.json")) == update()
    configured = _committed("configuration.json")
    wizard = configured.pop("wizard")
    assert ConfigurationFacts.from_payload(configured) == configuration()
    assert wizard == wizard_parameters(Path(REPO)) and wizard
    for language in ("ru", "en"):
        assert HelpSections.from_payload(
            _committed(f"help-{language}.json")
        ) == help_sections(language)
    # The diff fixture names a file the drift report lists: the server answers only for those.
    assert _committed("update-harness-diff.json")["path"] in diff_paths(DRIFT)


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="the facts files hold POSIX paths and shlex quoting; Windows renders its commands "
    "with subprocess.list2cmdline (open_project_snapshot.py) and its paths with backslashes",
)
def test_each_facts_file_is_what_the_tui_shows_for_its_fixture() -> None:
    opened = json.loads((FIXTURES / "open-project-facts.json").read_text(encoding="utf-8"))
    assert opened == open_project_facts(_committed("open-project.json"))
    assert "Git-проект найден · действие: обновление" in opened
    assert "harness console --web '/work/new service'" in opened
    updated = _committed("update-harness-facts.json")
    assert updated["page"] == update_facts(_committed("update-harness.json"))
    assert updated["diff"] == diff_facts(_committed("update-harness-diff.json"))
    assert "⚠ Обычное обновление остановится: 1 конфликт" in updated["page"]
    configured = json.loads((FIXTURES / "configuration-facts.json").read_text(encoding="utf-8"))
    assert configured == configuration_facts(
        {k: v for k, v in _committed("configuration.json").items() if k != "wizard"}
    )
    assert "⚠ требует обновления" in configured
    helped = _committed("help-facts.json")
    assert helped == help_facts(_committed("help-ru.json"), _committed("help-en.json"))
    assert helped["ru"][0] == "Окно консоли"


def test_the_catalog_fixtures_list_the_page_commands_behind_a_confirmation() -> None:
    for name, expected in (
        ("setup-catalog.json", ["setup-init", "setup-adopt", "setup-update"]),
        ("update-catalog.json", ["update", "update-force-managed", "update-seed-selected"]),
    ):
        commands = _committed(name)["commands"]
        assert isinstance(commands, list)
        assert [item["command_id"] for item in commands] == expected
        assert all(item["needs_confirmation"] for item in commands)


def main() -> None:
    for name, value in fixtures().items():
        (FIXTURES / name).write_text(_text(value), encoding="utf-8")


if __name__ == "__main__":
    main()
