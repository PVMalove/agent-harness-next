# test-author-guard.py: scoped guard субагента test-author

## 1. Название и локализация

- **Исходный скрипт:** [`harness/project/hooks/test-author-guard.py`](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/hooks/test-author-guard.py)
- **Русский перевод:** защитный hook субагента тест-автора.

## 2. Полное описание

`test-author-guard.py` ограничивает субагента test-author тестовой зоной и запуском одного теста.
Это hook события `PreToolUse` для `Write`, `Edit` и `Bash`, но в `settings.local.json` его нет:
установка копирует его в `.claude/hooks/`, а подключает только frontmatter агента
`.claude/agents/test-author.md`. Поэтому guard действует только на вызовы субагента test-author.
Project-wide hooks (`block-scratch-outside-docs-tasks.sh`, `require-bounded-check.sh` и остальные)
остаются в силе и срабатывают так же, как для любого агента.

Guard разрешает ровно три вида вызовов:

- `Write` и `Edit`: путь после нормализации лежит внутри `test_paths`. Symlink, ведущий за пределы
  зоны, и пути под `.git`, `.harness`, `.claude`, `.agents`, `.codex` guard отклоняет;
- `apply_patch` второго runtime: каждый путь патча из заголовков `*** Add File:`,
  `*** Update File:`, `*** Delete File:` и `*** Move to:` (абсолютный от `cwd` payload, разбор
  адаптера `apply_patch_payload.py`) проходит ту же проверку, что путь `Write`/`Edit`. Патч, в
  котором хотя бы один путь вне `test_paths`, получает `write_outside_test_paths`, а неразбираемый
  патч получает `patch_unparseable` с подсказкой о формате патча;
- `Bash`: один вызов `.claude/hooks/run-test.sh <test-id>` (допускается эквивалентный вызов через
  доверенный системный `bash`). Shell-метасимволы, `--probe`, дополнительные аргументы и другие
  команды guard отклоняет.

Остальные инструменты получают отказ `tool_not_allowed`. Если payload пришёл от другого агента
(`agent_type` не `test-author`), guard молча пропускает вызов, и маршрут developer и остальных
агентов не меняется.

**Мягкий отказ.** Hook печатает один JSON `PreToolUse` с `permissionDecision: deny` и причиной
`test-author: <причина>` и завершается кодом 0. Он не пишет файлов, не меняет dispatch и ledger и
не возвращает пользовательский ввод. Перед проверкой вызова guard заново проверяет активацию:
установлен ли agent с включённым hook, наследует ли он model и effort, корректны ли `test_paths`,
`test_runner` и зоны записи. Если эта проверка не прошла, отказ получает её причину или
`guard_unavailable`.

**Внутренний режим.** `test-author-guard.py --validate-config` печатает `{"status":"ok"}` или
`{"status":"disabled","reason":"<причина>"}`. Этот режим вызывает только
[`test-author-preflight.sh`](test-author-preflight.md).

## 3. Контракты

- **Вход:** JSON `PreToolUse` на stdin с `agent_type`, `tool_name`, `tool_input`. Корень проекта
  guard берёт из `CLAUDE_PROJECT_DIR`, а не из пути в вызове.
- **Причины отказа (закрытый набор):** `malformed_payload`, `write_outside_test_paths`,
  `write_path_invalid`, `patch_unparseable`, `runner_only`, `test_id_invalid`, `tool_not_allowed`, `guard_unavailable`
  и причины проверки активации: `agent_missing`, `scoped_hook_unsupported`, `config_invalid`,
  `test_author_config_invalid`, `test_paths_missing`, `test_runner_missing`, `write_zone_rejected`.
- **Код выхода:** всегда `0`.

## Источник

[test-author-guard.py](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/hooks/test-author-guard.py),
[test_guard.py](https://github.com/PVMalove/agent-harness-next/blob/master/tests/test_author/test_guard.py),
[test_compatibility.py](https://github.com/PVMalove/agent-harness-next/blob/master/tests/test_author/test_compatibility.py),
[docs/agents/test-author.md](../agents/test-author.md),
ADR 0035
