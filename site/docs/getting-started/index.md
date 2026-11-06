# Быстрый старт

Agent Harness Next разворачивает в проект скиллы, hooks и контекстные документы как проверяемый
snapshot. После установки проект живёт автономно: skills и hooks работают через нативные механизмы
Claude Code и Codex, а оркестрация использует Rust runtime и локальный runtime-store.

!!! note "Ранний доступ"

    Сайт описывает текущую версию, но поведение и флаги ещё меняются. Перед установкой в рабочий
    проект сделайте backup и проверьте требования.

## Путь установки

Выберите сборку: схема покажет, какой snapshot окажется в проекте. Узлы кликабельны.

<div class="ah-flow" id="ah-install-flow">
  <button class="ah-diagram-expand ah-core-expand" id="ah-install-expand" type="button" aria-haspopup="dialog">Развернуть</button>
  <div class="ah-core-scroll"><div class="ah-core is-fit" id="ah-install-map"></div></div>
  <div class="ah-flow-note" id="ah-install-note" aria-live="polite">
    <b>Выберите сборку</b>
    <span>Нажмите на capability или на любой узел схемы.</span>
  </div>
</div>

## Требования

| Компонент | Требование |
| --- | --- |
| Python | 3.12 или новее |
| Git | Каталог проекта уже инициализирован как Git-репозиторий |
| Runtime | Claude Code или Codex: skills и hooks подключаются нативно |
| ОС | Linux; на Windows — поддерживаемый runtime и named pipe |
| `uv` | Для веб-консоли и локальных проверок harness |
| Опционально | Docker или rootless Podman для контейнерного worker и QA |

## 1. Установите глобальный слой

Глобальный слой ставится однократно на машину: минимальный профиль инструкций и скиллы
`start-project` и `integrate-project`. Параметр `--runtime` повторяемый.

```bash
python3 bin/install-global.py --target-home "$HOME" \
  --runtime claude --runtime codex
```

`--check` показывает статус без записи, `--replace-conflicts` заменяет конфликтующие файлы,
предварительно сохраняя их backup. MCP, модели, плагины, credentials и permissions установщик
не трогает.

## 2. Подключите harness к проекту

Новый проект удобнее начинать через скилл `start-project`, существующий — через `integrate-project`:
он сначала изучает соглашения репозитория, а потом встраивает harness.

Прямая установка в Git-репозиторий:

```bash
python3 harness/bin/harness.py init /path/to/repository \
  --capability engineering-suite \
  --project-type software --stack python --base-branch main --language ru \
  --qa-gate-command "make test"
```

Если в проекте уже есть свои скиллы с теми же именами, используйте `adopt`: он сохраняет всё, что
не входит в выбранную capability, и падает со списком конфликтов. `--replace-conflicts` заменяет
конфликтующие каталоги без backup, поэтому сначала проверьте список.

```bash
python3 harness/bin/harness.py adopt /path/to/repository \
  --capability engineering-suite --replace-conflicts
```

Capability задаёт состав snapshot; сборки взаимоисключающие.

| Capability | Что добавляет |
| --- | --- |
| `project-foundation` | Доменно-нейтральная база по умолчанию: дизайн, research, handoff, язык проекта. |
| `mattpocock-suite` | Полный upstream-набор, закреплённый на проверенном коммите. |
| `engineering-suite` | Инженерный workflow: эпики и тикеты, триаж, двухосевое review, `qa-gate`, подготовка PR. |
| `backend-orchestration` | Поверх `engineering-suite`: coordinator, роли, briefs, worktrees, ledger и QA lane. |

## 3. Проверьте установку: health

`health` проверяет установку и окружение и без флагов ничего не меняет. Запускайте его после
`init`, `adopt` или `update`, после клонирования проекта и когда агент не обнаруживает скиллы.

```bash
python3 harness/bin/harness.py health /path/to/repository
python3 harness/bin/harness.py health /path/to/repository --fix
python3 harness/bin/harness.py health /path/to/repository --online
python3 harness/bin/harness.py health /path/to/repository --json
```

| Флаг | Что делает |
| --- | --- |
| без флагов | Локальные проверки файлов, каталогов, окружения и Repo Map. |
| `--fix` | Создаёт отсутствующие каталоги `.harness/` и перегенерирует устаревший registry скиллов; worktree не трогает. |
| `--online` | Добавляет проверки трекера: авторизация `gh`/`glab`, доступность origin, права и метки. |
| `--json` | Печатает машиночитаемый отчёт `schema_version: 1`. |

Каждая строка помечена `✅` ok, `⚠️` warn, `❌` fail или `-` skipped. На `fail` команда сама печатает
причину и команду исправления. Группа «Оркестрация» появляется только при `backend-orchestration`:
там видно ledger, незавершённые batch, dispatch без активности и неучтённые worktree.

## 4. Первые команды

```bash
python3 harness/bin/harness.py list /path/to/repository
python3 harness/bin/harness.py diff /path/to/repository
python3 harness/bin/harness.py update /path/to/repository
```

| Команда | Назначение |
| --- | --- |
| `list <repo>` | Список установленных скиллов. |
| `diff <repo>` | Расхождения с залоченным snapshot; `--json` для машиночитаемого отчёта. |
| `update <repo>` | Подтягивает новую версию capability и сохраняет локальные правки. |
| `console <repo>` | TUI-пульт и веб-консоль: задачи, оркестрация, отчёты и восстановление. |
| `cleanup <repo>` | План очистки `.harness/.sandboxes`; `--apply` удаляет, `--mode hard` требует `--apply --confirm HARD`. |
| `uninstall <repo>` | План и полное удаление harness; `--apply --confirm UNINSTALL` сохраняет изменённые файлы в `.harness-uninstall-backup/`. |

`console` — beta: ему нужен `uv`, а при первом запуске он скачивает зависимости, поэтому нужен
доступ к сети. `console --web` поднимает Сервер консоли, печатает URL с токеном и открывает браузер.

Если установлена `backend-orchestration`, добавьте проверку состояния:

```bash
python3 .harness/orchestration/coordinator.py --repo . dispatch preflight
python3 .harness/orchestration/coordinator.py --repo . ledger validate --full
```

## Дальше

- [Рабочий поток](../guides/workflow.md)
- [CLI и конфигурация](../reference/cli.md)
- [Обзор архитектуры](../architecture/overview.md)
- [Rust runtime](../architecture/runtime.md)
- [Справочник](../reference/index.md)
- [Демо](../demo/index.md)
