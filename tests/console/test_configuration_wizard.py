"""The parameter catalog of the Settings wizard: every parameter is a real path of the installed
schema, with its type, choices, default and lower bound taken from the schema itself."""

from __future__ import annotations

from pathlib import Path

from harness.configuration_schema import load_schema
from harness.console.kernel.configuration_wizard import GROUPS, wizard_parameters

REPO = Path(__file__).resolve().parents[2]


def _node(file: str, path: list[str]) -> dict[str, object]:
    node: dict[str, object] = load_schema(REPO, file)
    for key in path:
        properties = node["properties"]
        assert isinstance(properties, dict)
        node = properties[key]
    return node


def test_the_groups_are_the_mockup_sections_and_each_has_a_parameter() -> None:
    params = wizard_parameters(REPO)
    assert [group for group, _label in GROUPS] == ["orchestrator", "project", "qa", "dispatch", "hooks"]
    assert {param["group"] for param in params} == {group for group, _label in GROUPS}


def test_each_parameter_takes_type_choices_and_default_from_the_schema() -> None:
    for param in wizard_parameters(REPO):
        path = param["path"]
        assert isinstance(path, list)
        node = _node(str(param["file"]), path)
        expected = "enum" if "enum" in node else node["type"]
        assert param["type"] == expected, param
        assert param["choices"] == node.get("enum", [])
        assert param["default"] == node.get("default")
        assert param["minimum"] == node.get("minimum")
        assert param["description"] == node.get("description", "")
        assert isinstance(param["label"], str) and param["label"]


def test_known_parameters_sit_in_their_groups() -> None:
    by_key = {(p["file"], ".".join(p["path"])): p for p in wizard_parameters(REPO)}  # type: ignore[arg-type]
    assert by_key[("orchestration.json", "approval_policy")]["group"] == "orchestrator"
    assert by_key[("orchestration.json", "approval_policy")]["choices"] == ["manual_all", "milestone", "low_risk", "auto"]
    assert by_key[("project.json", "language")]["group"] == "project"
    assert by_key[("orchestration.json", "execution_policy.qa_lease_seconds")]["group"] == "qa"
    assert by_key[("orchestration.json", "execution_policy.dispatch_wait_timeout_seconds")]["default"] == 60
    assert by_key[("project.json", "branch_pattern")]["group"] == "hooks"


def test_a_project_without_a_schema_has_no_parameters(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from harness.console.kernel import configuration_wizard

    def missing(repo: Path, name: str) -> dict[str, object]:
        raise ValueError("Схема отсутствует")

    monkeypatch.setattr(configuration_wizard, "load_schema", missing)
    assert wizard_parameters(tmp_path) == []
