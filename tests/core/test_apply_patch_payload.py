"""Адаптер payload `apply_patch` второго runtime: грамматика патча, shell-форма и применение Update.

Таблицы повторяют формы, которые принимает и отвергает parse_patch runtime в режиме Lenient.
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path
from collections.abc import Sequence
from types import ModuleType
from typing import TYPE_CHECKING

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "harness" / "project" / "hooks" / "apply_patch_payload.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("apply_patch_payload_test", MODULE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


if TYPE_CHECKING:
    from harness.project.hooks import apply_patch_payload as ap
else:
    ap = _load()

ADD = "*** Begin Patch\n*** Add File: notes/a.md\n+hello\n+world\n*** End Patch"


def _paths(ops: Sequence[ap.FileOp]) -> list[tuple[str, str, str | None]]:
    return [(op.kind, op.path, op.move_to) for op in ops]


def test_a_quoted_heredoc_wrapper_parses_into_an_add_file() -> None:
    ops = ap.parse_patch("<<'EOF'\n" + ADD + "\nEOF\n")

    assert _paths(ops) == [("add", "notes/a.md", None)]
    assert ops[0].content == "hello\nworld\n"


@pytest.mark.parametrize("opening", ["<<EOF", "<<'EOF'", '<<"EOF"'])
def test_every_heredoc_opening_the_runtime_accepts_parses(opening: str) -> None:
    assert _paths(ap.parse_patch(f"{opening}\n{ADD}\nEOF")) == [
        ("add", "notes/a.md", None)
    ]


def test_whitespace_around_markers_and_crlf_are_accepted() -> None:
    text = "\n  *** Begin Patch  \r\n *** Add File: a.txt\r\n+x\r\n  *** End Patch \n\n"

    ops = ap.parse_patch(text)

    assert _paths(ops) == [("add", "a.txt", None)]
    assert ops[0].content == "x\n"


def test_environment_id_end_of_file_move_and_spaces_in_paths() -> None:
    text = (
        "*** Begin Patch\n"
        "*** Environment ID: env-1\n"
        "*** Update File: src/old name.py\n"
        "*** Move to: src/new name.py\n"
        "@@ def f():\n"
        "-    return 1\n"
        "+    return 2\n"
        "*** End of File\n"
        "*** Delete File: gone.txt\n"
        "*** End Patch"
    )

    ops = ap.parse_patch(text)

    assert _paths(ops) == [
        ("update", "src/old name.py", "src/new name.py"),
        ("delete", "gone.txt", None),
    ]
    chunk = ops[0].chunks[0]
    assert chunk.change_context == "def f():"
    assert (chunk.old_lines, chunk.new_lines) == (
        ("    return 1",),
        ("    return 2",),
    )
    assert chunk.end_of_file is True


def test_zero_hunks_is_an_empty_patch() -> None:
    assert ap.parse_patch("*** Begin Patch\n*** End Patch") == ()


def test_an_indented_header_inside_an_update_is_a_context_line() -> None:
    text = (
        "*** Begin Patch\n*** Update File: a.py\n@@\n x\n *** Add File: b.py\n+y\n"
        "*** End Patch"
    )

    ops = ap.parse_patch(text)

    assert _paths(ops) == [("update", "a.py", None)]
    assert ops[0].chunks[0].old_lines == ("x", "*** Add File: b.py")
    assert ops[0].chunks[0].context_indices == ((0, 0), (1, 1))


@pytest.mark.parametrize(
    "text",
    [
        "",
        "*** Add File: a\n+x\n*** End Patch",
        "*** Begin Patch\n*** Add File: a\n+x",
        "*** Begin Patch\n*** End Patch\nrm -rf /\n*** End Patch",
        "*** Begin Patch\n*** Update File: a.py\n*** End Patch",
        "*** Begin Patch\n*** Update File: a.py\n@@\n*** End Patch",
        "*** Begin Patch\n*** Environment ID: a\n*** Environment ID: b\n*** End Patch",
        "*** Begin Patch\n*** Environment ID:   \n*** End Patch",
        "*** Begin Patch\n*** Add File: \n+x\n*** End Patch",
        "*** Begin Patch\nhello\n*** End Patch",
        "*** Begin Patch\n*** Add File: a\nplain\n*** End Patch",
        "*** Begin Patch\n*** Update File: a\n x\n*** End of File\n y\n*** End Patch",
        "*** Begin Patch\n*** Add File: a\x00b\n+x\n*** End Patch",
        "<<EOF\n*** Begin Patch\nEOF",
    ],
)
def test_input_the_runtime_rejects_is_a_patch_error(text: str) -> None:
    with pytest.raises(ap.PatchError):
        ap.parse_patch(text)


@pytest.mark.parametrize(
    ("script", "cd_dir"),
    [
        ("apply_patch <<'EOF'\n" + ADD + "\nEOF", None),
        ("applypatch <<EOF\n" + ADD + "\nEOF\n", None),
        ("cd sub && apply_patch <<'PATCH'\n" + ADD + "\nPATCH", "sub"),
        ("cd 'a b' && apply_patch <<\"EOF\"\n" + ADD + "\nEOF", "a b"),
        ('cd "a b" && apply_patch <<EOF\n' + ADD + "\nEOF", "a b"),
    ],
)
def test_the_two_shell_forms_yield_the_heredoc_body(
    script: str, cd_dir: str | None
) -> None:
    assert ap.parse_shell(script) == (ADD, cd_dir)


@pytest.mark.parametrize(
    "script",
    [
        "cd sub; apply_patch <<'EOF'\n" + ADD + "\nEOF",
        "cd sub || apply_patch <<'EOF'\n" + ADD + "\nEOF",
        "cd a && cd b && apply_patch <<'EOF'\n" + ADD + "\nEOF",
        "apply_patch foo <<'EOF'\n" + ADD + "\nEOF",
        "apply_patch <<'EOF'\n" + ADD + "\nEOF\necho done",
        "echo hi",
    ],
)
def test_other_shell_forms_are_not_apply_patch(script: str) -> None:
    assert ap.parse_shell(script) is None


def _chunks(body: str) -> tuple[ap.Chunk, ...]:
    return ap.parse_patch(
        f"*** Begin Patch\n*** Update File: f\n{body}\n*** End Patch"
    )[0].chunks


def test_apply_update_replaces_exact_trimmed_and_normalised_lines() -> None:
    source = 'a\n  "key": 1,\nb \u201cq\u201d\nc\n'

    assert ap.apply_update(source, _chunks('@@\n-  "key": 1,\n+  "key": 2,')) == (
        'a\n  "key": 2,\nb \u201cq\u201d\nc\n'
    )
    assert ap.apply_update(source, _chunks('@@\n-"key": 1,\n+"key": 3,')) == (
        'a\n"key": 3,\nb \u201cq\u201d\nc\n'
    )
    assert ap.apply_update(source, _chunks('@@\n-b "q"\n+b plain')) == (
        'a\n  "key": 1,\nb plain\nc\n'
    )


def test_apply_update_honours_change_context_and_returns_none_when_lines_are_missing() -> (
    None
):
    source = "x\nx\nfirst\nx\n"

    assert ap.apply_update(source, _chunks("@@ first\n-x\n+y")) == "x\nx\nfirst\ny\n"
    assert ap.apply_update(source, _chunks("@@\n-absent\n+y")) is None
    assert ap.apply_update(source, _chunks("@@ absent\n-x\n+y")) is None


def test_operations_resolve_paths_against_the_payload_cwd(tmp_path: Path) -> None:
    patch = (
        "*** Begin Patch\n*** Add File: rel.txt\n+x\n"
        f"*** Update File: {tmp_path}/abs.txt\n*** Move to: moved.txt\n@@\n-a\n+b\n"
        "*** End Patch"
    )
    payload = {
        "tool_name": "apply_patch",
        "cwd": str(tmp_path / "sub"),
        "tool_input": {"command": patch},
    }

    assert _paths(ap.operations(payload)) == [
        ("add", str(tmp_path / "sub" / "rel.txt"), None),
        ("update", str(tmp_path / "abs.txt"), str(tmp_path / "sub" / "moved.txt")),
    ]


def test_bash_operations_join_the_cd_directory(tmp_path: Path) -> None:
    payload = {
        "tool_name": "Bash",
        "cwd": str(tmp_path),
        "tool_input": {"command": "cd .codex && apply_patch <<'EOF'\n" + ADD + "\nEOF"},
    }

    ops = ap.bash_operations(payload)
    assert ops is not None
    assert _paths(ops) == [
        ("add", str(tmp_path / ".codex" / "notes" / "a.md"), None)
    ]
    assert ap.bash_operations({"tool_input": {"command": "ls"}, "cwd": "/"}) is None


def test_mentions_patch_and_header_paths_scan_free_text() -> None:
    command = (
        "echo x; apply_patch <<'EOF'\n*** Begin Patch\n *** Update File: a b\n"
        "*** Move to: c\n*** Delete File: d\n*** End Patch\nEOF"
    )

    assert ap.mentions_patch(command) is True
    assert ap.mentions_patch("echo '*** Begin Patch'") is False
    assert ap.header_paths(command) == ("a b", "c", "d")


def test_fanout_feeds_one_write_payload_per_path_and_stops_at_the_first_block(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    seen = tmp_path / "seen.jsonl"
    child = (
        "import json,sys\n"
        "p=json.load(sys.stdin)\n"
        f"open({str(seen)!r},'a').write(json.dumps(p)+'\\n')\n"
        "path=p['tool_input']['file_path']\n"
        "sys.stderr.write('blocked '+path) if path.endswith('bad.txt') else None\n"
        "sys.exit(2 if path.endswith('bad.txt') else 0)\n"
    )
    patch = (
        "*** Begin Patch\n*** Add File: ok.txt\n+x\n*** Delete File: bad.txt\n"
        "*** Add File: never.txt\n+y\n*** End Patch"
    )
    payload = {
        "tool_name": "apply_patch",
        "session_id": "s1",
        "cwd": str(tmp_path),
        "tool_input": {"command": patch},
    }
    monkeypatch.setattr(
        sys, "stdin", io.TextIOWrapper(io.BytesIO(json.dumps(payload).encode()))
    )

    code = ap.main(["fanout", "--", sys.executable, "-c", child])

    assert code == 2
    assert capfd.readouterr().err.endswith("blocked " + str(tmp_path / "bad.txt"))
    calls = [json.loads(line) for line in seen.read_text().splitlines()]
    assert [call["tool_input"]["file_path"] for call in calls] == [
        str(tmp_path / "ok.txt"),
        str(tmp_path / "bad.txt"),
    ]
    assert all(
        call["tool_name"] == "Write" and call["session_id"] == "s1" for call in calls
    )
