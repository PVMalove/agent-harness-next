# Обзор архитектуры

Policy и исполнение разделены: Python принимает решения и ведёт approvals, Rust runtime хранит
operational state и запускает процессы, а Git остаётся владельцем истории и кандидатов.

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

Python — policy-слой: coordinator планирует batch, собирает approvals и принимает отчёты ролей.
Rust runtime — доверенный супервизор хоста: он исполняет только уже одобренный brief, проверяет
digest-ы плана и образа и не решает policy сам. Каждый handoff получает отдельное подтверждение,
поэтому роль не может расширить свой scope по ходу работы.

Operational state живёт в runtime-store, а не в файлах, которые правит Python. Это главное правило:
у каждой сущности ровно один writer, и переходы между состояниями сохраняются транзакцией, а не
дописыванием файла.

Git остаётся владельцем истории: кандидат, ветки и worktree — обычные Git-объекты, runtime их не
переписывает. Проектные контракты — `.harness/project.json`, `harness.lock` и `REGISTRY.md` —
принадлежат целевому репозиторию: их обновляет установщик harness, а не runtime.

## Кто владеет чем

| Сущность | Writer | Что это значит |
| --- | --- | --- |
| Lifecycle batch/dispatch | Rust runtime | Переходы сохраняются транзакцией; Python не пишет в store напрямую. |
| Approvals и policy | Python | Решение принимает человек и policy-слой; runtime исполняет сохранённое решение. |
| Операционный intent | Rust store | Idempotency key, attempt и reconcile живут в одной транзакции. |
| Git-история и candidate | Git | Кандидат, ветки и worktree — обычные Git-объекты; runtime их не переписывает. |
| Audit | Rust store | Хэш-цепочка с checkpoint для инкрементальной проверки. |

!!! note "Fallback-writer запрещён"

    Если runtime недоступен, Python не начинает писать в файловый ledger «чтобы продолжить».
    Операция возвращает типизированную ошибку с remedy.

## Границы доверия

Граница проходит между Python policy, Rust runtime и untrusted worker: runtime — доверенный
супервизор хоста, worker — кандидат в контейнере или отдельном процессе.

| Граница | Правило |
| --- | --- |
| Runtime socket | Только peer uid/SID и capability-токен; каталог `0700`, сокет `0600`. |
| Engine socket | Никогда не монтируется в worker или QA-контейнер. |
| Approval | Immutable brief связывает план, образ, policy digest и verification digest. |
| Secrets | Не попадают в командную строку, логи, audit и отчёты. |

Подробности — в разделе [Безопасность](runtime.md) и в ADR 0021.

## Слои и модель поставки

| Слой | Источник истины | Ответственность |
| --- | --- | --- |
| Capability catalog | `harness/CAPABILITIES.json` | Разрешает состав snapshot и зависимости между сборками. |
| Skill packages | `skills/vendor/`, `skills/first-party/` | Инструкции, переводы и overrides; vendor-снимок вручную не правится. |
| Project snapshot | `.harness/skills/`, `harness.lock`, `REGISTRY.md` | Независимая поставка в целевой репозиторий, drift и provenance. |
| Project contract | `.harness/project.json` | Язык, base branch, шаблон ветки и команды проверок. |
| Orchestration core | coordinator и ledger | Policy, approvals, lifecycle batch, audit и dispatch ролей. |
| Evidence execution | gate runner и evidence | Проверки, санитизированное evidence и telemetry. |
| Runtime boundary | адаптер проекта | Доставляет уже approved brief; scope и state не меняет. |

Цепочка поставки: `capability → skills → project snapshot → .harness/project.json → runtime`.
`harness init`, `adopt` и `update` разрешают capability из каталога, копируют пакеты и фиксируют lock.
Claude Code и Codex находят один и тот же snapshot через свои native skill roots, а `REGISTRY.md`
остаётся индексом установленного набора. После установки целевой проект живёт автономно: исходный
клон harness во время работы не нужен.

## Discovery Pipeline

Контекст передаётся между сессиями через проверяемые артефакты, а не через пересказ в чате:

1. `/grilling` предлагает кандидатные пути и записывает в артефакт только явно одобренные файлы.
2. `/to-spec` сохраняет этот список в эпике, в разделе `Relevant Files`.
3. `/to-tickets` назначает пути тикетам и строит Path inventory.
4. Context builder читает pinned commit, собирает exact diff, стартовые файлы, связанные тесты,
   ADR и precedent cards в immutable Context Package.
5. Coordinator регистрирует пакет в ledger и перед новым dispatch проверяет его freshness.

## Backend orchestration

`backend-orchestration` — opt-in capability поверх `engineering-suite`. Coordinator владеет batch,
approval каждого handoff, изменениями scope, QA lane и принятием reports. Роль получает immutable
brief, подтверждает model self-report и передаёт heartbeat; расширить scope, выбрать модель или
смержить PR она не может.

Обычный `/implement` проходит `architect → developer → code-review → qa → publish`. Review и QA
работают с pinned candidate SHA, а PR остаётся отдельным ручным шагом.

## Дальше

- [Rust runtime](runtime.md)
- [Быстрый старт](../getting-started/index.md)
- [Справочник](../reference/index.md)
