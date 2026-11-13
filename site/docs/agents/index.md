# Карта агентов и руководств

Здесь собраны операционные руководства Harness Next и русские описания проектных агентов.
Руководства artifacts, git-workflow, issue-tracker, test-author, triage-labels и worktrees
соответствуют шаблонам `harness/project/docs-agents/`. `harness init` разворачивает эти шаблоны в
`docs/agents/` целевого проекта: по этим документам работают агенты. `releases.md` и
`console-web-home-checklist.md` относятся только к этому репозиторию. Сам этот обзор и описания
агентов в целевой проект не попадают. Публичные руководства по workflow и CLI
([руководства](../guides/workflow.md), [справочник CLI](../reference/cli.md)) и руководство по
backend-оркестрации ([`backend-orchestration.md`](../backend-orchestration.md)) написаны для
разработчика.

## Субагенты

Проектные субагенты из `harness/project/agents/`. Описания code-review-standards,
code-review-spec и pr-composer содержат название и локализацию, полный перевод манифеста и
контракты. Test-author описан руководством: конфигурация, защита и контракт вызова.

| Агент | Назначение |
| --- | --- |
| [code-review-standards](code-review-standards.md) | Ось Standards скилла `code-review`: соответствие стандартам репозитория и «запахи» Фаулера. |
| [code-review-spec](code-review-spec.md) | Ось Spec скилла `code-review`: полнота реализации и выход за рамки задачи. |
| [pr-composer](pr-composer.md) | Заполняет тело PR по шаблону проекта и возвращает путь к файлу. |
| [test-author](test-author.md) | Пишет один поведенческий Red-тест в защищённой тестовой зоне и запускает его через изолированный runner. |

## Процесс и Git

| Документ | Содержимое |
| --- | --- |
| [git-workflow](git-workflow.md) | Ветки, коммиты, PR и закрытие тикетов. |
| [issue-tracker](issue-tracker.md) | Работа с трекером issues. |
| [triage-labels](triage-labels.md) | Метки триажа и их цвета. |
| [worktrees](worktrees.md) | Параллельная работа в Git worktree. |

## Артефакты и релизы

| Документ | Содержимое |
| --- | --- |
| [artifacts](artifacts.md) | Временные артефакты и их размещение. |
| [releases](releases.md) | Выпуск версии и GitHub Release. |

## Приёмка

| Документ | Содержимое |
| --- | --- |
| [console-web-home-checklist](console-web-home-checklist.md) | Ручная приёмка Главной SPA веб-консоли. |

## Связанные документы

- Навыки и роли конвейера: [карта навыков](../skills/index.md)
- Hooks: [карта hooks](../hooks/index.md)
