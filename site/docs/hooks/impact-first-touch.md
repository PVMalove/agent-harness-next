# impact-first-touch.sh: первое касание рискованного пути

## 1. Название и локализация

- **Исходный хук:** [`harness/project/hooks/impact-first-touch.sh`](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/hooks/impact-first-touch.sh)
  и общее тело [`change_impact_hooks.py`](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/hooks/change_impact_hooks.py)
- **Русский перевод:** предупреждение о первом касании рискованного пути в операции.

## 2. Полное описание

Advisory-hook `PreToolUse(Write|Edit)` из матрицы ADR 0024, раздел 2a. Hook читает
`tool_input.file_path` и предупреждает, когда агент в операции впервые правит путь, влияние которого
ChangeImpact не вычисляет по графу импортов. Это конфиг сборки и проверок (`pyproject.toml`,
`uv.lock`, `Makefile`, `conftest.py`, `.github/*`, `scripts/verify.py`, `scripts/verification/*`) или
каталог capabilities и skills (`harness/CAPABILITIES.json`, `skills/*`). Набор совпадает с правилами
`build-config-changed` и `capabilities-or-skills-changed` функции `path_unknown_code` в
`harness/repo_map/change_impact.py`. Правило `non-python-file` в набор не входит, иначе рискованной
стала бы каждая правка документа. Hook не видит пакет harness и держит копию правил, а
`tests/core/test_change_impact_hooks.py` сверяет копию с источником.

Hook сравнивает путь после `realpath` относительно ближайшего вверх каталога с `.git` (каталога или
файла worktree), в posix-форме. На Windows сравнение не учитывает регистр. Путь вне git-checkout hook
пропускает без предупреждения.

Предупреждение получает модель: stdout содержит
`{"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": "<текст>"}}` без
`permissionDecision`, поэтому поток разрешений не меняется. Hook никогда не блокирует.

- **Профили.** В `minimal` hook не работает: конверт отвечает `allow`, тело не запускается и
  состояние не пишется. В `standard` и `strict` hook даёт `warn` с кодом `risky-path-first-touch`.
- **Дедупликация.** Hook предупреждает один раз на путь в операции: это и есть первое касание, и
  повторная правка того же пути новых предупреждений не даёт. Операция означает прогон агента:
  `operation_id` равен первым 32 hex от sha256 массива `["hook-operation", session_id, agent_id или ""]`.
  Роль-субагент, внешний worker и coordinator получают разные операции. Новый dispatch,
  developer-retry и повтор роли получают новую операцию и новое предупреждение. Маркер `n-<key>.json`
  hook создаёт через `O_EXCL`, поэтому из параллельных вызовов предупреждает ровно один. Маркер
  служит и evidence-записью: его путь стоит в `evidence_ref` вердикта. Хранилище и его границы описаны
  в [targeted-check-reminder.md](targeted-check-reminder.md).
- **Внутренняя ошибка.** Нечитаемый JSON, нет `session_id` или `tool_input.file_path`, сбой
  хранилища, любое исключение, ненулевой код и тайм-аут 10 с (`ADVISORY_TIMEOUT_SECONDS`) дают `warn`
  `internal-error` с кодом `0` и пустым stdout ([hook-response.md](hook-response.md)).
- **Второй runtime.** Там правка файла приходит как `apply_patch` без `file_path`, поэтому hook не
  подключён, пока нет адаптера payload. `harness health` перечисляет его в строке `нет события или
  payload` с проверкой вне hook: ChangeImpact-gate по ADR 0023.

## 3. Контракт

- **Вход:** JSON события `PreToolUse` в stdin: `session_id`, `agent_id` (у субагента),
  `hook_event_name`, `tool_name`, `tool_input.file_path`, `cwd`. Профиль hook берёт только из
  `hook_policy` в `.harness/project.json`.
- **Выход:** всегда код `0`. При первом касании рискованного пути hook пишет `additionalContext` в
  stdout, первой строкой stderr `[risky-path-first-touch] <текст>` и строку `evidence_ref=<путь>`;
  последняя строка stderr содержит вердикт конверта. Остальные вызовы получают `allow` без stdout.
- **Состояние:** `.harness/.sandboxes/hook-events/<operation_id>/n-<key>.json`. Hook не запускает
  тесты, `make` и `git`.

## Источник

[impact-first-touch.sh](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/hooks/impact-first-touch.sh),
[change_impact_hooks.py](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/hooks/change_impact_hooks.py),
[change_impact.py](https://github.com/PVMalove/agent-harness-next/blob/master/harness/repo_map/change_impact.py)
