"""Установка, выбор capability и обновление harness: сценарий clean-room из `scripts/test_clean_room.py`."""

from __future__ import annotations

import filecmp
import hashlib
import json
import re
import sys
from types import SimpleNamespace

from harness.bin import harness as harness_cli
from harness.health.project_files import frontmatter_metadata
from harness.orchestration.core.constants import STATE_REL
from harness.seed_links import RULES_POINTER

from scripts.clean_room.support import (
    HARNESS,
    apply_patch,
    assert_contract_link,
    ROOT,
    capture,
    capture_json,
    check_technical_english,
    count_skill_files,
    fail_json,
    fill_agents,
    find_check,
    run_fails,
    run_health,
    run_ok,
    starts_with_text,
    run_step,
)


def run(ctx: SimpleNamespace) -> None:
    """Установка, выбор capability и обновление harness.

    Читает из контекста: `test_root`.
    Передаёт дальше: `pv_project`, `target_home`.
    """
    test_root = ctx.test_root
    project = test_root / "project"
    foundation = test_root / "foundation"
    target_home = test_root / "home"
    for d in (project, foundation, target_home):
        d.mkdir(parents=True)
    run_step(["git", "init", "-q"], cwd=project, check=True)
    run_step(["git", "init", "-q"], cwd=foundation, check=True)

    run_ok(
        HARNESS
        + [
            "init",
            str(foundation),
            "--project-type",
            "content",
            "--base-branch",
            "main",
        ]
    )
    check_technical_english(foundation)
    # Model an older standard installation with project-owned entry points.
    original_entries = {
        name: (foundation / name).read_bytes() for name in ("AGENTS.md", "CLAUDE.md")
    }
    old_agents = "# Local instructions\n\nKeep the project glossary in Russian.\n"
    old_claude = "# Local Claude instructions\n\nRun the focused checks first.\n"
    (foundation / "AGENTS.md").write_text(old_agents, encoding="utf-8")
    (foundation / "CLAUDE.md").write_text(old_claude, encoding="utf-8")
    contract = foundation / ".harness/instructions/technical-english.md"
    contract.unlink()
    old_lock_path = foundation / ".harness/harness.lock"
    old_lock = json.loads(old_lock_path.read_text(encoding="utf-8"))
    old_lock["files"].pop(".harness/instructions/technical-english.md")
    old_lock_path.write_text(json.dumps(old_lock), encoding="utf-8")
    update_output = capture(HARNESS + ["update", str(foundation)])
    if (
        contract.read_bytes()
        != (ROOT / "harness/project/instructions/technical-english.md").read_bytes()
    ):
        sys.exit("standard update did not deliver the managed contract")
    for name, original in (("AGENTS.md", old_agents), ("CLAUDE.md", old_claude)):
        if (foundation / name).read_text(encoding="utf-8") != original:
            sys.exit("update changed project-owned instructions before approval")
        if f"--- a/{name}" not in update_output or f"+++ b/{name}" not in update_output:
            sys.exit("update did not show a reviewable entry-point addition")
    diff_output = capture(HARNESS + ["diff", str(foundation)])
    patch = diff_output[diff_output.index("diff --git ") :]
    if patch != update_output[update_output.index("diff --git ") :]:
        sys.exit("diff and update proposed different seed adaptations")
    # Approval is an ordinary edit/patch after review; the CLI never applies seeds.
    apply_patch(patch, foundation)
    check_technical_english(foundation)
    approved = {
        name: (foundation / name).read_bytes() for name in ("AGENTS.md", "CLAUDE.md")
    }
    for name, original in (("AGENTS.md", old_agents), ("CLAUDE.md", old_claude)):
        if not starts_with_text(approved[name], original):
            sys.exit("approved additions lost local instructions")
    repeated = capture(HARNESS + ["update", str(foundation)])
    repeated += capture(HARNESS + ["diff", str(foundation)])
    if "diff --git " in repeated:
        sys.exit("repeat update proposed an already connected contract link")
    if any(
        (foundation / name).read_bytes() != content
        for name, content in approved.items()
    ):
        sys.exit("repeat update changed approved project instructions")
    check_technical_english(foundation)

    # An existing import in either direction already reaches a mandatory source.
    # Later entry-point cases check only the Technical English link; the Codex rules
    # pointer is already present there.
    old_agents += "\n" + RULES_POINTER
    (foundation / "AGENTS.md").write_text(
        old_agents + "\n@CLAUDE.md\n", encoding="utf-8"
    )
    if capture_json(HARNESS + ["diff", str(foundation), "--json"])[
        "seed_link_proposals"
    ]:
        sys.exit("diff proposed a duplicate for an existing entry-point transition")
    # A passive reference needs an explicit obligation, without a second link.
    passive = (
        old_claude + "\nSee [Technical English](.harness/instructions/technical-english.md).\n"
    )
    (foundation / "CLAUDE.md").write_text(passive, encoding="utf-8")
    proposal_output = capture(HARNESS + ["update", str(foundation)])
    if "no recognized mandatory reading instruction" not in proposal_output:
        sys.exit("ambiguous reference did not explain the proposed obligation")
    patch = proposal_output[proposal_output.index("diff --git ") :]
    if "technical-english.md" in "\n".join(
        line
        for line in patch.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    ):
        sys.exit("passive reference proposal duplicated an existing contract link")
    apply_patch(patch, foundation)
    if capture_json(HARNESS + ["diff", str(foundation), "--json"])[
        "seed_link_proposals"
    ]:
        sys.exit("approved passive-reference obligation was proposed again")

    # A valid Markdown title does not disconnect an existing mandatory link.
    for title in ('"Shared contract"', "'Shared contract'", "(Shared contract)"):
        titled = (
            old_agents + "\nBefore the first English handoff, agents must read "
            f"[Technical English](.harness/instructions/technical-english.md {title}).\n"
        )
        (foundation / "AGENTS.md").write_text(titled, encoding="utf-8")
        (foundation / "CLAUDE.md").write_text(
            old_claude + "\n@AGENTS.md\n", encoding="utf-8"
        )
        titled_entries = {
            name: (foundation / name).read_bytes()
            for name in ("AGENTS.md", "CLAUDE.md")
        }
        for _ in range(2):
            if capture_json(HARNESS + ["diff", str(foundation), "--json"])[
                "seed_link_proposals"
            ]:
                sys.exit(
                    f"diff proposed a duplicate for a mandatory link with title {title}"
                )
            if "diff --git " in capture(HARNESS + ["update", str(foundation)]):
                sys.exit(
                    f"update proposed a duplicate for a mandatory link with title {title}"
                )
            if any(
                (foundation / name).read_bytes() != content
                for name, content in titled_entries.items()
            ):
                sys.exit(
                    "repeated update changed entry points with a titled contract link"
                )

    # A fenced example cannot supply the obligation for a passive reference.
    for fence in ("```", "~~~"):
        fenced = (
            old_agents
            + "\nSee [Technical English](.harness/instructions/technical-english.md).\n\n"
            + fence
            + "\nBefore the first English handoff, agents must read the contract linked above.\n"
            + fence
            + "\n"
        )
        (foundation / "AGENTS.md").write_text(fenced, encoding="utf-8")
        before = {
            name: (foundation / name).read_bytes()
            for name in ("AGENTS.md", "CLAUDE.md")
        }
        proposals = capture_json(HARNESS + ["diff", str(foundation), "--json"])[
            "seed_link_proposals"
        ]
        if [item["path"] for item in proposals] != ["AGENTS.md"]:
            sys.exit("fenced example suppressed the required reading obligation")
        output = capture(HARNESS + ["update", str(foundation)])
        if "no recognized mandatory reading instruction" not in output:
            sys.exit("update treated a fenced example as an active reading obligation")
        patch = output[output.index("diff --git ") :]
        if patch != proposals[0]["diff"]:
            sys.exit("diff and update disagree on the missing non-fenced obligation")
        if any(
            (foundation / name).read_bytes() != content
            for name, content in before.items()
        ):
            sys.exit("update changed the fenced example before approval")
        apply_patch(patch, foundation)
        if not (foundation / "AGENTS.md").read_bytes().startswith(before["AGENTS.md"]):
            sys.exit("approved obligation changed the existing fenced example")
        if capture_json(HARNESS + ["diff", str(foundation), "--json"])[
            "seed_link_proposals"
        ] or "diff --git " in capture(HARNESS + ["update", str(foundation)]):
            sys.exit("approved non-fenced obligation was proposed again")

    for name, content in original_entries.items():
        (foundation / name).write_bytes(content)

    run_ok(HARNESS + ["diff", str(foundation)])
    if not run_fails(HARNESS + ["health", str(foundation)], quiet_all=True):
        sys.exit("unresolved AGENTS.md unexpectedly passed health")
    fill_agents(foundation)
    run_health(foundation)
    if count_skill_files(foundation / ".harness" / "skills") != 5:
        sys.exit("expected 5 skills in foundation")
    if "- Type: content" not in (foundation / "AGENTS.md").read_text(encoding="utf-8"):
        sys.exit("AGENTS.md missing '- Type: content'")
    if "| `grilling` | `.harness/skills/grilling` |" not in (
        foundation / ".harness" / "skills" / "REGISTRY.md"
    ).read_text(encoding="utf-8"):
        sys.exit("REGISTRY.md missing grilling entry")

    run_ok(
        HARNESS
        + [
            "init",
            str(project),
            "--stack",
            "node",
            "--capability",
            "mattpocock-suite",
            "--base-branch",
            "main",
        ]
    )
    fill_agents(project)
    check_technical_english(project)

    run_ok(HARNESS + ["diff", str(project)])
    run_health(project)

    if count_skill_files(project / ".harness" / "skills") != 25:
        sys.exit("expected 25 skills in project")
    if (project / ".agents" / "skills").readlink().as_posix() != "../.harness/skills":
        sys.exit(".agents/skills does not link to ../.harness/skills")
    if (project / ".claude" / "skills").readlink().as_posix() != "../.harness/skills":
        sys.exit(".claude/skills does not link to ../.harness/skills")

    list_output = capture(HARNESS + ["list", str(project)])
    lines = list_output.splitlines()
    if lines != sorted(lines):
        sys.exit("harness list output is not sorted")
    if "ask-matt" not in lines:
        sys.exit("ask-matt missing from harness list output")

    registry_path = project / ".harness" / "skills" / "REGISTRY.md"
    registry_path.write_text("corrupted\n", encoding="utf-8")
    run_ok(HARNESS + ["registry", str(project)])
    if "| `ask-matt` |" not in registry_path.read_text(encoding="utf-8"):
        sys.exit(
            "standalone 'harness registry' did not regenerate REGISTRY.md correctly"
        )

    with (project / ".harness" / "skills" / "ask-matt" / "SKILL.md").open(
        "a", encoding="utf-8"
    ) as f:
        f.write("\nlocal edit\n")
    if not run_fails(HARNESS + ["diff", str(project)], quiet_all=True):
        sys.exit("drift check unexpectedly passed")
    if not run_fails(HARNESS + ["update", str(project)], quiet_all=True):
        sys.exit("non-forced update unexpectedly overwrote a local edit")
    run_ok(HARNESS + ["update", str(project), "--force"], quiet=True)
    run_health(project)

    (project / ".mcp.json").write_text('{"mcpServers": {}}\n', encoding="utf-8")
    if not run_fails(HARNESS + ["health", str(project)], quiet_all=True):
        sys.exit("uninventoried project integration unexpectedly passed health")

    mcp_config = project / ".mcp.json"
    integrations_payload = {
        "schema": 1,
        "integrations": [
            {
                "id": "test-mcp",
                "kind": "mcp",
                "runtimes": ["codex"],
                "config": ".mcp.json",
                "sha256": hashlib.sha256(mcp_config.read_bytes()).hexdigest(),
                "secret_refs": ["TEST_MCP_TOKEN"],
                "verify": "Open a fresh session and list MCP tools.",
            }
        ],
    }
    (project / ".harness" / "integrations.json").write_text(
        json.dumps(integrations_payload, indent=2) + "\n", encoding="utf-8"
    )
    run_health(project)

    # Selecting a capability together with a second one that overrides the same names by a
    # different source path must fail loudly (docs/adr/0001) instead of picking one silently.
    dup_project = test_root / "dup_project"
    dup_project.mkdir(parents=True)
    run_step(["git", "init", "-q"], cwd=dup_project, check=True)
    if not run_fails(
        HARNESS
        + [
            "init",
            str(dup_project),
            "--capability",
            "mattpocock-suite",
            "--capability",
            "engineering-suite",
        ],
        quiet_all=True,
    ):
        sys.exit(
            "selecting mattpocock-suite and engineering-suite together unexpectedly succeeded"
        )

    # engineering-suite inherits 25 upstream skills, overrides some of them in place, and adds 8 names;
    # the clean-room check below expects 34 distinct installed skills (ADR 0001).
    pv_project = test_root / "pv_project"
    pv_project.mkdir(parents=True)
    run_step(["git", "init", "-q"], cwd=pv_project, check=True)
    run_ok(
        HARNESS
        + [
            "init",
            str(pv_project),
            "--capability",
            "engineering-suite",
            "--base-branch",
            "main",
            "--language",
            "ru",
            "--pr-base-branch",
            "main",
            "--branch-pattern",
            "^release/rel-[0-9]+-.+",
            "--qa-gate-command",
            "echo test",
        ]
    )
    # Provenance matters: target docs/agents are intentionally identical to their
    # templates, so comparing bytes against root docs/ would reject a valid install.
    root_docs = (ROOT / "docs").resolve()
    selected = ["engineering-suite"]
    sources = harness_cli.selected_skills(selected) + harness_cli.selected_resources(
        selected
    )
    if any(source.resolve().is_relative_to(root_docs) for source in sources):
        sys.exit("package_files selected a source from repository docs/")
    payload = harness_cli.package_files(selected)
    if any(not path.startswith(".harness/") for path in payload):
        sys.exit("package_files emitted a path outside .harness/")
    for destination, expected in payload.items():
        if (pv_project / destination).read_bytes() != expected:
            sys.exit(f"installed package differs from selected source: {destination}")
    # The managed instructions of the same template folder go to `.harness/instructions/`.
    seed_guides = harness_cli.seed_sources(
        harness_cli.PROJECT_TEMPLATE_DIR, "instructions", frozenset({".md"})
    )
    installed_docs = pv_project / "docs" / "agents"
    if {path.name for path in installed_docs.glob("*.md")} != {
        path.name for path in seed_guides
    }:
        sys.exit("target docs/agents did not come only from project templates")
    for source in seed_guides:
        if (installed_docs / source.name).read_bytes() != source.read_bytes():
            sys.exit(f"installed guide differs from project template: {source.name}")
    fill_agents(pv_project)
    check_technical_english(pv_project)
    # Existing root entry points are already connected; only the older agent seed
    # needs adaptation. A missing final newline must survive the reviewed patch.
    for name in ("code-review-spec.md", "code-review-standards.md"):
        entry = pv_project / ".claude/agents" / name
        entry.write_text(
            entry.read_text(encoding="utf-8") + "\n@../../AGENTS.md\n", encoding="utf-8"
        )
    agent = pv_project / ".claude/agents/pr-composer.md"
    test_author = pv_project / ".claude/agents/test-author.md"
    original_agent = (
        agent.read_bytes() + b"\nLocal review instructions without final newline"
    )
    original_test_author = test_author.read_bytes()
    agent.write_bytes(original_agent)
    untouched = pv_project / "docs/local-agent-notes.md"
    untouched.write_text(
        "Local notes are not a harness entry point.\n", encoding="utf-8"
    )
    seed_snapshot = {
        path: path.read_bytes()
        for path in (
            pv_project / "AGENTS.md",
            pv_project / "CLAUDE.md",
            agent,
            untouched,
        )
    }
    output = capture(HARNESS + ["update", str(pv_project)])
    if any(path.read_bytes() != content for path, content in seed_snapshot.items()):
        sys.exit("pvmalove update modified an unapproved seed")
    proposal = capture_json(HARNESS + ["diff", str(pv_project), "--json"])[
        "seed_link_proposals"
    ]
    if [item["path"] for item in proposal] != [
        ".claude/agents/pr-composer.md",
        ".claude/agents/test-author.md",
    ]:
        sys.exit(
            "update proposed links for already connected or unrelated entry points"
        )
    patch = output[output.index("diff --git ") :]
    expected_patch = "".join(item["diff"] for item in proposal)
    if patch != expected_patch:
        sys.exit("JSON diff differs from the visible update proposal")
    apply_patch(patch, pv_project)
    assert_contract_link(
        agent, pv_project / ".harness/instructions/technical-english.md", "installed agent seed"
    )
    assert_contract_link(
        test_author,
        pv_project / ".harness/instructions/technical-english.md",
        "installed test-author seed",
    )
    patched = agent.read_bytes()
    # A Windows checkout writes CRLF while the fixture suffix and the patch are LF.
    if not patched.replace(b"\r\n", b"\n").startswith(
        original_agent.replace(b"\r\n", b"\n")
    ):
        sys.exit(
            "approved agent addition lost local instructions: "
            f"expected prefix tail {original_agent[-60:]!r}, "
            f"got {patched[len(original_agent) - 60 : len(original_agent)]!r}"
        )
    approved_agent = agent.read_bytes()
    if "diff --git " in capture(HARNESS + ["update", str(pv_project)]):
        sys.exit("repeat pvmalove update proposed duplicate links")
    if capture_json(HARNESS + ["diff", str(pv_project), "--json"])[
        "seed_link_proposals"
    ]:
        sys.exit("repeat JSON diff proposed duplicate links")
    if (
        agent.read_bytes() != approved_agent
        or untouched.read_bytes() != seed_snapshot[untouched]
    ):
        sys.exit("repeat pvmalove update changed local instructions")
    # Keep subsequent installer baseline checks independent of approved seed edits.
    agent.write_bytes(original_agent)
    test_author.write_bytes(original_test_author)

    run_health(pv_project)
    repo_map_health = find_check(
        capture_json(HARNESS + ["health", str(pv_project), "--json"]), "repo_map.tier"
    )
    if repo_map_health["status"] != "warn":
        sys.exit("health did not mark the degraded Repo Map tier as a warning")
    if not repo_map_health["message"].startswith("Repo Map: tier=minimal"):
        sys.exit("health did not report the degraded Repo Map tier")
    if (
        "provenance: offline parser bundle unavailable"
        not in repo_map_health["message"]
    ):
        sys.exit("health did not report missing Repo Map bundle provenance")
    repo_map_fix = repo_map_health["fix"]["text"] if repo_map_health["fix"] else ""
    if "установите offline parser bundle" not in repo_map_fix:
        sys.exit("health did not provide the offline Repo Map remedy")
    if "uv run" in repo_map_fix:
        sys.exit("health incorrectly offered uv run as a Repo Map dispatch remedy")
    corrupt_registry = (
        pv_project
        / ".harness"
        / ".sandboxes"
        / "cache"
        / "repo_map"
        / "parser_bundle"
        / "registry"
    )
    corrupt_registry.mkdir(parents=True)
    (corrupt_registry / "parser_bundle.lock.json").write_text(
        "{invalid", encoding="utf-8"
    )
    corrupt_bundle_health = find_check(
        capture_json(HARNESS + ["health", str(pv_project), "--json"]), "repo_map.tier"
    )
    if not corrupt_bundle_health["message"].startswith("Repo Map: tier=minimal"):
        sys.exit("health accepted a corrupt Repo Map bundle as full tier")
    if corrupt_bundle_health["status"] == "ok":
        sys.exit("health reported a corrupt Repo Map bundle as full tier")
    repo_map_cli = pv_project / ".harness" / "repo_map" / "repo_map.py"
    if (
        not repo_map_cli.is_file()
        or not (pv_project / ".harness" / "token_estimator.py").is_file()
        or not (pv_project / ".harness" / "repo_map" / "repo_map.schema.json").is_file()
    ):
        sys.exit("engineering-suite Repo Map resource missing")
    if not (pv_project / ".harness" / "health" / "registry.py").is_file():
        sys.exit("engineering-suite health resource missing")
    map_project = test_root / "map_project"
    map_project.mkdir()
    run_step(["git", "init", "-q"], cwd=map_project, check=True)
    (map_project / "mapped.py").write_text(
        "def mapped(value: int = 1) -> int:\n    return value\n", encoding="utf-8"
    )
    run_step(["git", "add", "mapped.py"], cwd=map_project, check=True)
    run_step(
        [
            "git",
            "-c",
            "user.email=test@example.invalid",
            "-c",
            "user.name=Test",
            "commit",
            "-qm",
            "fixture",
        ],
        cwd=map_project,
        check=True,
    )
    mapped_commit = capture(
        ["git", "-C", str(map_project), "rev-parse", "HEAD"]
    ).strip()
    mapped = json.loads(
        capture(
            [
                sys.executable,
                str(repo_map_cli),
                "--repo",
                str(map_project),
                "--commit",
                mapped_commit,
            ]
        )
    )
    if not any(item["path"] == "mapped.py" for item in mapped["files"]):
        sys.exit("installed Repo Map did not read the pinned commit")

    pv_skill_count = count_skill_files(pv_project / ".harness" / "skills")
    if pv_skill_count != 34:
        sys.exit(
            f"expected 34 skills in a engineering-suite project (25 inherited, overrides replaced in place, + 9 additions), found {pv_skill_count}"
        )

    # A failed older update could remove a retired managed skill's SKILL.md but leave
    # its empty top-level directory behind. A forced update must recover instead of
    # making registry generation fail on that stale directory.
    retired_skill_dir = pv_project / ".harness" / "skills" / "run-workflow"
    retired_skill_dir.mkdir()
    run_ok(HARNESS + ["update", str(pv_project), "--force"])
    if retired_skill_dir.exists():
        sys.exit("update did not remove an empty retired skill directory")
    run_health(pv_project)
    check_tracker_field(pv_project)
    check_hook_settings_merge(pv_project)
    check_tracker_from_origin(test_root)
    check_package_root_without_init(test_root)
    check_runtime_rules(test_root)
    check_workflow_procedures(test_root)
    to_spec_source = ROOT / "skills" / "first-party" / "engineering" / "to-spec"
    for discovery in (".harness", ".claude", ".agents"):
        for relative in (
            "SKILL.md",
            "agents/openai.yaml",
            "references/spec-template.md",
            "references/drill-down-template.md",
        ):
            installed = pv_project / discovery / "skills" / "to-spec" / relative
            if not installed.is_file() or not filecmp.cmp(
                to_spec_source / relative, installed, shallow=False
            ):
                sys.exit(
                    f"engineering-suite did not expose {installed.relative_to(pv_project)}"
                )
    # Issue #1208: to-tickets loads its ticket template and publication steps lazily, and
    # publish-epic owns epic publication; every discovery root exposes both complete skills.
    skill_files = {
        "to-tickets": (
            "SKILL.md",
            "agents/openai.yaml",
            "references/ticket-template.md",
            "references/publish.md",
        ),
        "publish-epic": ("SKILL.md", "agents/openai.yaml"),
    }
    for name, relatives in skill_files.items():
        source_dir = ROOT / "skills" / "first-party" / "engineering" / name
        for discovery in (".harness", ".claude", ".agents"):
            for relative in relatives:
                installed = pv_project / discovery / "skills" / name / relative
                if not installed.is_file() or not filecmp.cmp(
                    source_dir / relative, installed, shallow=False
                ):
                    sys.exit(
                        f"engineering-suite did not expose {installed.relative_to(pv_project)}"
                    )
    to_tickets_text = "\n".join(
        (pv_project / ".harness" / "skills" / "to-tickets" / relative).read_text(
            encoding="utf-8"
        )
        for relative in skill_files["to-tickets"]
    )
    for required_text in (
        "Path inventory",
        "one advisory sub-agent call",
        "stop and report it",
        "result dependency",
        "known requirement incompatibility",
        "File overlap alone is not a blocker",
        "`**Status** — Approved`",
        "## Parent: #<epic>",
    ):
        if required_text not in to_tickets_text:
            sys.exit(f"to-tickets discovery contract is missing: {required_text}")
    # The release rule must reach every installed place that states it, not only to-tickets.
    for rule_file in (
        pv_project / ".harness" / "skills" / "to-pull-requests" / "SKILL.md",
        pv_project / "docs" / "agents" / "triage-labels.md",
    ):
        if "accepted QA" not in rule_file.read_text(encoding="utf-8"):
            sys.exit(f"blocker release rule is missing from {rule_file.name}")
    # Issue #537: the PR step installed without the orchestration capability keeps the plain
    # /qa-gate route and still carries the whole PR continuation for an opt-in project.
    pr_step_text = (
        pv_project / ".harness" / "skills" / "to-pull-requests" / "SKILL.md"
    ).read_text(encoding="utf-8")
    for required_text in ("integration next", "separate confirmation", "/qa-gate"):
        if required_text not in pr_step_text:
            sys.exit(f"installed to-pull-requests step lacks: {required_text}")
    for name in (
        "grill-me",
        "grill-with-docs",
        "diagnosing-bugs",
        "architect",
        "developer",
        "tdd",
    ):
        if not filecmp.cmp(
            ROOT / "skills" / "first-party" / "engineering" / name / "SKILL.md",
            pv_project / ".harness" / "skills" / name / "SKILL.md",
            shallow=False,
        ):
            sys.exit(f"engineering-suite override did not install the first-party {name}")
    # Issue 1156: both runtime discovery links resolve the installed developer skill.
    for discovery in (".claude", ".agents"):
        if not (pv_project / discovery / "skills" / "developer" / "SKILL.md").is_file():
            sys.exit(f"{discovery}/skills does not resolve the developer skill")
    # Issue #552: the installed registry lists the first-party tdd, and the update baseline
    # records no drift for its files.
    _, tdd_description = frontmatter_metadata(
        ROOT / "skills" / "first-party" / "engineering" / "tdd" / "SKILL.md"
    )
    if f"| `tdd` | `.harness/skills/tdd` | {tdd_description} |" not in (
        pv_project / ".harness" / "skills" / "REGISTRY.md"
    ).read_text(encoding="utf-8"):
        sys.exit("installed REGISTRY.md does not list the first-party tdd")
    pv_drift = capture_json(HARNESS + ["diff", str(pv_project), "--json"])
    tdd_drift = [
        path
        for key in (
            "added",
            "missing",
            "package_changed",
            "local_changed",
            "conflict",
            "retired",
        )
        for path in pv_drift[key]
        if path.startswith(".harness/skills/tdd/")
    ]
    if tdd_drift:
        sys.exit(f"installed first-party tdd has unconfirmed drift: {tdd_drift}")
    if not filecmp.cmp(
        ROOT
        / "skills"
        / "vendor"
        / "mattpocock"
        / "engineering"
        / "research"
        / "SKILL.md",
        pv_project / ".harness" / "skills" / "research" / "SKILL.md",
        shallow=False,
    ):
        sys.exit(
            "engineering-suite unexpectedly changed a skill it neither overrides nor adds"
        )
    if not filecmp.cmp(
        ROOT / "harness" / "project" / "instructions" / "project-memory.md",
        pv_project / ".harness" / "instructions" / "project-memory.md",
        shallow=False,
    ):
        sys.exit("engineering-suite did not install the interactive memory contract")
    for human_guide in ("harness-guide.md", "backend-orchestration.md"):
        if (pv_project / ".harness" / "instructions" / human_guide).exists():
            sys.exit(f"engineering-suite installed a developer guide: {human_guide}")
    # An older installation delivered the guides; update must retire them without touching others.
    stale_lock_path = pv_project / ".harness" / "harness.lock"
    stale_lock = json.loads(stale_lock_path.read_text(encoding="utf-8"))
    for human_guide in ("harness-guide.md", "backend-orchestration.md"):
        stale = pv_project / ".harness" / "instructions" / human_guide
        stale.write_text("# legacy copy\n", encoding="utf-8")
        stale_lock["files"][f".harness/instructions/{human_guide}"] = hashlib.sha256(
            stale.read_bytes()
        ).hexdigest()
    stale_lock_path.write_text(json.dumps(stale_lock), encoding="utf-8")
    capture(HARNESS + ["update", str(pv_project)])
    for human_guide in ("harness-guide.md", "backend-orchestration.md"):
        if (pv_project / ".harness" / "instructions" / human_guide).exists():
            sys.exit(f"update kept a retired developer guide: {human_guide}")
    if not (pv_project / ".harness" / "instructions" / "project-memory.md").is_file():
        sys.exit("update removed the interactive memory contract")
    qa_gate_skill = pv_project / ".harness" / "skills" / "qa-gate" / "SKILL.md"
    if not qa_gate_skill.is_file():
        sys.exit("engineering-suite addition qa-gate missing")
    if "test_summary.py" not in qa_gate_skill.read_text(encoding="utf-8"):
        sys.exit("qa-gate does not route quality commands through the summary wrapper")
    pytest_summary = (
        pv_project / ".harness" / "skills" / "qa-gate" / "scripts" / "test_summary.py"
    )
    if pytest_summary.exists():
        pytest_summary.unlink()
    run_ok(HARNESS + ["update", str(pv_project), "--force"])
    if not pytest_summary.is_file():
        sys.exit("update did not install the qa-gate pytest summary wrapper")
    passing_summary = run_step(
        [
            sys.executable,
            str(pytest_summary),
            "--",
            sys.executable,
            "-c",
            "print('3 passed in 0.01s'); print('PASSING_NOISE')",
        ],
        cwd=pv_project,
        capture_output=True,
        text=True,
        check=False,
    )
    if passing_summary.returncode != 0:
        sys.exit("pytest summary wrapper rejected a passing command")
    if "PASS" not in passing_summary.stdout or "3 passed" not in passing_summary.stdout:
        sys.exit("pytest summary wrapper did not report a compact pass result")
    if "PASSING_NOISE" in passing_summary.stdout:
        sys.exit("pytest summary wrapper leaked passing command output")
    failing_summary = run_step(
        [
            sys.executable,
            str(pytest_summary),
            "--",
            sys.executable,
            "-c",
            (
                "import sys; print('=== short test summary info ==='); "
                "print('FAILED tests/test_checkout.py::test_quote - AssertionError: gho_abcdefghijklmnopqrstuvwxyz1234567890'); "
                "print('Traceback (most recent call last):'); "
                "print('  File tests/test_checkout.py, line 12, in test_quote'); "
                "print('RuntimeError: gho_abcdefghijklmnopqrstuvwxyz1234567890'); "
                "print('src/check.py:7:4: error: incompatible types'); "
                "print('1 failed, 2 passed in 0.01s'); sys.exit(1)"
            ),
        ],
        cwd=pv_project,
        capture_output=True,
        text=True,
        check=False,
    )
    if failing_summary.returncode != 1:
        sys.exit(
            "pytest summary wrapper did not preserve the failing command exit code"
        )
    if "tests/test_checkout.py::test_quote" not in failing_summary.stdout:
        sys.exit("pytest summary wrapper did not retain the failed test node ID")
    for expected_diagnostic in (
        "Traceback: RuntimeError: <REDACTED_GITHUB_TOKEN>",
        "Error: src/check.py:7:4: incompatible types",
    ):
        if expected_diagnostic not in failing_summary.stdout:
            sys.exit(
                "pytest summary wrapper did not extract a structured failure diagnostic"
            )
    if "gho_abcdefghijklmnopqrstuvwxyz1234567890" in failing_summary.stdout:
        sys.exit("pytest summary wrapper leaked a secret into its bounded summary")
    log_match = re.search(
        r"^Full log: (.+)$", failing_summary.stdout, flags=re.MULTILINE
    )
    if not log_match:
        sys.exit("pytest summary wrapper did not provide a failure-log path")
    failure_log = pv_project / log_match.group(1).strip()
    if (
        not failure_log.is_file()
        or "gho_abcdefghijklmnopqrstuvwxyz1234567890"
        in failure_log.read_text(encoding="utf-8")
    ):
        sys.exit("pytest summary wrapper did not save a sanitized failure log")
    ctx.pv_project = pv_project
    ctx.target_home = target_home


