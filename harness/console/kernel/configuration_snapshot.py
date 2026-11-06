"""The «Настройка» facts of the one project a console server serves: whether the configuration
schema and the orchestration roles are installed, whether a configuration write left a prepared
transaction, where the version store lies and, per configuration file, whether it exists, the
SHA-256 digest of its raw bytes and its document with every secret masked (the default document
for a missing file), with the runtime adapter preview. Collecting reads only: it never creates
the version store, never moves a legacy one and never recovers a transaction.
`ConfigurationFacts.to_payload` and `ConfigurationFacts.from_payload` are the wire codec of a
`configuration.snapshot` reply; reading it back is strict, so a reply off the schema is a
`ValueError`."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from harness.configuration import (
    inside_project,
    mask_secrets,
    parse_object,
    read_config_bundle,
    read_journal,
)
from harness.json_types import JsonObject
from harness.runtime_adapters import AdapterStatus

from .configuration import (
    CONFIG_NAMES,
    RuntimeAdapterPreview,
    default_document,
    preview_runtime_adapters,
)

STORE_DIR = ".harness/config_versions"
_FIELDS = frozenset(
    {
        "schema_installed",
        "orchestration_installed",
        "transaction_pending",
        "store_root",
        "files",
        "adapters",
    }
)
_FILE_FIELDS = frozenset({"exists", "digest", "document", "error"})
_ADAPTER_FIELDS = frozenset({"preview", "error"})
_PREVIEW_FIELDS = frozenset(
    {"adapters", "capabilities", "fingerprint", "text", "blocked", "reason"}
)
_STATUS_FIELDS = frozenset({"path", "status", "problem"})


def config_digest(raw: bytes | None) -> str:
    """The SHA-256 hex digest of a configuration file's raw bytes; empty for a missing file."""
    return "" if raw is None else hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class ConfigFile:
    """One configuration file: `document` is masked, or the default for a missing file, and is
    empty with the reason in `error` when the file cannot be read as a JSON object."""

    exists: bool
    digest: str
    document: JsonObject
    error: str


@dataclass(frozen=True)
class AdapterFacts:
    """The runtime adapter preview, or None with the reason in `error`."""

    preview: RuntimeAdapterPreview | None
    error: str


@dataclass(frozen=True)
class ConfigurationFacts:
    schema_installed: bool
    orchestration_installed: bool
    transaction_pending: bool
    store_root: str
    files: dict[str, ConfigFile]
    adapters: AdapterFacts

    def to_payload(self) -> dict[str, object]:
        """The JSON object of a `configuration.snapshot` reply."""
        preview = self.adapters.preview
        return {
            "schema_installed": self.schema_installed,
            "orchestration_installed": self.orchestration_installed,
            "transaction_pending": self.transaction_pending,
            "store_root": self.store_root,
            "files": {
                name: {
                    "exists": item.exists,
                    "digest": item.digest,
                    "document": item.document,
                    "error": item.error,
                }
                for name, item in self.files.items()
            },
            "adapters": {
                "preview": None
                if preview is None
                else {
                    "adapters": [dict(item) for item in preview.adapters],
                    "capabilities": list(preview.capabilities),
                    "fingerprint": preview.fingerprint,
                    "text": preview.text,
                    "blocked": preview.blocked,
                    "reason": preview.reason,
                },
                "error": self.adapters.error,
            },
        }

    @classmethod
    def from_payload(cls, payload: object) -> ConfigurationFacts:
        """The facts of a `configuration.snapshot` reply; anything off the schema is a
        `ValueError`."""
        found = _object(payload, _FIELDS)
        flags = [
            found[name]
            for name in ("schema_installed", "orchestration_installed", "transaction_pending")
        ]
        if not all(isinstance(flag, bool) for flag in flags):
            raise ValueError("configuration snapshot flags")
        files = _object(found["files"])
        if set(files) != set(CONFIG_NAMES):
            raise ValueError("configuration snapshot files")
        return cls(
            cast(bool, flags[0]),
            cast(bool, flags[1]),
            cast(bool, flags[2]),
            _str(found["store_root"]),
            {name: _file(files[name]) for name in CONFIG_NAMES},
            _adapters(found["adapters"]),
        )


