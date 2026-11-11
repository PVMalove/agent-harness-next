# Роли и транспорт

Эти группы `.harness/orchestration.json` связывают роль с профилем провайдера, runtime, моделью
и транспортом. Manifest определяет поведение и режим роли; конфигурация выбирает исполнителя,
не переопределяя manifest. Начните с [индекса контракта](index.md), если файл ещё не настроен.

`<ключ>` в путях ниже — имя записи словаря, а не буквальный JSON-ключ. Все JSON-блоки —
фрагменты для объединения с текущим файлом. Их model и effort взяты из управляемого примера,
а не выбраны по умолчанию для вашего проекта.

## Профили провайдеров: provider_profiles

Каждый именованный профиль содержит все три поля. Учётные данные в нём запрещены.

| Поле | Контракт |
| --- | --- |
| `provider_profiles.<ключ>.capabilities` | Обязательный непустой массив непустых строк. Возможности профиля должны быть совместимы с `required_capabilities` manifest'а роли. |
| `provider_profiles.<ключ>.fallback` | Обязательный массив имён резервных профилей в порядке выбора. `[]` означает отсутствие резервов. Ссылки должны существовать; циклы отклоняются. |
| `provider_profiles.<ключ>.known_limitations` | Обязательный массив непустых строк с известными ограничениями. `[]` означает, что ограничения не перечислены. |

Схема документирует capability: `architecture-analysis`, `backend-development`, `code-review`,
`independent-verification`, `database-migrations`, `messaging-integration`, `conflict-resolution`.
Это перечень из описания схемы, а не `enum`: проверяющий код сопоставляет возможности с manifest'ами.
Fallback не меняет runtime утверждённого brief.

```json
{
  "provider_profiles": {
    "claude-profile": {
      "capabilities": [
        "architecture-analysis",
        "backend-development",
        "code-review",
        "independent-verification"
      ],
      "fallback": [],
      "known_limitations": []
    }
  }
}
```

## Назначения ролей: assignment_plans

Ключи — имена установленных manifest'ов: `architect`, `developer`, `code-review`, `qa`,
`verification`, `database-migrations`, `messaging-integration`, `conflict-resolver`.
В поставляемом наборе `architect`, `code-review`, `qa` и `verification` имеют режим `read-only`;
остальные четыре — `write`. Если назначения непустые, `code-review` обязателен.
`test-author` — помощник developer, а не отдельное назначение orchestration; см.
[руководство test-author](../../../agents/test-author.md).

| Поле | Контракт |
| --- | --- |
| `assignment_plans.<ключ>.zone` | Необязательная непустая строка. Устаревшее имя существующей записи `backend_zones`; для новых планов используйте явный `write_paths`. |
| `assignment_plans.<ключ>.write_paths` | Необязательный непустой массив непустых строк: потолок записи роли. Без него — весь репозиторий либо пути указанной устаревшей зоны. Scope batch не может быть шире; при совместном указании путей и зоны пути должны оставаться внутри зоны. |
| `assignment_plans.<ключ>.transport` | `in-process` или `external`. Default — `in-process`: подагент сессии coordinator. `external` использует проектный runtime adapter. |
| `assignment_plans.<ключ>.default_runtime` | Необязательное имя runtime из этого плана. Если runtime несколько, а поля нет, выберите runtime флагом `--runtime`; единственный runtime выбирается автоматически. |
| `assignment_plans.<ключ>.runtimes.<ключ>.profiles` | Обязательный непустой массив непустых имён из `provider_profiles`. Профили проверяются на существование и совместимость с ролью. |
| `assignment_plans.<ключ>.runtimes.<ключ>.model` | Обязательная непустая строка: CLI-алиас или ID модели без пробелов. Универсальной модели по умолчанию нет; наличие ID в примере не гарантирует доступ в вашей учётной записи. |
| `assignment_plans.<ключ>.runtimes.<ключ>.effort` | Обязательная строка: `none`, `minimal`, `low`, `medium`, `high`, `xhigh`, `max`, `ultra`. Доступность уровня у выбранного исполнителя проверяется отдельно. |

У каждого плана обязателен непустой объект `runtimes`. Coordinator фиксирует выбранные runtime,
model, effort и транспорт в brief. Наличие `write_paths` у read-only роли не превращает её
в writer. Транспорт, рабочее дерево и ограничения доступа — разные настройки; `external`
сам по себе не означает контейнер. Ресурсы задаёт [access_policy](access.md).

Пример назначает только `developer` и обязательный `code-review`, используя профиль выше.
Это не полный маршрут: добавьте планы остальных используемых ролей. `write_paths: ["**"]`
означает весь репозиторий; при настройке выберите подходящий проекту потолок.

```json
{
  "assignment_plans": {
    "developer": {
      "write_paths": [
        "**"
      ],
      "transport": "in-process",
      "default_runtime": "claude",
      "runtimes": {
        "claude": {
          "profiles": [
            "claude-profile"
          ],
          "model": "claude-opus-5-5",
          "effort": "xhigh"
        }
      }
    },
    "code-review": {
      "transport": "in-process",
      "default_runtime": "claude",
      "runtimes": {
        "claude": {
          "profiles": [
            "claude-profile"
          ],
          "model": "claude-opus-5-5",
          "effort": "xhigh"
        }
      }
    }
  }
}
```