def check_hook_settings_merge(pv_project) -> None:
    """`update` сливает managed hook-записи: добавляет недостающую, сохраняет запись пользователя,
    не трогает правку managed-записи и при повторном запуске ничего не меняет."""
    config = ".claude/settings.local.json"
    settings = pv_project / config
    document = json.loads(settings.read_text(encoding="utf-8"))
    bash_group = next(
        group for group in document["hooks"]["PreToolUse"] if group["matcher"] == "Bash"
    )
    user_hook = {"type": "command", "command": "bash scripts/user-guard.sh"}
    bash_group["hooks"] = [
        hook
        for hook in bash_group["hooks"]
        if "block-pr-merge.sh" not in hook["command"]
    ] + [user_hook]
    settings.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")

    first = capture(HARNESS + ["update", str(pv_project)])
    merged = json.loads(settings.read_text(encoding="utf-8"))
    commands = [
        hook["command"]
        for group in merged["hooks"]["PreToolUse"]
        for hook in group["hooks"]
    ]
    if sum("block-pr-merge.sh" in command for command in commands) != 1:
        sys.exit("update did not restore the removed managed hook entry once")
    if commands.count(user_hook["command"]) != 1:
        sys.exit("update dropped or duplicated a user hook entry")
    if "added=1 replaced=0" not in first:
        sys.exit("update did not report the added managed hook entry")

    settings_before = settings.read_bytes()
    second = capture(HARNESS + ["update", str(pv_project)])
    if settings.read_bytes() != settings_before:
        sys.exit("a repeated update changed the merged hook settings")
    if "added=0 replaced=0" not in second or "hooks check:" not in second:
        sys.exit("a repeated update did not print the hooks migration and check report")

    changed = json.loads(settings.read_text(encoding="utf-8"))
    for group in changed["hooks"]["PreToolUse"]:
        for hook in group["hooks"]:
            if "block-dangerous-git.sh" in hook["command"]:
                hook["timeout"] = 5
    settings.write_text(json.dumps(changed, indent=2) + "\n", encoding="utf-8")
    conflicted = settings.read_bytes()
    output = capture(HARNESS + ["update", str(pv_project)])
    if (
        f"hooks conflict: {config}: PreToolUse [Bash] block-dangerous-git.sh"
        not in output
    ):
        sys.exit("update did not list the changed managed hook entry as a conflict")
    if settings.read_bytes() != conflicted:
        sys.exit("update overwrote a managed hook entry changed by the user")
    run_ok(
        HARNESS + ["update", str(pv_project), "--force-seed-file", config], quiet=True
    )

    second_config = ".codex/hooks.json"
    second = pv_project / second_config
    second_document = json.loads(second.read_text(encoding="utf-8"))
    for group in second_document["hooks"]["PreToolUse"]:
        group["hooks"] = [
            hook
            for hook in group["hooks"]
            if "block-pr-merge.sh" not in hook["command"]
        ]
    second.write_text(json.dumps(second_document, indent=2) + "\n", encoding="utf-8")
    output = capture(HARNESS + ["update", str(pv_project)])
    restored = second.read_text(encoding="utf-8")
    if restored.count("block-pr-merge.sh") != 1:
        sys.exit(
            "update did not restore the removed managed entry of the second runtime"
        )
    if f"hooks merge: {second_config}: added=1 replaced=0" not in output:
        sys.exit("update did not report the second runtime hook merge")
    inventory = json.loads(
        (pv_project / ".harness/integrations.json").read_text(encoding="utf-8")
    )
    if "engineering-suite-codex-hooks" not in {
        entry["id"] for entry in inventory["integrations"]
    }:
        sys.exit("the second runtime hook adapter is not recorded in the integrations")


