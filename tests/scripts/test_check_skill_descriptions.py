"""Tests for scripts/check_skill_descriptions.py: format rules F1-F6 of skill descriptions."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import inspect
import types
from pathlib import Path

import pytest

from scripts import verify

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check_skill_descriptions.py"

GOOD = (
    "Publishes an approved specification as an epic. Use explicitly after /to-spec. "
    "Never changes production code."
)
BLOCK_POLICY = (
    'interface:\n  display_name: "X"\npolicy:\n  allow_implicit_invocation: false\n'
)


def _load() -> types.ModuleType:
    loader = importlib.machinery.SourceFileLoader(
        "check_skill_descriptions_under_test", str(SCRIPT)
    )
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


descriptions = _load()


def _skill(
    root: Path,
    name: str,
    description: str,
    *,
    layer: str = "skills/first-party/engineering",
    extra: str = "",
    openai_yaml: str | None = None,
) -> Path:
    directory = root / layer / name
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n{extra}---\n\nBody.\n",
        encoding="utf-8",
    )
    if openai_yaml is not None:
        (directory / "agents").mkdir(exist_ok=True)
        (directory / "agents" / "openai.yaml").write_text(openai_yaml, encoding="utf-8")
    return directory


def _registry(root: Path, rows: list[tuple[str, str]]) -> None:
    lines = [
        "# Skill Registry",
        "",
        "| Skill | Canonical path | When to use |",
        "|---|---|---|",
    ]
    lines.extend(
        f"| `{name}` | `skills/first-party/engineering/{name}` | {text} |"
        for name, text in rows
    )
    (root / "skills" / "REGISTRY.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def _tree(tmp_path: Path) -> Path:
    """A minimal repository whose neighbour names and registry make GOOD pass."""
    _skill(tmp_path, "to-spec", GOOD)
    _registry(tmp_path, [("to-spec", GOOD)])
    return tmp_path


def _problems(root: Path) -> list[str]:
    problems: list[str] = descriptions.check(root)[0]
    return problems


def test_a_description_that_follows_the_template_passes(tmp_path: Path) -> None:
    sut = _tree(tmp_path)

    assert _problems(sut) == []


def test_a_skill_without_an_invocation_condition_fails_with_f3(tmp_path: Path) -> None:
    sut = _tree(tmp_path)
    _skill(sut, "triage", "Moves issues through triage roles. Never closes a PR.")

    assert _problems(sut) == [
        "skills/first-party/engineering/triage/SKILL.md: F3 description has no invocation "
        'condition; add a sentence such as "Use when …", "Use explicitly after /<skill> …" '
        'or "Run once …"'
    ]


@pytest.mark.parametrize(
    "description",
    [
        "Use test-driven development to build behavior. Never skips Red.",
        "Stress-tests a plan. Use /grill-me when you only need context.",
    ],
)
def test_an_intent_or_a_neighbour_pointer_is_not_an_invocation_condition(
    tmp_path: Path, description: str
) -> None:
    sut = _tree(tmp_path)
    _skill(sut, "grill-me", "Interviews. Use explicitly before /to-spec.")
    _skill(sut, "tdd", description)

    assert [problem.split(": ")[1][:2] for problem in _problems(sut)] == ["F3"]


@pytest.mark.parametrize(
    "description",
    [
        "Creates labels. Run once per repo before first use.",
        "Creates labels listed in .harness/instructions/triage-labels.md. Run once per repo before first use.",
    ],
)
def test_a_description_without_a_refusal_or_a_neighbour_fails_with_f4(
    tmp_path: Path, description: str
) -> None:
    sut = _tree(tmp_path)
    _skill(
        sut,
        "triage",
        "Triages issues. Use explicitly for raw reports; not for tickets.",
    )
    _skill(sut, "setup-labels", description)

    assert _problems(sut) == [
        "skills/first-party/engineering/setup-labels/SKILL.md: F4 description has no boundary; "
        'add "not for …", "never …", or name the neighbour skill as /<skill>'
    ]


def test_a_vendor_neighbour_counts_as_a_boundary(tmp_path: Path) -> None:
    sut = _tree(tmp_path)
    _skill(
        sut, "domain-modeling", "Models.", layer="skills/vendor/upstream/engineering"
    )
    _skill(sut, "grill-with-docs", "Grills. Use explicitly with /domain-modeling.")

    assert _problems(sut) == []


def test_a_vendor_skill_without_a_condition_is_out_of_scope(tmp_path: Path) -> None:
    sut = _tree(tmp_path)
    _skill(sut, "ask-matt", "A router.", layer="skills/vendor/upstream/engineering")

    assert _problems(sut) == []


@pytest.mark.parametrize(("length", "expected"), [(500, []), (501, ["F2"])])
def test_the_description_limit_is_500_characters(
    tmp_path: Path, length: int, expected: list[str]
) -> None:
    sut = _tree(tmp_path)
    prefix = "Use explicitly after /to-spec. "
    _skill(sut, "publish-epic", prefix + "x" * (length - len(prefix)))

    assert [problem.split(": ")[1][:2] for problem in _problems(sut)] == expected


def test_a_block_scalar_description_fails_with_f1(tmp_path: Path) -> None:
    sut = _tree(tmp_path)
    directory = _skill(sut, "publish-epic", GOOD)
    (directory / "SKILL.md").write_text(
        "---\nname: publish-epic\ndescription: >\n  " + GOOD + "\n---\n",
        encoding="utf-8",
    )

    assert _problems(sut) == [
        "skills/first-party/engineering/publish-epic/SKILL.md: F1 description must be a "
        "non-empty single-line value; scripts/build_registry.py reads one line only"
    ]


def test_a_name_that_differs_from_the_directory_fails_with_f1(tmp_path: Path) -> None:
    sut = _tree(tmp_path)
    directory = _skill(sut, "publish-epic", GOOD)
    (directory / "SKILL.md").write_text(
        f"---\nname: publish\ndescription: {GOOD}\n---\n", encoding="utf-8"
    )

    assert _problems(sut) == [
        "skills/first-party/engineering/publish-epic/SKILL.md: F1 name 'publish' does not "
        "match directory 'publish-epic'"
    ]


def test_manual_invocation_without_a_codex_policy_fails_with_f5(tmp_path: Path) -> None:
    sut = _tree(tmp_path)
    _skill(sut, "publish-epic", GOOD, extra="disable-model-invocation: true\n")

    assert _problems(sut) == [
        "skills/first-party/engineering/publish-epic/SKILL.md: F5 disable-model-invocation: "
        "true requires agents/openai.yaml with policy.allow_implicit_invocation: false"
    ]


def test_manual_invocation_with_a_block_codex_policy_passes(tmp_path: Path) -> None:
    sut = _tree(tmp_path)
    _skill(
        sut,
        "publish-epic",
        GOOD,
        extra="disable-model-invocation: true\n",
        openai_yaml=BLOCK_POLICY,
    )

    assert _problems(sut) == []


def test_a_codex_policy_without_the_frontmatter_key_fails_with_f5(
    tmp_path: Path,
) -> None:
    sut = _tree(tmp_path)
    _skill(sut, "publish-epic", GOOD, openai_yaml=BLOCK_POLICY)

    assert _problems(sut) == [
        "skills/first-party/engineering/publish-epic/SKILL.md: F5 agents/openai.yaml sets "
        "allow_implicit_invocation: false but SKILL.md lacks disable-model-invocation: true"
    ]


def test_a_false_frontmatter_key_fails_with_f5(tmp_path: Path) -> None:
    sut = _tree(tmp_path)
    _skill(sut, "publish-epic", GOOD, extra="disable-model-invocation: false\n")

    assert _problems(sut) == [
        "skills/first-party/engineering/publish-epic/SKILL.md: F5 disable-model-invocation "
        "must be true or absent, got 'false'"
    ]


def test_the_registry_budget_is_enforced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sut = _tree(tmp_path)
    _skill(
        sut,
        "publish-epic",
        GOOD,
        extra="disable-model-invocation: true\n",
        openai_yaml=BLOCK_POLICY,
    )
    _registry(sut, [("to-spec", GOOD), ("publish-epic", GOOD)])
    monkeypatch.setattr(descriptions, "REGISTRY_BUDGET", 2 * len(GOOD) - 1)

    assert _problems(sut) == [
        f"skills/REGISTRY.md: F6 first-party descriptions total {2 * len(GOOD)} characters; "
        f"the budget is {2 * len(GOOD) - 1}"
    ]


def test_the_model_invoked_budget_counts_only_model_invoked_skills(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sut = _tree(tmp_path)
    _skill(
        sut,
        "publish-epic",
        GOOD,
        extra="disable-model-invocation: true\n",
        openai_yaml=BLOCK_POLICY,
    )
    _registry(sut, [("to-spec", GOOD), ("publish-epic", GOOD)])
    monkeypatch.setattr(descriptions, "MODEL_INVOKED_BUDGET", len(GOOD) - 1)

    assert _problems(sut) == [
        f"skills/REGISTRY.md: F6 model-invoked first-party descriptions total {len(GOOD)} "
        f"characters; the budget is {len(GOOD) - 1}"
    ]


def test_the_command_reports_ok_on_a_passing_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(descriptions, "ROOT", _tree(tmp_path))

    code = descriptions.main()

    assert code == 0
    assert capsys.readouterr().out.startswith("skill-descriptions: ok (1 skills;")


def test_the_command_fails_with_a_problem_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    sut = _tree(tmp_path)
    _skill(sut, "triage", "Moves issues. Never closes a PR.")
    monkeypatch.setattr(descriptions, "ROOT", sut)

    code = descriptions.main()

    assert code == 1
    assert capsys.readouterr().err.endswith("skill-descriptions: 1 problem(s)\n")


def test_make_verify_runs_the_check_after_the_registry_comparison() -> None:
    source = inspect.getsource(verify._static_checks)

    assert "check_skill_descriptions.py" in source
    assert source.index("skills/REGISTRY.md") < source.index(
        "check_skill_descriptions.py"
    )