## Языки: communication_policy

Объект необязателен; без него действуют `en` между агентами и `ru` в отчётах coordinator.
Если объект указан, оба поля обязательны. Язык страницы сайта этого контракта не меняет.

| Поле | Контракт |
| --- | --- |
| `communication_policy.agent_to_agent_language` | Только `en` (`const`): язык технического обмена между агентами. |
| `communication_policy.coordinator_report_language` | Только `ru` (`const`): язык отчётов coordinator для человека. |

```json
{
  "communication_policy": {
    "agent_to_agent_language": "en",
    "coordinator_report_language": "ru"
  }
}
```

## Рабочие инструменты: tool_policy

Объект необязателен. Coordinator выбирает **полный список** по приоритету: запись роли,
иначе запись режима, иначе встроенный набор режима manifest'а. Списки не складываются.

| Поле | Контракт |
| --- | --- |
| `tool_policy.modes` | Необязательный словарь с ключами `read-only` и `write`. Значение каждой записи — непустой массив уникальных непустых имён инструментов. |
| `tool_policy.roles` | Необязательный словарь: для каждой установленной роли — непустой массив уникальных непустых имён инструментов. Перекрывает набор режима целиком. Имена ролей — те же, что у `assignment_plans`. |

Встроенный набор `read-only` — `Read`, `Grep`, `Glob`, `Bash`; набор `write` дополнительно
содержит `Edit`, `Write`. При активном test-author встроенный набор developer может также
включать `Agent(test-author)`; явный набор не дополняется автоматически.

```json
{
  "tool_policy": {
    "modes": {
      "read-only": [
        "Read",
        "Grep",
        "Glob"
      ],
      "write": [
        "Read",
        "Grep",
        "Glob",
        "Bash",
        "Edit",
        "Write"
      ]
    },
    "roles": {
      "code-review": [
        "Read",
        "Grep",
        "Glob",
        "Bash"
      ]
    }
  }
}
```

В этом примере `code-review` получает `Bash` из собственной записи, хотя общий набор
`read-only` его не содержит. `allowed_tools` — рабочий набор, фиксируемый в brief, а не
запрет глобальных инструментов runtime и не замена `access_policy`. Правка конфигурации влияет
только на следующие brief; уже утверждённые не меняются. Подробнее — в
[руководстве](../../../backend-orchestration.md).

## Настроить назначения с агентом {#agent-assignments}

Промпт помогает выбрать исполнителей для уже установленной оркестрации. Он не должен
назначать модель по имени текущего агента или менять согласование и доступ заодно с ролями.

??? quote ah-skill-text "Промпт для агента: профили и назначения ролей"

    ```text
    Configure role assignments in this project's .harness/orchestration.json.
    Follow repository instructions. Use English for technical instructions and Russian
    for all questions, choices and user-facing summaries.

    Read current project and orchestration configs, the installed schema, the managed
    example and role manifests. Run read-only health/config validation if available.
    Do not read credentials or authentication files. Preserve existing assignments
    unless I request a change; ask only for facts not established by the repository.

    Work through missing decisions one question at a time:
    - Which roles are needed: keep session-based assignments or configure explicit ones?
    - Which configured runtimes, available model IDs/aliases and effort levels should
      each role use? For multiple runtimes, which is the default?
    - Which write ceiling does each writer need, and which transport is intended?
    - Are fallback profiles, known limitations or tool overrides needed?
    Do not assume your own model or the managed example is the desired choice.

    Offer 2-4 concrete Russian choices plus «Другое», each with a one-line consequence.
    Put a justified recommendation first and mark it «Рекомендуется»; ask for missing
    facts when a recommendation is not possible. Example question:
    «Как запускать роль?» — «in-process: подагент текущей сессии»,
    «external: проектный runtime adapter», «Другое».
    Explain that external transport does not itself provide container isolation.

    Build only supported provider_profiles, assignment_plans, communication_policy
    and tool_policy fields. Reuse real profile/runtime IDs; ask for unknown model IDs
    and effort rather than guessing. Include code-review for non-empty assignments.
    Check capabilities against manifests, fallback references/cycles, runtime defaults,
    write ceilings and complete tool-list overrides. Keep communication languages en/ru.
    Do not alter manifests, approvals, access, execution policy, unrelated settings
    or existing dispatches. Never request token/key values or put them in configuration.

    Show the exact diff and explain choices, defaults and unresolved facts.
    Wait for my approval before applying it with Edit/Write. Validate the approved file
    with config validate --canonical --json and harness health through installed entry
    points. Report failures and unverified runtime/model availability separately.
    Do not run workers, change Git state, commit or open a PR.
    ```

## Проверка и следующий шаг

Выполните команды из [индекса](index.md#config-validation). Затем переходите к
[политикам](policies.md), [доступу](access.md) или [верификации](verification.md).
Жизненный цикл ролей и handoff описаны в [backend-руководстве](../../../backend-orchestration.md).