def check_tracker_field(pv_project) -> None:
    """Поле tracker в установленном проекте (docs/adr/0011): discovery обоих runtime и health.

    Проект без origin получает при установке project.json без поля tracker. С добавленным полем
    discovery-ссылки (`.agents/skills` для Codex и `.claude/skills`), `AGENTS.md`, реестр навыков и
    `files.project_json` остаются ok, а `tracker.project` берёт трекер из поля; неизвестный ключ
    внутри tracker роняет health. Исходные байты project.json восстанавливаются: по нему дальше
    работают сценарии hooks.
    """
    project_json = pv_project / ".harness" / "project.json"
    original = project_json.read_bytes()
    data = json.loads(original)
    if "tracker" in data:
        sys.exit("install wrote a tracker field into a project without origin")
    if not (pv_project / ".harness" / "health" / "project_tracker.py").is_file():
        sys.exit(
            "engineering-suite health resource is missing the project tracker resolver"
        )
    if not (pv_project / ".agents" / "skills" / "qa-gate" / "SKILL.md").is_file():
        sys.exit("Codex discovery path .agents/skills does not expose installed skills")
    data["tracker"] = {
        "type": "gitlab",
        "host": "git.example.test:4443",
        "project": "group/sub/project",
    }
    project_json.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    report = capture_json(HARNESS + ["health", str(pv_project), "--json"])
    for check_id in (
        "files.project_json",
        "files.discovery_links",
        "files.agents_md",
        "files.skill_registry",
    ):
        if find_check(report, check_id)["status"] != "ok":
            sys.exit(f"health with a tracker field did not keep {check_id} ok")
    tracker = find_check(report, "tracker.project")
    if tracker["status"] != "ok" or tracker["message"] != (
        "трекер проекта: gitlab, хост git.example.test:4443, проект group/sub/project "
        "(источник: поле tracker)"
    ):
        sys.exit("health did not resolve the project tracker from the tracker field")
    data["tracker"]["unexpected"] = True
    project_json.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    invalid = find_check(
        fail_json(HARNESS + ["health", str(pv_project), "--json"]), "files.project_json"
    )
    if (
        invalid["status"] != "fail"
        or "tracker has unknown field(s): unexpected" not in invalid["message"]
    ):
        sys.exit("health accepted an unknown key inside the tracker field")
    project_json.write_bytes(original)
    run_health(pv_project)


