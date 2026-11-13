# Карта навыков и ролей

Здесь собраны короткие описания скиллов и ролей харнесса. На каждой странице есть русское название, триггеры, ответственность и контракт входа и выхода (Input/Output). На части страниц есть PNG-схема Archify. Полные первоисточники лежат в `skills/first-party/engineering/`, `harness/orchestration/roles/`, `harness/orchestration/playbook.md` и `harness/orchestration/pilot.md`.

## Командные навыки

- [ask-matt](ask-matt.md), [wayfinder](wayfinder.md), [triage](triage.md)
- [diagnosing-bugs](diagnosing-bugs.md), [tdd](tdd.md)
- [architect](architect.md#architect_1): ручное сравнение архитектурных вариантов
- [grill-me](grill-me.md), [grilling](grilling.md), [grill-with-docs](grill-with-docs.md)
- [to-spec](to-spec.md), [to-tickets](to-tickets.md), [to-guide](to-guide.md)
- [implement](implement.md), [fast-implement](fast-implement.md), [code-review](code-review.md), [qa-gate](qa-gate.md), [to-pull-requests](to-pull-requests.md)
- [start-project](start-project.md), [integrate-project](integrate-project.md), [setup-labels](setup-labels.md), [delivery-stats](delivery-stats.md)

## Роли конвейера

- [Coordinator](coordinator.md), [Architect](architect.md), [Developer](developer.md)
- [Code Review](code-review-role.md), [QA](qa.md)
- [Messaging Integration](messaging-integration.md), [Database Migrations](database-migrations.md), [Conflict Resolver](conflict-resolver.md)
- [Playbook](playbook.md), [Pilot](pilot.md)

## Закреплённые upstream skills

Русские описания всех 25 скиллов из `skills/vendor/mattpocock/` собраны в [vendor/](vendor/index.md).
Их исходные `SKILL.md` закреплены в upstream snapshot, вручную их не правят. First-party
overrides с теми же именами описаны на страницах этого каталога по текущей версии `engineering-suite`.

## Связанные документы

- Discovery Context (список путей, важных для задачи) начинается в `/grilling` с opt-in
  `Live Artifact`, затем переходит в `Relevant Files` спецификации и в Path inventory тикета.
  Backend batch берёт `Context Package`, который собирается без LLM, checkpoint/continuation для
  write-роли и base-commit gate. Правила работы собраны в
  [backend-orchestration](../backend-orchestration.md). Текущее устройство описывает ADR 0003,
  конвейер описывает ADR 0005.
- Агенты: [Агенты](../agents/index.md)
- Hooks: [Hooks](../hooks/index.md)
- Схемы конкретных процессов (`/implement`, `/to-spec`, `/wayfinder`, `/triage` и др.): [Схемы](../diagrams/index.md)
