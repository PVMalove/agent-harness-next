"""Native integration paths, events and invocation capabilities shared by the packager."""

from dataclasses import dataclass

from harness.json_types import JsonObject

FRONTMATTER_INVOCATION = "disable-model-invocation"
CODEX_INVOCATION = "policy.allow_implicit_invocation"
CODEX_HOOKS = ".codex/hooks.json"


@dataclass(frozen=True)
class NativeAdapter:
    runtime: str
    config: str
    skill_root: str
    invocation_policy: str
    events: dict[str, str]
    flat_hooks: bool = False
    multi_install_safe: bool = True
    guard_config: str | None = None

    def guard_path(self) -> str:
        if self.guard_config is None:
            raise ValueError(f"{self.runtime} has no built-in guard wiring")
        return self.guard_config

    def hook(self, command: str) -> JsonObject:
        if self.flat_hooks:
            return {"command": command}
        return {"hooks": [{"type": "command", "command": command}]}

    def commands(self, entry: object) -> set[str]:
        if not isinstance(entry, dict):
            return set()
        handlers = [entry] if self.flat_hooks else entry.get("hooks", [])
        if not isinstance(handlers, list):
            return set()
        return {
            handler["command"]
            for handler in handlers
            if isinstance(handler, dict) and isinstance(handler.get("command"), str)
        }


CANONICAL_EVENTS = {
    "session_start": "SessionStart",
    "session_end": "SessionEnd",
    "stop": "Stop",
}
NATIVE_ADAPTERS = (
    NativeAdapter(
        "claude",
        ".claude/settings.json",
        ".claude/skills",
        FRONTMATTER_INVOCATION,
        CANONICAL_EVENTS,
        guard_config=".claude/settings.local.json",
    ),
    NativeAdapter(
        "codex",
        CODEX_HOOKS,
        ".agents/skills",
        CODEX_INVOCATION,
        CANONICAL_EVENTS,
        guard_config=CODEX_HOOKS,
    ),
    NativeAdapter(
        "cursor",
        ".cursor/hooks.json",
        ".agents/skills",
        FRONTMATTER_INVOCATION,
        {"session_start": "sessionStart", "session_end": "sessionEnd", "stop": "stop"},
        flat_hooks=True,
    ),
)


NATIVE_ADAPTER_BY_RUNTIME = {adapter.runtime: adapter for adapter in NATIVE_ADAPTERS}