def check_tracker_from_origin(test_root) -> None:
    """Поле tracker из GitLab- и GitHub-origin при установке (docs/adr/0011).

    Install без терминала и флагов трекера выводит тип, хост с портом и проект с подгруппами из
    origin; userinfo в project.json не попадает, `files.project_json` ok, а `tracker.project` берёт
    трекер из записанного поля.
    """
    remotes = {
        "gitlab": (
            "https://ci-user@gitlab.example.test:4443/group/sub/project.git",
            {
                "type": "gitlab",
                "host": "gitlab.example.test:4443",
                "project": "group/sub/project",
            },
        ),
        "github": (
            "git@github.com:acme/widgets.git",
            {"type": "github", "host": "github.com", "project": "acme/widgets"},
        ),
    }
    for name, (remote, expected) in remotes.items():
        project = test_root / f"tracker_{name}_project"
        project.mkdir(parents=True)
        run_step(["git", "init", "-q"], cwd=project, check=True)
        run_step(["git", "remote", "add", "origin", remote], cwd=project, check=True)
        run_ok(
            HARNESS
            + [
                "init",
                str(project),
                "--capability",
                "engineering-suite",
                "--language",
                "ru",
                "--pr-base-branch",
                "main",
                "--branch-pattern",
                "^feature/issue-[0-9]+-.+",
                "--qa-gate-command",
                "echo test",
            ],
            quiet=True,
        )
        text = (project / ".harness" / "project.json").read_text(encoding="utf-8")
        if json.loads(text).get("tracker") != expected or "ci-user" in text:
            sys.exit(f"install did not write the {name} tracker derived from origin")
        fill_agents(project)
        report = capture_json(HARNESS + ["health", str(project), "--json"])
        if find_check(report, "files.project_json")["status"] != "ok":
            sys.exit(f"the {name} tracker field written by install failed health")
        tracker = find_check(report, "tracker.project")
        if tracker["status"] != "ok" or not tracker["message"].endswith(
            "(источник: поле tracker)"
        ):
            sys.exit(f"health did not resolve the {name} tracker from the field")


