# Настройки проекта

Проект настраивают два основных контракта в `.harness/` и несколько файлов рядом с ними.
`project.json` описывает сам проект: язык, ветки, команды QA gate, трекер, тестовую зону, hook
policy и память. `orchestration.json` описывает, как coordinator и runtime ведут роли, согласование,
доступ и проверки. Он появляется вместе с capability `backend-orchestration`. Кроме них, настройку
дополняют инвентарь интеграций, сгенерированная hook policy, native-конфиги рантаймов, секреты и
окружение.

## С чего начать настройку {#agent-setup}

??? quote ah-skill-text "Промпт для агента: с чего начать"

    ```text
    Help me choose where to begin configuring this installed harness.

    Follow repository instructions. Keep questions, choices and user-facing summaries in Russian.
    Read existing configuration and installed documentation before proposing changes; missing files
    are not permission to initialize or overwrite anything. Ask only for unresolved facts, one question
    at a time. Offer 2-4 concrete choices plus «Другое», with one consequence each. Put an evidence-based
    recommendation first and mark it «Рекомендуется»; otherwise ask for the missing fact.
    Never read authentication files or request, print, copy or store token/key values.

    Read .harness/project.json, orchestration.json, integrations.json and harness.lock only if present,
    plus installed schemas/examples and settings documentation. Inspect available health diagnostics.
    Explain which settings are already valid, missing or blocked. Ask what the user wants to achieve:
    basic project workflow, role orchestration, external/container execution or integration inventory.
    Start with project metadata, branches and actual QA commands. Add orchestration only when required
    and installed; ask about providers, models and transports instead of selecting them silently.
    Keep approval, access, verification, context and environment decisions separate. Use the relevant
    page's focused prompt for the next group. Ask about environment-variable names only; credentials
    are entered by the user privately. Agree on one small configuration step before editing.

    Preserve unrelated configuration. Show the exact proposed diff, assumptions and remaining
    prerequisites. Wait for approval, then apply only the approved diff with Edit/Write.
    Run harness health and, when orchestration is installed, config validate --canonical --json.
    Distinguish skipped from passed checks.
    Report results and the next smallest step. Do not install tools, change credentials/trust,
    start or restart services, migrate state, send workers, change Git, commit or open a PR.
    Give any such commands for separate review instead of executing them automatically.
    ```

## Два основных контракта

Оба файла находятся в `.harness/`.

| Контракт | Кто создаёт, кто читает, чем проверяется |
| --- | --- |
| [project.json](project.md) | Установщик создаёт его из шаблона при `harness init`, `adopt` или `update`, если файла ещё нет. Дальше файл ведёт проект. Читают qa-gate, pr-composer, code-review, to-guide, test-author и hooks. Health: `files.project_json`. |
| [orchestration.json](orchestration/index.md) | Появляется с capability `backend-orchestration`: если файла нет, установщик копирует его из `.harness/orchestration.example.json`. Дальше файл ведёт проект. Читают coordinator, `harness-runtime` и мастер настройки консоли. Health: `files.orchestration_config`. |

Установщик создаёт `project.json` один раз и больше его не перезаписывает. `orchestration.json`
он тоже создаёт, только если файла нет. `harness update` обновляет управляемый пример
`.harness/orchestration.example.json`. Проектный `orchestration.json` он заменяет новой версией,
только если вы файл не меняли: содержимое совпадает с baseline, записанным в `harness.lock`.
Изменённый файл перезаписывают только явные флаги `--force-seed-file .harness/orchestration.json`,
`--force-seed-files` или `--force`.

## Что ещё входит в настройку

Кроме двух контрактов, у проекта есть настройки, которые задаются отдельно:

- `.harness/integrations.json`: инвентарь native-конфигов. В нём пути, sha256, runtime'ы,
  `secret_refs` и действие `verify`. Файл проверяет `files.integrations`.
- `.harness/hook-policy.json`: его генерирует установщик, вручную файл не правят. Дрейф показывает
  `hooks.policy`, исправляет `harness update`. Формат и проверка описаны в
  [установке hooks](../../hooks/install-and-update.md).
- Native-конфиги `.claude/settings.json`, `.claude/settings.local.json`, `.codex/hooks.json`,
  `.mcp.json`, `.kimi/mcp.json`, `opencode.json`, `opencode.jsonc`: их читает свой runtime. Harness
  учитывает их в инвентаре. При установке hooks он добавляет управляемые записи и сохраняет
  остальные настройки. Заменить файл целиком можно только отдельным явным действием.
- Секреты: `secret_refs` и `access_policy.*.environment` содержат только имена. Значения хранят
  авторизация CLI, окружение или native-конфиг интеграции. Контейнер получает их из окружения
  `harness-runtime serve`. Токены IPC и консоли создаются отдельно.
