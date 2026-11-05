# Справочник

## CLI

| Команда | Назначение |
| --- | --- |
| `harness init <repo>` | Установить snapshot в новый проект |
| `harness adopt <repo>` | Установить поверх существующих скиллов |
| `harness update <repo>` | Обновить managed-файлы и hooks |
| `harness health <repo>` | Проверить окружение, hooks, ledger и память |
| `harness diff <repo>` | Показать расхождения с залоченным snapshot |
| `harness cleanup <repo>` | План и применение очистки sandboxes |
| `harness uninstall <repo>` | Полное удаление harness из проекта |

## Конфигурация

```json
{
  "language": "ru",
  "base_branch": "main",
  "qa_gate_commands": ["make verify"],
  "hook_policy": { "profile": "standard" }
}
```

Схемы и валидаторы — в `harness/project/project.schema.json` и
`harness/orchestration/orchestration.schema.json`.

## Hooks

`minimal`, `standard` и `strict` меняют поведенческую строгость, не ослабляя критические
guard-ы. Профиль задаётся в `.harness/project.json`, источник — только конфиг проекта.

## Агенты

`code-review-spec`, `code-review-standards`, `pr-composer` и optional `test-author`
описаны в `docs/agents/`. Внутренние ADR — в `docs/adr/`.
