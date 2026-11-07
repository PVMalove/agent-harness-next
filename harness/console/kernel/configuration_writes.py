"""Configuration writes run as console server jobs through `configuration_cli.py`. A draft travels
as a set of changes against the masked `configuration.snapshot` it was built from, with the
digests of the files it read: the write checks the digests (a changed file is
`StaleConfiguration`), replays the changes onto the current unmasked documents and refuses any
value that still holds the secret mask, so an untouched secret is kept and a mask is never
written. The request is compact JSON, small enough for one `job.start` frame for usual edits."""

from __future__ import annotations

import copy
import json
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import cast

from harness.configuration import (
    SECRET_MASK,
    parse_object,
    read_config_bundle,
)
from harness.configuration_store import ConfigurationStore, StaleConfiguration
from harness.json_types import JsonObject

from .configuration import (
    CONFIG_NAMES,
    ConfigurationDraft,
    _MISSING,
    _changed_paths,
    _lookup,
    apply_runtime_adapters,
    default_document,
    preview_runtime_adapters,
)
from .configuration_snapshot import config_digest

_STALE = "Файл изменён другим процессом; загрузите внешние изменения и заново просмотрите итог"


def _base(draft: ConfigurationDraft, name: str) -> JsonObject:
    raw = draft.original[name]
    return parse_object(raw, name) if raw is not None else default_document(draft.repo, name)


def draft_changes(draft: ConfigurationDraft) -> list[dict[str, object]]:
    """The edits of `draft` against its base, leaf by leaf: a set value or a removed key."""
    changes: list[dict[str, object]] = []
    for name, document in draft.documents.items():
        for path in _changed_paths(_base(draft, name), document):
            value = _lookup(document, path)
            change: dict[str, object] = {"file": name, "path": list(path)}
            if value is _MISSING:
                change["remove"] = True
            else:
                change["value"] = value
            changes.append(change)
    return changes


def _compact(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def draft_request(draft: ConfigurationDraft, description: str = "") -> str:
    """The request of a draft write: its changes, the digests it read and a description."""
    return _compact(
        {
            "changes": draft_changes(draft),
            "expected": dict(draft.digests),
            "description": description,
        }
    )


def _holds_mask(value: object) -> bool:
    if isinstance(value, dict):
        return any(_holds_mask(item) for item in value.values())
    if isinstance(value, list):
        return any(_holds_mask(item) for item in value)
    return value == SECRET_MASK


def _path(value: object) -> tuple[str, ...]:
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(key, str) for key in value)
    ):
        raise ValueError("Неверный путь поля в наборе изменений")
    return tuple(cast(list[str], value))


def replay_changes(
    documents: dict[str, JsonObject], changes: Sequence[object]
) -> dict[str, JsonObject]:
    """A copy of `documents` with `changes` applied; a value holding the secret mask, an unknown
    file or a malformed change is `ValueError`."""
    result = copy.deepcopy(documents)
    draft = ConfigurationDraft(Path(), result, {})
    for change in changes:
        if not isinstance(change, dict) or change.get("file") not in result:
            raise ValueError("Неверное изменение конфигурации")
        name = cast(str, change["file"])
        path = _path(change.get("path"))
        if set(change) == {"file", "path", "remove"} and change["remove"] is True:
            draft.remove_value(name, path)
        elif set(change) == {"file", "path", "value"}:
            if _holds_mask(change["value"]):
                raise ValueError("Скрытое значение нельзя записать: введите его заново")
            draft.set_value(name, path, change["value"])
        else:
            raise ValueError("Неверное изменение конфигурации")
    return result


def _request(text: str) -> dict[str, object]:
    try:
        value = json.loads(text)
    except ValueError:
        raise ValueError("Запрос записи конфигурации — не JSON") from None
    if not isinstance(value, dict):
        raise ValueError("Запрос записи конфигурации — не JSON-объект")
    return cast(dict[str, object], value)