def _object(value: object, fields: frozenset[str] | None = None) -> dict[str, object]:
    if not isinstance(value, dict) or (fields is not None and set(value) != fields):
        raise ValueError("configuration snapshot off the schema")
    return cast(dict[str, object], value)


def _str(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("configuration snapshot string")
    return value


def _file(value: object) -> ConfigFile:
    found = _object(value, _FILE_FIELDS)
    if not isinstance(found["exists"], bool):
        raise ValueError("configuration snapshot file")
    return ConfigFile(
        found["exists"],
        _str(found["digest"]),
        cast(JsonObject, _object(found["document"])),
        _str(found["error"]),
    )


def _status(value: object) -> AdapterStatus:
    found = _object(value, _STATUS_FIELDS)
    problem = found["problem"]
    if problem is not None and not isinstance(problem, str):
        raise ValueError("configuration snapshot adapter")
    return AdapterStatus(
        path=_str(found["path"]), status=_str(found["status"]), problem=problem
    )


def _adapters(value: object) -> AdapterFacts:
    found = _object(value, _ADAPTER_FIELDS)
    error = _str(found["error"])
    if found["preview"] is None:
        return AdapterFacts(None, error)
    preview = _object(found["preview"], _PREVIEW_FIELDS)
    adapters, capabilities = preview["adapters"], preview["capabilities"]
    if not isinstance(adapters, list) or not isinstance(capabilities, list):
        raise ValueError("configuration snapshot preview")
    if not isinstance(preview["blocked"], bool):
        raise ValueError("configuration snapshot preview")
    return AdapterFacts(
        RuntimeAdapterPreview(
            [_status(item) for item in adapters],
            [_str(item) for item in capabilities],
            _str(preview["fingerprint"]),
            _str(preview["text"]),
            preview["blocked"],
            _str(preview["reason"]),
        ),
        error,
    )


def _pending(repo: Path) -> bool:
    """Whether the journal holds a prepared transaction; read only, never recovered. An
    unreadable journal is pending too: the next write must stop on it."""
    try:
        journal = read_journal(inside_project(repo, repo / STORE_DIR / ".transaction.json"))
    except (ValueError, OSError):
        return True
    return journal is not None and journal["state"] == "prepared"


def _read_files(repo: Path) -> dict[str, ConfigFile]:
    try:
        bundle = read_config_bundle(repo)
    except (ValueError, OSError) as exc:
        reason = str(exc) or type(exc).__name__
        return {name: ConfigFile(False, "", {}, reason) for name in CONFIG_NAMES}
    files: dict[str, ConfigFile] = {}
    for name in CONFIG_NAMES:
        raw = bundle[name]
        try:
            document = (
                cast(JsonObject, mask_secrets(parse_object(raw, name)))
                if raw is not None
                else default_document(repo, name)
            )
        except (ValueError, OSError) as exc:
            files[name] = ConfigFile(raw is not None, config_digest(raw), {}, str(exc))
        else:
            files[name] = ConfigFile(raw is not None, config_digest(raw), document, "")
    return files


def _adapter_facts(repo: Path) -> AdapterFacts:
    try:
        return AdapterFacts(preview_runtime_adapters(repo), "")
    except (ValueError, OSError) as exc:
        return AdapterFacts(None, str(exc) or type(exc).__name__)


def collect_configuration(repo: Path) -> ConfigurationFacts:
    """The «Настройка» facts of `repo`; reads files only."""
    repo = repo.expanduser().resolve()
    return ConfigurationFacts(
        schema_installed=(repo / ".harness/project.schema.json").is_file(),
        orchestration_installed=(repo / ".harness/orchestration/roles").is_dir(),
        transaction_pending=_pending(repo),
        store_root=str(repo / STORE_DIR),
        files=_read_files(repo),
        adapters=_adapter_facts(repo),
    )