def _project_bytes(project) -> dict[str, bytes]:
    """Байты каждого файла проекта вне `.git` по POSIX-пути от корня проекта."""
    return {
        path.relative_to(project).as_posix(): path.read_bytes()
        for path in project.rglob("*")
        if path.is_file() and ".git" not in path.relative_to(project).parts
    }


def check_package_root_without_init(test_root) -> None:
    """Установка без `.harness/__init__.py` (#626).

    После `harness install` файла нет ни на диске, ни в lock, и `python -m unittest` без
    аргументов из корня проекта находит и проходит тест проекта. `harness update` поверх прежней
    установки, где файл был управляемым, удаляет только его и меняет только lock.
    """
    project = test_root / "unittest_project"
    project.mkdir(parents=True)
    run_step(["git", "init", "-q"], cwd=project, check=True)
    run_ok(
        HARNESS
        + [
            "init",
            str(project),
            "--capability",
            "engineering-suite",
            "--language",
            "ru",
            "--pr-base-branch",
            "main",
            "--branch-pattern",
            "^feature/issue-[0-9]+-.+",
            "--qa-gate-command",
            "echo test",
        ],
        quiet=True,
    )
    package_init = project / ".harness" / "__init__.py"
    lock_path = project / ".harness" / "harness.lock"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    if package_init.exists() or ".harness/__init__.py" in lock["files"]:
        sys.exit("install still delivers .harness/__init__.py")
    (project / "test_project.py").write_text(
        "import unittest\n\n\nclass ProjectTest(unittest.TestCase):\n"
        "    def test_project(self):\n        self.assertTrue(True)\n",
        encoding="utf-8",
    )
    discovery = run_step(
        [sys.executable, "-m", "unittest"],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
    )
    if discovery.returncode != 0 or "Ran 1 test" not in discovery.stderr:
        sys.exit(
            "python -m unittest did not discover the project test after install:\n"
            + discovery.stderr[-2000:]
        )
    # A previous installation delivered .harness/__init__.py as a managed file.
    package_init.write_bytes((ROOT / "harness" / "__init__.py").read_bytes())
    lock["files"][".harness/__init__.py"] = hashlib.sha256(
        package_init.read_bytes()
    ).hexdigest()
    lock_path.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    before = _project_bytes(project)
    run_ok(HARNESS + ["update", str(project)], quiet=True)
    after = _project_bytes(project)
    removed = sorted(set(before) - set(after))
    added = sorted(set(after) - set(before))
    changed = sorted(
        path for path in set(before) & set(after) if before[path] != after[path]
    )
    if (
        removed != [".harness/__init__.py"]
        or added
        or changed != [".harness/harness.lock"]
    ):
        sys.exit(
            "update did not retire only .harness/__init__.py: "
            f"removed {removed}, added {added}, changed {changed}"
        )


