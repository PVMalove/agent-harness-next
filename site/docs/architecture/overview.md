# Обзор архитектуры

Политика и исполнение разделены: Python принимает решения и ведёт approvals, Rust runtime хранит
operational state и запускает процессы, а Git владеет историей и кандидатами.

<div class="ah-arch">
  <div class="panel">
    <div class="layer">
      <div class="tag">Policy</div>
      <div class="nodes"><span class="node">coordinator</span> <span class="node">approvals</span> <span class="node primary">человек</span></div>
    </div>
    <div class="layer">
      <div class="tag">Runtime</div>
      <div class="nodes"><span class="node ok">supervisor</span> <span class="node ok">reconcile</span> <span class="node ok">engine</span></div>
    </div>
    <div class="layer">
      <div class="tag">State</div>
      <div class="nodes"><span class="node">SQLite WAL</span> <span class="node">audit</span> <span class="node">leases</span></div>
    </div>
  </div>
  <div class="panel">
    <div class="layer">
      <div class="tag">Git</div>
      <div class="nodes"><span class="node">candidate</span> <span class="node">branch</span> <span class="node">worktree</span></div>
    </div>
    <div class="layer">
      <div class="tag">Проект</div>
      <div class="nodes"><span class="node">project.json</span> <span class="node">harness.lock</span> <span class="node">REGISTRY.md</span></div>
    </div>
  </div>
</div>

## Policy и исполнение

Python работает как policy-слой: coordinator планирует batch, собирает approvals и принимает
отчёты ролей. Rust runtime работает как доверенный супервизор хоста: он исполняет только уже
одобренный brief, проверяет digest плана и образа и сам policy не решает. Каждый handoff
подтверждается отдельно, поэтому роль не может расширить свой scope по ходу работы.

Главное правило: operational state хранится в runtime store, а не в файлах, которые правит
Python. У каждой сущности ровно один writer, и переход между состояниями сохраняется транзакцией,
а не дописыванием файла.

Git владеет историей: кандидат, ветки и worktree остаются обычными Git-объектами, и runtime их не
переписывает. Проектные контракты `.harness/project.json`, `harness.lock` и `REGISTRY.md`
принадлежат целевому репозиторию; их обновляет установщик harness, а не runtime.

## Кто владеет чем

| Сущность | Writer | Что это значит |
| --- | --- | --- |
| Lifecycle batch/dispatch | Rust runtime | Решение принимает Python, runtime сохраняет его транзакцией. Python не пишет в store напрямую, только через IPC. |
| Approvals и policy | Python | Решение принимают человек и policy-слой; runtime исполняет сохранённое решение. |
| Операционный intent | Rust store | Idempotency key, attempt и reconcile хранятся в одной транзакции. |
| Git-история и candidate | Git | Кандидат, ветки и worktree остаются обычными Git-объектами; runtime их не переписывает. |
| Audit | Rust store | Хэш-цепочка с checkpoint для инкрементальной проверки. |

!!! note "Fallback-writer запрещён"

    Если runtime недоступен, Python не начинает писать в файловый ledger «чтобы продолжить».
    Операция возвращает типизированную ошибку с remedy.

## Границы доверия

Границы проходят между Python policy, Rust runtime и недоверенным worker. Runtime выступает
доверенным супервизором хоста, а worker готовит кандидата в контейнере или отдельном процессе.

| Граница | Правило |
| --- | --- |
| Runtime socket | Только peer uid/SID и capability-токен; каталог `0700`, сокет `0600`. |
| Engine socket | Никогда не монтируется в worker или QA-контейнер. |
| Approval | Неизменяемый brief связывает план, образ, policy digest и verification digest. |
| Secrets | Не попадают в командную строку, логи, audit и отчёты. |

Подробности в разделе [Безопасность](runtime.md) и в ADR 0021.

## Слои и модель поставки

| Слой | Источник истины | Ответственность |
| --- | --- | --- |
| Capability catalog | `harness/CAPABILITIES.json` | Определяет состав snapshot и зависимости между сборками. |
| Skill packages | `skills/vendor/`, `skills/first-party/` | Инструкции, переводы и overrides; vendor-снимок вручную не правят. |
| Project snapshot | `.harness/skills/`, `harness.lock`, `REGISTRY.md` | Независимая поставка в целевой репозиторий, drift и provenance. |
| Project contract | `.harness/project.json` | Язык, base branch, шаблон ветки и команды проверок. |
| Orchestration core | coordinator и ledger | Policy, approvals, lifecycle batch, audit и dispatch ролей. |
| Evidence execution | gate runner и evidence | Проверки, очищенное от секретов evidence и telemetry. |
| Runtime boundary | адаптер проекта | Доставляет уже одобренный brief; scope и state не меняет. |

Цепочка поставки: `capability → skills → project snapshot → .harness/project.json → runtime`.
`harness init`, `adopt` и `update` разрешают capability по каталогу, копируют пакеты и фиксируют
lock. Claude Code и Codex находят один и тот же snapshot через свои native skill roots, а
`REGISTRY.md` остаётся индексом установленного набора. После установки целевой проект работает
сам: исходный клон harness ему не нужен.

## Discovery Pipeline

Контекст переходит между сессиями через проверяемые артефакты, а не через пересказ в чате:

1. `/grilling` предлагает пути-кандидаты и записывает в артефакт только явно одобренные файлы.
2. `/to-spec` переносит этот список в эпик, в раздел `## Relevant Files (Discovery Context)`.
3. `/to-tickets` распределяет пути по тикетам и строит Path inventory.
4. Context builder читает закреплённый коммит и собирает в неизменяемый Context Package точный
   diff, стартовые файлы, связанные тесты, ADR и precedent cards.
5. Coordinator регистрирует пакет в ledger и перед новым dispatch проверяет, свежий ли он.

## Backend orchestration

`backend-orchestration` подключается по желанию поверх `engineering-suite`. Coordinator владеет
batch, approval каждого handoff, изменениями scope, QA lane и приёмом отчётов. Роль получает
неизменяемый brief, подтверждает модель через self-report и шлёт heartbeat. Расширить scope,
выбрать модель или смержить PR роль не может.

Обычный `/implement` проходит `architect → developer → code-review → qa → publish`. Review и QA
работают с закреплённым candidate SHA, а PR открывается отдельным ручным шагом.

## Дальше

- [Rust runtime](runtime.md)
- [Быстрый старт](../getting-started/index.md)
- [Справочник](../reference/index.md)
