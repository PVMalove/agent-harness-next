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
    <p class="ah-lead">Rust runtime, транзакционный runtime-store, инкрементальные проверки,
      Release Gate и веб-консоль. Python остаётся policy-слоем, исполнение — за нативным runtime.</p>
    <div class="ah-actions">
      <a class="md-button md-button--primary" href="getting-started/index.html">Начать</a>
      <a class="md-button" href="architecture/index.html">Архитектура</a>
      <a class="md-button" href="demo/index.html">Демо</a>
    </div>
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
    <span class="i">▣</span>
    <b>Веб-консоль</b>
    <span>TUI и браузер — клиенты одного Сервера консоли: задачи, оркестрация, отчёты
      и восстановление.</span>
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
</div>
