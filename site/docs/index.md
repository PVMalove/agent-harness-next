---
title: Agent Harness Next
description: Портативный harness для Claude Code и Codex.
hide:
  - navigation
  - toc
---

<div class="ah-hero">
  <div>
    <span class="ah-eyebrow">Agent Harness Next · beta</span>
    <h1>Harness для Claude Code и Codex</h1>
    <p class="ah-lead">Agent Harness Next разворачивает в проект скиллы, hooks и контекстные
      документы и ведёт оркестрацию через Rust runtime и локальный runtime-store, оставляя Python
      policy-слоем.</p>
    <div class="ah-actions">
      <a class="md-button md-button--primary" href="getting-started/index.html">Начать</a>
      <a class="md-button" href="architecture/index.html">Архитектура</a>
      <a class="md-button" href="demo/index.html">Демо</a>
    </div>
    <div class="ah-install">
      <span class="ah-install-label">Установка</span>
      <code>python3 bin/install-global.py --target-home "$HOME" --runtime claude --runtime codex</code>
    </div>
    <p class="ah-install-note">Требуются Python 3.12+ и Git. Подробнее — в
      <a href="getting-started/index.html">быстром старте</a>.</p>
  </div>
  <div class="ah-art">
    <div class="ah-mascot">
      <img src="assets/mascot.svg" alt="Воксельный маскот Agent Harness Next">
      <div class="ah-bubble"><b>Привет, я H›.</b> Коротко о том, как устроен harness.</div>
    </div>
    <div class="ah-terminal">
      <div class="ah-terminal-bar"><i></i><i></i><i></i><span>harness · runtime-store</span><span style="margin-left:auto">beta</span></div>
<pre><code>$ harness health .
== Оркестрация ==
✓ ledger: authority=runtime-store schema_version=4
✓ незавершённых batch нет
✓ активные dispatch посылают heartbeat вовремя
ℹ Rust runtime: protocol 1.6 · serving
⚠ Repo Map: minimal (parser bundle отсутствует)
== Итог ==
ok=40 warn=4 fail=1 skipped=11</code></pre>
    </div>
    <div class="ah-note">Демонстрационный вывод; реальные цифры зависят от проекта.</div>
  </div>
</div>

<div class="ah-status">
  <div><div class="k">Runtime</div><div class="v">Rust + Tokio</div><div class="s">supervisor, OCI, reconcile</div></div>
  <div><div class="k">State</div><div class="v">SQLite WAL</div><div class="s">schema 4 · audit chain</div></div>
  <div><div class="k">Runtimes</div><div class="v">Claude Code · Codex</div><div class="s">hooks и skills нативно</div></div>
  <div><div class="k">Platforms</div><div class="v">Linux · Windows</div><div class="s">UDS и named pipe</div></div>
</div>

<div class="ah-section">
  <span class="ah-kicker">Сборки (Capabilities)</span>
  <h2>Соберите harness под задачу</h2>
  <p>Capability задаёт состав скиллов и поведение агента. Сборки взаимоисключающие:
    <code>engineering-suite</code> расширяет <code>mattpocock-suite</code>,
    <code>backend-orchestration</code> — <code>engineering-suite</code>, а
    <code>project-foundation</code> выбирается отдельно.</p>
</div>

<div class="ah-cards ah-cards--four">
  <div class="ah-card">
    <span class="i">◇</span>
    <b>project-foundation</b>
    <span>Лёгкая доменно-нейтральная база из пяти ключевых скиллов. Вариант по умолчанию.</span>
  </div>
  <div class="ah-card">
    <span class="i">⌁</span>
    <b>mattpocock-suite</b>
    <span>Полный upstream-набор, закреплённый на проверенном коммите.</span>
  </div>
  <div class="ah-card">
    <span class="i">✓</span>
    <b>engineering-suite</b>
    <span>Эпики и тикеты, триаж, двухосевое review, <code>qa-gate</code> и подготовка PR.</span>
  </div>
  <div class="ah-card">
    <span class="i">▣</span>
    <b>backend-orchestration</b>
    <span>Роли и coordinator для распределённых систем: briefs, worktrees и ledger.</span>
  </div>
</div>

<p class="ah-note"><a href="getting-started/index.html">Как выбрать сборку и подключить её к проекту</a></p>

<div class="ah-section">
  <span class="ah-kicker">Возможности</span>
  <h2>Policy и исполнение разделены</h2>
  <p>Python принимает решения, Rust runtime хранит состояние и запускает процессы.
    Проверки выполняются по плану, а не всем набором.</p>
</div>