def _expected(request: dict[str, object]) -> dict[str, str]:
    expected = request.get("expected")
    if (
        not isinstance(expected, dict)
        or not expected
        or not all(
            name in CONFIG_NAMES and isinstance(digest, str)
            for name, digest in expected.items()
        )
    ):
        raise ValueError("Запрос записи конфигурации без digest файлов")
    return cast(dict[str, str], expected)


def _fresh(repo: Path, expected: dict[str, str]) -> dict[str, bytes | None]:
    """The current files once every expected digest still matches; `StaleConfiguration`
    otherwise."""
    bundle = read_config_bundle(repo)
    if any(config_digest(bundle[name]) != digest for name, digest in expected.items()):
        raise StaleConfiguration(_STALE)
    return bundle


def _description(request: dict[str, object]) -> str:
    description = request.get("description", "")
    if not isinstance(description, str):
        raise ValueError("Описание версии должно быть строкой")
    return description


def _replayed(repo: Path, request: dict[str, object]) -> ConfigurationDraft:
    """The draft the request describes, rebuilt on the current unmasked files."""
    repo = repo.expanduser().resolve()
    expected = _expected(request)
    bundle = _fresh(repo, expected)
    current: dict[str, JsonObject] = {}
    for name in expected:
        raw = bundle[name]
        current[name] = (
            parse_object(raw, name) if raw is not None else default_document(repo, name)
        )
    changes = request.get("changes")
    if not isinstance(changes, list):
        raise ValueError("Запрос записи конфигурации без набора изменений")
    draft = ConfigurationDraft(
        repo,
        replay_changes(current, changes),
        {name: bundle[name] for name in expected},
        dict(expected),
    )
    problems = draft.problems()
    if problems:
        raise ValueError("Исправьте ошибки черновика: " + "; ".join(problems))
    return draft


def save_draft(repo: Path, request: str) -> str:
    """Save the draft as a version without applying it."""
    found = _request(request)
    draft = _replayed(repo, found)
    store = ConfigurationStore(draft.repo)
    version = store.save(
        {**read_config_bundle(draft.repo), **draft.encoded()}, _description(found)
    )
    return f"Версия сохранена без применения: {version.id}\nХранилище: {store.root}"


def save_current(repo: Path, request: str) -> str:
    """Save the active configuration as a version."""
    store = ConfigurationStore(repo)
    version = store.save(read_config_bundle(store.repo), _description(_request(request)))
    return f"Текущая конфигурация сохранена как версия: {version.id}\nХранилище: {store.root}"


def apply(repo: Path, request: str) -> str:
    """Apply the draft; the active set is saved as a version first."""
    draft = _replayed(repo, _request(request))
    backup = ConfigurationStore(draft.repo).apply(draft.encoded(), expected=draft.original)
    return "Конфигурация применена. Предыдущая версия: " + backup.id


def apply_adapters(repo: Path, request: str) -> str:
    """Install or update the runtime adapters of the previewed plan with `fingerprint`."""
    fingerprint = _request(request).get("fingerprint")
    preview = preview_runtime_adapters(repo)
    if not isinstance(fingerprint, str) or preview.fingerprint != fingerprint:
        raise ValueError("План изменился: выполните просмотр заново")
    return apply_runtime_adapters(repo, preview, confirmed=True)


def recover(repo: Path, request: str = "") -> str:
    """Roll back an interrupted configuration write."""
    ConfigurationStore(repo).recover()
    return "Незавершённая запись конфигурации проверена"


def restore(repo: Path, request: str) -> str:
    """Restore a saved version once the active files still have the expected digests."""
    found = _request(request)
    version = found.get("version")
    if not isinstance(version, str) or not version:
        raise ValueError("Не указана версия конфигурации")
    store = ConfigurationStore(repo)
    bundle = _fresh(store.repo, _expected(found))
    backup = store.apply(store.load(version), expected=bundle)
    return "Версия восстановлена. Обратный откат: " + backup.id


# The CLI operation name of every write.
OPERATIONS: dict[str, Callable[[Path, str], str]] = {
    "save-draft": save_draft,
    "save-current": save_current,
    "apply": apply,
    "adapters": apply_adapters,
    "recover": recover,
    "restore": restore,
}