- Зависимости: Python 3.12 или новее, `uv` и Git. Backend-оркестрации нужен `harness-runtime`
  (для сборки нужен Rust 1.89 или новее), контейнеру нужен Docker или Podman. Проверки окружения
  имеют префикс `environment.*`. Зависимости вашего проекта harness не устанавливает.

Они описаны на страницах [«Интеграции»](integrations.md),
[«Секреты и токены»](secrets.md) и [«Зависимости и окружение»](environment.md).

## Где лежат схемы

- `.harness/project.schema.json`: схема `project.json`. В самом файле стоит `"$schema": "./project.schema.json"`.
- `.harness/orchestration/orchestration.schema.json`: схема `orchestration.json`. В файле стоит
  `"$schema": "./orchestration/orchestration.schema.json"`.
- `.harness/orchestration.example.json`: управляемый пример полной конфигурации. Его дрейф
  показывает `harness diff`.

По схемам редактор подсказывает поля и проверяет значения. Правила задают схема и валидатор
`harness health`, а пример их не задаёт.

## Как править безопасно

1. Правьте файл инструментом Edit или Write. Не используйте перенаправление shell и heredoc:
   правка Edit или Write видна в diff и не обходит проверку.
2. Оставляйте JSON валидным: UTF-8, без комментариев, без висячих запятых, с уникальными ключами.
3. Меняйте одну логическую группу полей за раз и проверяйте результат до следующей правки.
4. После правки запустите `python3 harness/bin/harness.py health <repo>` (или `harness health <repo>`,
   если CLI установлен). Проверка ничего не меняет, а при `fail` печатает причину и команду исправления.
5. Для `orchestration.json` дополнительно запустите `config validate` (см. ниже).
6. Если конфигурацию читает запущенный runtime, перезапустите `harness-runtime serve`: он держит
   конфигурацию в памяти.

## Проверка конфигурации

```bash {.ah-code-wrap}
python3 .harness/orchestration/coordinator.py --repo . config validate --json
python3 .harness/orchestration/coordinator.py --repo . config validate --canonical --json
python3 .harness/orchestration/coordinator.py --repo . config validate --fix --dry-run --json
```

| Команда | Что делает |
| --- | --- |
| `config validate --json` | Печатает диагностику: файл, JSON pointer, код, допустимые значения и безопасное полученное значение. Ничего не пишет. Невалидный конфиг даёт код 2. |
| `config validate --canonical --json` | Дополнительно отклоняет написание, которое требует нормализации, с кодом `config-noncanonical`. |
| `config validate --fix --dry-run --json` | Показывает diff безопасной нормализации enum-полей и не пишет файл. |
| `config validate --fix --json` | Записывает нормализацию транзакцией с резервной копией. |

При загрузке coordinator нормализует enum-поля только в памяти и предупреждает о каждом
исправлении. Файл при этом не меняется. ID, модели, пути и команды coordinator не нормализует.
Дубликат ключа, секрет и неоднозначное значение coordinator считает ошибками и не выбирает
последнее значение. Подробности в [руководстве по backend-оркестрации](../../backend-orchestration.md).

## Страницы раздела

- [project.json](project.md): все поля `.harness/project.json`. Язык, ветки, QA gate, трекер,
  тестовая зона, hook policy, story points, память.
- [orchestration.json](orchestration/index.md): обязательные поля, проверка и карта остальных страниц.
- [Роли и транспорт](orchestration/roles.md): профили провайдеров, планы назначения, языки
  общения и политика инструментов.
- [Политики](orchestration/policies.md): согласование, повторы, внимание, продолжение сессии,
  таймауты и preflight.
- [Доступ и контейнер](orchestration/access.md): `access_policy`, `extensions` и связь с
  контейнерным исполнителем.
- [Верификация](orchestration/verification.md): команды QA, профили и планы проверки, Repo Map и
  Context Package.
- [Интеграции](integrations.md): `.harness/integrations.json`, native-конфиги, `secret_refs` и `verify`.
- [Секреты и токены](secrets.md): доступ к модели, секреты интеграций, токены runtime и консоли.
- [Зависимости и окружение](environment.md): Python, uv, Git, Rust и runtime, Docker или Podman, окружение.
- [Контейнер](container.md): хост, образы, сеть, токен, проверки и типичные ошибки.
- [Test-author](test-author.md): поля, условия включения, причины отказа и живая проверка.

## Соседние руководства

- [Backend-оркестрация](../../backend-orchestration.md): запуск, batch, approval и recovery.
- [Настройка проекта в консоли](../../console-configuration.md): мастер настройки и диагностика.
- [Test-author: руководство агента](../../agents/test-author.md): полный контракт роли.