<div class="ah-cards">
  <a class="ah-card" href="architecture/index.html">
    <span class="i">◇</span>
    <b>Rust runtime и store</b>
    <span>Единственный writer operational state: SQLite WAL, lease с fencing, audit-цепочка
      и идемпотентные IPC-операции.</span>
  </a>
  <a class="ah-card" href="getting-started/index.html">
    <span class="i">✓</span>
    <b>Инкрементальные проверки</b>
    <span>ChangeImpact и VerificationPlan запускают только затронутые тесты; QA — полный
      clean-room на финальном SHA.</span>
  </a>
  <a class="ah-card" href="architecture/index.html">
    <span class="i">◆</span>
    <b>Release Gate</b>
    <span>Публикация начинается только после полного прогона на финальном SHA и подтверждения
      человеком.</span>
  </a>
  <a class="ah-card" href="reference/index.html#hooks">
    <span class="i">⌘</span>
    <b>Профили hooks</b>
    <span>Политика предупреждений и повторов без ослабления guard-ов на границах риска.</span>
  </a>
  <a class="ah-card" href="demo/index.html">
    <span class="i">▣</span>
    <b>Веб-консоль</b>
    <span>TUI и браузер — клиенты одного Сервера консоли: задачи, оркестрация, отчёты
      и восстановление.</span>
  </a>
  <a class="ah-card" href="architecture/index.html">
    <span class="i">⬡</span>
    <b>Безопасность и контейнеры</b>
    <span>Изоляция исполнителя, allowlist egress и сохранение native approval.</span>
  </a>
</div>

<div class="ah-section">
  <span class="ah-kicker">Архитектура</span>
  <h2>Слои и границы</h2>
  <p>Python решает policy, Rust исполняет и хранит. Один writer на состояние,
    один протокол IPC, один аудит.</p>
</div>

<div class="ah-arch">
  <div class="panel">
    <div class="layer"><div class="tag">Clients</div><div class="nodes"><span class="node">CLI</span><span class="node">TUI</span><span class="node primary">Web console</span><span class="node">Skills</span></div></div>
    <div class="layer"><div class="tag">Policy</div><div class="nodes"><span class="node primary">Lifecycle</span><span class="node primary">Approvals</span><span class="node primary">Hook policy</span><span class="node primary">Verification</span></div></div>
    <div class="layer"><div class="tag">Runtime</div><div class="nodes"><span class="node ok">harness-runtime</span><span class="node ok">Supervisor</span><span class="node ok">OCI engine</span><span class="node ok">Reconcile</span></div></div>
    <div class="layer"><div class="tag">State</div><div class="nodes"><span class="node">SQLite WAL</span><span class="node">Audit chain</span><span class="node">Leases</span><span class="node">AUTHORITY</span></div></div>
  </div>
  <div class="panel">
    <div class="layer"><div class="tag">01</div><div><b>Один writer.</b> Python не пишет operational state в обход runtime.</div></div>
    <div class="layer"><div class="tag">02</div><div><b>Идемпотентность.</b> Повтор после потерянного ответа возвращает тот же результат.</div></div>
    <div class="layer"><div class="tag">03</div><div><b>Audit.</b> Хэш-цепочка и <code>ledger validate --full</code> находят удаление, вставку и перестановку.</div></div>
    <div class="layer"><div class="tag">04</div><div><b>Recovery.</b> После SIGKILL runtime находит исполнение по меткам и завершает остановку.</div></div>
  </div>
</div>

<div class="ah-section">
  <span class="ah-kicker">Демо</span>
  <h2>Веб-консоль целиком</h2>
  <p>Задачи, оркестрация, отчёты и восстановление в одном интерфейсе. Ниже — интерактивный
    макет на демонстрационных данных.</p>
</div>

<iframe class="ah-demo" src="demo/console.html" title="Демонстрация веб-консоли" loading="lazy"></iframe>

<p class="ah-note">Данные демонстрационные, команды не выполняются.
  <a href="demo/index.html">Открыть демо отдельно</a>.</p>

<div class="ah-section">
  <span class="ah-kicker">Документация</span>
  <h2>Начало работы</h2>
  <p>Установите глобальный слой, подключите harness к проекту и проверьте окружение.</p>
</div>

<div class="ah-cards">
  <a class="ah-card" href="getting-started/index.html">
    <span class="i">→</span>
    <b>Быстрый старт</b>
    <span>Требования, установка, init/adopt и health.</span>
  </a>
  <a class="ah-card" href="architecture/index.html">
    <span class="i">◇</span>
    <b>Архитектура</b>
    <span>Слои, ownership, runtime, store и безопасность.</span>
  </a>
  <a class="ah-card" href="reference/index.html">
    <span class="i">≡</span>
    <b>Справочник</b>
    <span>CLI, конфигурация, hooks и агенты.</span>
  </a>
  <a class="ah-card" href="demo/index.html">
    <span class="i">▣</span>
    <b>Демо</b>
    <span>Веб-консоль и демонстрационные сценарии.</span>
  </a>
</div>