def check_runtime_rules(test_root) -> None:
    """Runtime rules (ADR 0039): свежая установка, старый путь правил, правки проекта, указатель
    Codex в существующем AGENTS.md и закреплённый batch."""
    project = test_root / "rules_project"
    project.mkdir(parents=True)
    run_step(["git", "init", "-q"], cwd=project, check=True)
    run_ok(
        HARNESS + ["init", str(project), "--capability", "engineering-suite"],
        quiet=True,
    )
    rules_source = ROOT / "harness" / "project" / "rules"
    expected = sorted(path.name for path in rules_source.glob("*.md"))
    installed = sorted(path.name for path in (project / ".claude/rules").iterdir())
    if installed != expected or len(installed) != 4:
        sys.exit(f"fresh install did not seed the runtime rules: {installed}")
    agents = project / "AGENTS.md"
    if RULES_POINTER not in agents.read_text(encoding="utf-8"):
        sys.exit("fresh AGENTS.md has no Codex read pointer to .claude/rules/")
    if any(
        ".claude/rules" in item["diff"]
        for item in capture_json(HARNESS + ["diff", str(project), "--json"])[
            "seed_link_proposals"
        ]
    ):
        sys.exit("diff proposed a rules pointer for a fresh AGENTS.md")

    # A pinned batch snapshot under the coordinator state is never touched by update.
    pinned = project / STATE_REL / "batches/batch-pinned/snapshot/docs/agents/git-workflow.md"
    pinned.parent.mkdir(parents=True)
    pinned_bytes = b"### 1. Fundamental Constraints & Tooling\n* **Zero Direct Commits:** pinned\n"
    pinned.write_bytes(pinned_bytes)

    # An older release: the old section 1 in the guide, no rule files yet.
    lock_path = project / ".harness" / "harness.lock"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    guide = project / "docs/agents/git-workflow.md"
    old_guide = (
        b"# Git workflow\n\n### 1. Fundamental Constraints & Tooling\n"
        b"* **Zero Direct Commits:** old release text\n"
    )
    guide.write_bytes(old_guide)
    lock["seed_files"]["docs/agents/git-workflow.md"] = hashlib.sha256(old_guide).hexdigest()
    for name in ("git-delivery.md", "worktree-conventions.md"):
        (project / ".claude/rules" / name).unlink()
        lock["seed_files"].pop(f".claude/rules/{name}")
    lock_path.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    output = capture(HARNESS + ["update", str(project)])
    if guide.read_bytes() != (ROOT / "harness/project/instructions/git-workflow.md").read_bytes():
        sys.exit("update did not replace the unedited old git-workflow.md")
    if "docs/agents/git-workflow.md (устарел по версии)" not in output:
        sys.exit("update did not report the backed-up old git-workflow.md")
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    for name in ("git-delivery.md", "worktree-conventions.md"):
        rule = project / ".claude/rules" / name
        if rule.read_bytes() != (rules_source / name).read_bytes():
            sys.exit(f"update did not install the new rule {name}")
        if lock["seed_files"].get(f".claude/rules/{name}") != hashlib.sha256(
            rule.read_bytes()
        ).hexdigest():
            sys.exit(f"update recorded no baseline for the new rule {name}")

    # Project-edited guide and rule stay byte for byte; the warning names the move.
    edited = {
        "docs/agents/git-workflow.md": guide.read_bytes() + b"\n* **Local rule:** keep.\n",
        ".claude/rules/karpathy-guidelines.md": b"# Local karpathy edit\n",
    }
    for relative, data in edited.items():
        (project / relative).write_bytes(data)
    output = capture(HARNESS + ["update", str(project)])
    for relative, data in edited.items():
        if (project / relative).read_bytes() != data:
            sys.exit(f"update overwrote the project-edited {relative}")
    if "Источник правил переехал" not in output or ".claude/rules/git-delivery.md" not in output:
        sys.exit("update did not say that the rule source of the edited guide moved")

    # An existing AGENTS.md without the pointer: same patch from update and diff, file intact.
    existing = agents.read_text(encoding="utf-8").replace(RULES_POINTER, "")
    agents.write_text(existing, encoding="utf-8")
    update_output = capture(HARNESS + ["update", str(project)])
    diff_output = capture(HARNESS + ["diff", str(project)])
    if agents.read_text(encoding="utf-8") != existing:
        sys.exit("update changed an existing AGENTS.md")
    if "diff --git a/AGENTS.md" not in update_output:
        sys.exit("update did not propose the Codex rules pointer")
    patch = update_output[update_output.index("diff --git ") :]
    if patch != diff_output[diff_output.index("diff --git ") :]:
        sys.exit("diff and update proposed different rules pointers")
    apply_patch(patch, project)
    if RULES_POINTER not in agents.read_text(encoding="utf-8"):
        sys.exit("approved patch did not add the rules pointer")
    if capture_json(HARNESS + ["diff", str(project), "--json"])["seed_link_proposals"]:
        sys.exit("approved rules pointer was proposed again")

    if pinned.read_bytes() != pinned_bytes:
        sys.exit("update changed a pinned batch snapshot")


