# Настройки проекта

Проект настраивают два файла в `.harness/`. `project.json` описывает сам проект: язык, ветки,
команды QA gate, трекер, тестовую зону и память. `orchestration.json` описывает, как coordinator и
runtime ведут роли, согласование и проверки. Первый файл есть в любом проекте, второй появляется
вместе с capability `backend-orchestration`.

## Два файла

| Файл | Когда появляется | Кто пишет | Кто читает |
| --- | --- | --- | --- |
| `.harness/project.json` | `harness init`, `adopt` или `update`, если файла ещё нет | проект после создания; установщик пишет файл из шаблона | qa-gate, pr-composer, code-review, to-guide, test-author и hooks |
| `.harness/orchestration.json` | установка capability `backend-orchestration` | проект; при отсутствии копируется из `.harness/orchestration.example.json` | coordinator, `harness-runtime` и мастер настройки консоли |

Установщик не перезаписывает существующие значения: `project.json` создаётся один раз, а
`orchestration.json` — только если его нет. `harness update` обновляет управляемый пример
`.harness/orchestration.example.json`, но не проектный конфиг; перезапись проектного файла требует
явного `--force-seed-file`.

## Где лежат схемы

- `.harness/project.schema.json` — схема `project.json`; в самом файле стоит `"$schema": "./project.schema.json"`.
- `.harness/orchestration/orchestration.schema.json` — схема `orchestration.json`; в файле стоит
  `"$schema": "./orchestration/orchestration.schema.json"`.
- `.harness/orchestration.example.json` — управляемый пример полной конфигурации; `harness diff`
  показывает его дрейф.

Схемы нужны редактору для подсказок и проверки. Источником истины остаются схема и валидатор
`harness health`, а не пример.

## Как править безопасно

1. Правьте файл инструментом Edit или Write, а не перенаправлением shell и не heredoc. Так
   изменение видно в diff и не обходит проверку.
2. Оставляйте JSON валидным: UTF-8, без комментариев, без висячих запятых, с уникальными ключами.
3. Меняйте одну логическую группу полей за раз и проверяйте результат до следующей правки.
4. После правки запустите `python3 harness/bin/harness.py health <repo>` (или `harness health <repo>`,
   если CLI установлен). Проверка ничего не меняет, а на `fail` печатает причину и команду исправления.
5. Для `orchestration.json` дополнительно запустите `config validate` (см. ниже).
6. Если конфигурацию читает запущенный runtime, перезапустите `harness-runtime serve`: процесс
   держит конфигурацию в памяти.

## Проверка конфигурации

```bash
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
исправлении; файл при этом не меняется. ID, модели, пути и команды не нормализуются. Дубликат
ключа, секрет и неоднозначное значение — ошибки, а не повод выбрать последнее значение.
Подробности — в [руководстве по backend-оркестрации](../../backend-orchestration.md).

## Страницы раздела

- [project.json](project.md) — все поля `.harness/project.json`: язык, ветки, QA gate, трекер,
  тестовая зона, hook policy, story points, память.
- [orchestration.json](orchestration/index.md) — обязательные поля, проверка и карта остальных страниц.
- [Роли и транспорт](orchestration/roles.md) — профили провайдеров, планы назначения, языки
  общения и политика инструментов.
- [Политики](orchestration/policies.md) — согласование, повторы, внимание, продолжение сессии,
  таймауты и preflight.
- [Доступ и контейнер](orchestration/access.md) — `access_policy`, `extensions` и связь с
  контейнерным исполнителем.
- [Верификация](orchestration/verification.md) — команды QA, профили и планы проверки, Repo Map и
  Context Package.
- [Контейнерный исполнитель](container.md) — хост, образы, сеть, токен, проверки и типичные ошибки.
- [Test-author](test-author.md) — поля, условия активации, причины отказа и живая проверка.

## Соседние руководства

- [Backend-оркестрация](../../backend-orchestration.md) — запуск, batch, approval и recovery.
- [Настройка проекта в консоли](../../console-configuration.md) — мастер настройки и диагностика.
- [Test-author: руководство агента](../../agents/test-author.md) — полный контракт роли.
