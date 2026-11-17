# Роли и транспорт

Эти группы `.harness/orchestration.json` связывают роль с профилем провайдера, runtime, моделью
и транспортом. Manifest роли задаёт её поведение и режим; конфигурация выбирает исполнителя и
manifest не переопределяет. Если файл ещё не настроен, начните с [индекса контракта](index.md).

`<ключ>` в путях ниже означает имя записи словаря, а не буквальный JSON-ключ. Каждый JSON-блок
на странице нужно объединить с текущим файлом. Model и effort в блоках взяты из управляемого
примера; это не значения по умолчанию для вашего проекта.

## Профили провайдеров: provider_profiles

Каждый именованный профиль содержит все три поля. Учётные данные в профиле запрещены.

| Поле | Контракт |
| --- | --- |
| `provider_profiles.<ключ>.capabilities` | Обязательный непустой массив непустых строк. Возможности профиля должны подходить к `required_capabilities` manifest'а роли. |
| `provider_profiles.<ключ>.fallback` | Обязательный массив имён резервных профилей в порядке выбора. `[]`: резервов нет. Каждая ссылка должна существовать; циклы валидатор отклоняет. |
| `provider_profiles.<ключ>.known_limitations` | Обязательный массив непустых строк с известными ограничениями. `[]`: ограничения не перечислены. |

Описание схемы перечисляет capability: `architecture-analysis`, `backend-development`,
`code-review`, `independent-verification`, `database-migrations`, `messaging-integration`,
`conflict-resolution`. Это не `enum`: валидатор сверяет возможности профиля с manifest'ами ролей.
Fallback не меняет runtime уже утверждённого brief.

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

Ключи плана совпадают с именами установленных manifest'ов: `architect`, `developer`,
`code-review`, `qa`, `verification`, `database-migrations`, `messaging-integration`,
`conflict-resolver`. В поставке `architect`, `code-review`, `qa` и `verification` работают в
режиме `read-only`, остальные четыре в режиме `write`. Если назначения непустые, `code-review`
обязателен. `test-author` помогает developer и отдельного назначения в оркестрации не имеет;
см. [руководство test-author](../../../agents/test-author.md).

| Поле | Контракт |
| --- | --- |
| `assignment_plans.<ключ>.zone` | Необязательная непустая строка: устаревшее имя записи из `backend_zones`. В новых планах задавайте `write_paths`. |
| `assignment_plans.<ключ>.write_paths` | Необязательный непустой массив непустых строк: потолок записи роли. Без поля потолок равен всему репозиторию или путям указанной устаревшей зоны. Scope batch не может быть шире потолка. Если заданы и пути, и зона, пути должны лежать внутри зоны. |
| `assignment_plans.<ключ>.transport` | `in-process` или `external`. По умолчанию `in-process`: роль работает подагентом сессии coordinator. `external` запускает роль через проектный runtime adapter. |
| `assignment_plans.<ключ>.default_runtime` | Необязательное имя runtime из этого плана. Если runtime несколько, а поля нет, выберите runtime флагом `--runtime`. Единственный runtime coordinator выбирает сам. |
| `assignment_plans.<ключ>.runtimes.<ключ>.profiles` | Обязательный непустой массив непустых имён из `provider_profiles`. Валидатор проверяет, что профили существуют и подходят роли. |
| `assignment_plans.<ключ>.runtimes.<ключ>.model` | Обязательная непустая строка: CLI-алиас или ID модели без пробелов. Общей модели по умолчанию нет. ID из примера может быть недоступен в вашей учётной записи. |
| `assignment_plans.<ключ>.runtimes.<ключ>.effort` | Обязательная строка: `none`, `minimal`, `low`, `medium`, `high`, `xhigh`, `max`, `ultra`. Поддерживает ли уровень выбранный исполнитель, проверяется отдельно. |

У каждого плана обязателен непустой объект `runtimes`. Coordinator записывает в brief выбранные
runtime, model, effort и транспорт. Read-only роль с `write_paths` не становится writer.
Транспорт, рабочее дерево и ограничения доступа настраиваются отдельно: `external` сам по себе
не означает контейнер. Ресурсы задаёт [access_policy](access.md).

Пример назначает только `developer` и обязательный `code-review` с профилем выше. Это не полный
маршрут: добавьте планы остальных ролей, которые используете. `write_paths: ["**"]` разрешает
запись во весь репозиторий; выберите потолок, который подходит вашему проекту.

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

Объект необязателен. Без него агенты общаются между собой на `en`, а coordinator пишет отчёты на
`ru`. Если объект указан, оба поля обязательны. Язык страницы сайта на контракт не влияет.

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

Объект необязателен. Coordinator берёт **полный список** инструментов по приоритету: запись
роли, затем запись режима, затем встроенный набор режима из manifest'а. Списки не складываются.

| Поле | Контракт |
| --- | --- |
| `tool_policy.modes` | Необязательный словарь с ключами `read-only` и `write`. Значение каждой записи: непустой массив уникальных непустых имён инструментов. |
| `tool_policy.roles` | Необязательный словарь: для установленной роли непустой массив уникальных непустых имён инструментов. Запись роли целиком заменяет набор режима. Имена ролей те же, что в `assignment_plans`. |

Встроенный набор `read-only` содержит `Read`, `Grep`, `Glob`, `Bash`; набор `write` добавляет
`Edit` и `Write`. Если test-author включён, встроенный набор developer получает ещё
`Agent(test-author)`. В явный набор этот инструмент сам не добавляется.

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

В этом примере `code-review` получает `Bash` из своей записи, хотя общий набор `read-only` его не
содержит. `allowed_tools` задаёт рабочий набор, который coordinator записывает в brief. Он не
запрещает глобальные инструменты runtime и не заменяет `access_policy`. Правка конфигурации
действует только на следующие brief; уже утверждённые не меняются. Подробнее в
[руководстве](../../../backend-orchestration.md).

## Настроить назначения с агентом {#agent-assignments}

Промпт помогает выбрать исполнителей, когда оркестрация уже установлена. Агент не должен выбирать
модель по имени текущего агента и не должен попутно менять согласование и доступ.

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