WORKFLOW_SKILLS = ("implement", "fast-implement", "to-guide", "to-pull-requests")
INSTALLED_TARGET = re.compile(
    r"`((?:docs/agents|\.harness)/[A-Za-z0-9_./-]+\.(?:md|py|json|sh))`"
)
ISSUE_WORKTREE = ".harness/skills/implement/references/issue-worktree.md"
PROCEDURE_GUIDES = ("docs/agents/worktrees.md", "docs/agents/test-author.md")


def check_workflow_procedures(test_root) -> None:
    """Маршруты процедур (ADR 0037, #1162): цели указателей после свежей установки для Claude Code
    и Codex, замена старых руководств при update и предупреждение о переезде у правленой копии."""
    project = test_root / "procedures_project"
    project.mkdir(parents=True)
    run_step(["git", "init", "-q"], cwd=project, check=True)
    run_ok(
        HARNESS + ["init", str(project), "--capability", "backend-orchestration"],
        quiet=True,
    )
    sources = [project / relative for relative in PROCEDURE_GUIDES]
    for name in WORKFLOW_SKILLS:
        skill = project / ".harness" / "skills" / name
        sources += [skill / "SKILL.md", *sorted((skill / "references").glob("*.md"))]
    for source in sources:
        for target in INSTALLED_TARGET.findall(source.read_text(encoding="utf-8")):
            if "<" not in target and not (project / target).is_file():
                sys.exit(f"{source.relative_to(project)} names a missing {target}")
    for guide, target in (
        ("docs/agents/worktrees.md", ISSUE_WORKTREE),
        ("docs/agents/test-author.md", ".harness/skills/fast-implement/SKILL.md"),
        (
            "docs/agents/test-author.md",
            ".harness/orchestration/roles/references/developer-test-author.md",
        ),
    ):
        if target not in (project / guide).read_text(encoding="utf-8"):
            sys.exit(f"{guide} does not point to {target}")

    # Claude Code: the runtime rule names the procedure and the native skill route resolves it.
    rule = (project / ".claude/rules/worktree-conventions.md").read_text(encoding="utf-8")
    if ISSUE_WORKTREE not in rule:
        sys.exit("worktree-conventions.md does not name the coordinator procedure")
    claude_route = project / ".claude/skills/implement/references/issue-worktree.md"
    if not claude_route.is_file():
        sys.exit("Claude Code skill route does not reach issue-worktree.md")
    # Codex: AGENTS.md points at the rules, and the Codex skill route reaches the procedures.
    if RULES_POINTER not in (project / "AGENTS.md").read_text(encoding="utf-8"):
        sys.exit("AGENTS.md has no Codex read pointer to .claude/rules/")
    for relative in (
        ".agents/skills/implement/references/issue-worktree.md",
        ".agents/skills/fast-implement/SKILL.md",
    ):
        if not (project / relative).is_file():
            sys.exit(f"Codex skill route does not reach {relative}")

    # An older release: full procedure sections in the unedited guides are replaced with a backup.
    lock_path = project / ".harness" / "harness.lock"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    old_guides = {
        "docs/agents/worktrees.md": (
            b"# Parallel work: git worktrees\n\n## Coordinator issue worktree\n\n"
            b"python .harness/orchestration/coordinator.py worktree create --repo .\n"
        ),
        "docs/agents/test-author.md": (
            b"# Test-author\n\n## 6. The short `/fast-implement` route\n\nold text\n\n"
            b"## 7. The full `/implement` route\n\nold text\n"
        ),
    }
    for relative, data in old_guides.items():
        (project / relative).write_bytes(data)
        lock["seed_files"][relative] = hashlib.sha256(data).hexdigest()
    lock_path.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    output = capture(HARNESS + ["update", str(project)])
    instructions = ROOT / "harness" / "project" / "instructions"
    for relative in old_guides:
        name = relative.rsplit("/", 1)[1]
        if (project / relative).read_bytes() != (instructions / name).read_bytes():
            sys.exit(f"update did not replace the unedited old {relative}")
        if f"{relative} (устарел по версии)" not in output:
            sys.exit(f"update did not report the backed-up old {relative}")

    # Project-edited guides stay byte for byte, and the warning names each new procedure source.
    edited = {
        relative: (project / relative).read_bytes() + b"\nLocal note.\n"
        for relative in PROCEDURE_GUIDES
    }
    for relative, data in edited.items():
        (project / relative).write_bytes(data)
    output = capture(HARNESS + ["update", str(project)])
    for relative, data in edited.items():
        if (project / relative).read_bytes() != data:
            sys.exit(f"update overwrote the project-edited {relative}")
    for target in (
        ISSUE_WORKTREE,
        ".harness/skills/fast-implement/SKILL.md",
        ".harness/orchestration/roles/references/developer-test-author.md",
    ):
        if f"→ {target}" not in output:
            sys.exit(f"update did not name the moved procedure source {target}")
    if "Источник процедуры переехал" not in output:
        sys.exit("update did not say that a procedure source moved")
    if (project / "docs" / "adr").exists():
        sys.exit("install or update copied the repository docs/ into the target")
