---
title: Agent Harness Next
description: Портативный harness для coding-агентов.
hide:
  - navigation
  - toc
---

<div class="ah-hero">
  <div class="ah-hero-head">
    <span class="ah-eyebrow"><i></i> Agent Harness Next · beta</span>
    <h1>Harness для coding-агентов</h1>
  </div>
  <div class="ah-hero-copy">
    <p class="ah-lead">Agent Harness Next разворачивает в проект скиллы, hooks и контекстные
      документы и ведёт оркестрацию через Rust runtime и локальный runtime-store, оставляя Python
      policy-слоем.</p>
    <div class="ah-actions">
      <a class="md-button md-button--primary" href="getting-started/index.html">Начать</a>
      <a class="md-button" href="architecture/index.html">Архитектура</a>
      <a class="md-button" href="demo/index.html">Демо</a>
    </div>

    <div class="ah-install" id="ah-install">
      <div class="ah-install-head">
        <span class="ah-install-label">Установка</span>
        <button class="ah-copy" type="button" aria-label="Скопировать команду установки">
          <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><rect x="9" y="9" width="11" height="11" rx="2"></rect><path d="M5 15V5a2 2 0 0 1 2-2h10"></path></svg>
          <span class="ah-copy-label">Copy</span>
        </button>
      </div>
      <div class="ah-install-lines" id="ah-install-lines">
        <div class="ah-install-line"><span class="ah-prompt">$</span><code id="ah-install-global">python3 bin/install-global.py --target-home "$HOME" --runtime claude --runtime codex</code></div>
        <div class="ah-install-line"><span class="ah-prompt">$</span><code id="ah-install-capability">python3 harness/bin/harness.py init . --capability engineering-suite</code></div>
      </div>
    </div>

    <p class="ah-install-note">
      <span>Требуются</span>
      <span class="ah-req"><svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="m8 9-3 3 3 3M16 9l3 3-3 3M13 6l-2 12"></path></svg> Python 3.12+</span>
      <span class="ah-req" title="rust-version 1.89 в native/harness-runtime/Cargo.toml"><svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><circle cx="12" cy="12" r="3.2"></circle><path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3M5.3 5.3l2.1 2.1M16.6 16.6l2.1 2.1M18.7 5.3l-2.1 2.1M7.4 16.6l-2.1 2.1"></path></svg> Rust 1.89+</span>
      <span class="ah-req"><svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><circle cx="6" cy="6" r="2.2"></circle><circle cx="18" cy="6" r="2.2"></circle><circle cx="12" cy="18" r="2.2"></circle><path d="M8 7.5 11 16M16 7.5 13 16"></path></svg> Git</span>
      <span>Подробнее — в <a href="getting-started/index.html">быстром старте</a>.</span>
    </p>
  </div>

  <div class="ah-art">
    <div class="ah-terminal-wrap">
      <div class="ah-mascot ah-mascot--perch">
        <img src="assets/mascot.svg" alt="Воксельный маскот Agent Harness Next" width="108" height="140">
        <div class="ah-bubble" id="ah-hero-bubble"><b>Привет, я H›.</b> Запускаю <code>harness health</code>.</div>
      </div>
      <div class="ah-terminal" id="ah-hero-terminal">
        <div class="ah-terminal-bar">
          <span class="ah-terminal-dots"><i></i><i></i><i></i></span>
          <span class="ah-terminal-title">harness · runtime-store</span>
          <span class="ah-terminal-beta">beta</span>
          <button class="ah-terminal-play" id="ah-terminal-play" type="button" aria-label="Запустить демонстрацию">
            <svg class="ah-play-icon" viewBox="0 0 24 24" width="11" height="11" fill="currentColor" aria-hidden="true"><path d="M8 5v14l11-7z"></path></svg>
            <svg class="ah-stop-icon" viewBox="0 0 24 24" width="11" height="11" fill="currentColor" aria-hidden="true"><rect x="6" y="6" width="12" height="12" rx="1"></rect></svg>
            <span class="ah-terminal-play-label">Демо</span>
          </button>
        </div>
        <pre class="ah-terminal-output" id="ah-terminal-output" aria-live="polite"><code><span class="ah-t-prompt">$</span> <span class="ah-t-cmd">harness health .</span>
<span class="ah-t-dim">Нажмите «Демо», чтобы запустить сценарий.</span><span class="ah-cursor"></span></code></pre>
      </div>
    </div>
  </div>
</div>

<div class="ah-specs">
  <div class="ah-spec">
    <span class="ah-spec-icon"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><circle cx="12" cy="12" r="3.2"></circle><path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3M5.3 5.3l2.1 2.1M16.6 16.6l2.1 2.1M18.7 5.3l-2.1 2.1M7.4 16.6l-2.1 2.1"></path></svg></span>
    <div><div class="k">Runtime</div><div class="v">Rust <em>std-потоки</em></div><div class="s">supervisor, OCI, reconcile</div></div>
  </div>
  <div class="ah-spec">
    <span class="ah-spec-icon"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><ellipse cx="12" cy="5.5" rx="7" ry="3"></ellipse><path d="M5 5.5v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6M5 11.5v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6"></path></svg></span>
    <div><div class="k">State</div><div class="v">SQLite <em>WAL</em></div><div class="s">schema 7 · audit chain</div></div>
  </div>
  <div class="ah-spec">
    <span class="ah-spec-icon"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2"></rect><path d="m8 10 2 2-2 2M13 14h4"></path></svg></span>
    <div><div class="k">Runtimes</div><div class="v"><em>Claude Code</em> · <em>Codex</em></div><div class="s">hooks и skills нативно</div></div>
  </div>
  <div class="ah-spec">
    <span class="ah-spec-icon"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><rect x="3" y="4" width="18" height="13" rx="2"></rect><path d="M8 21h8M12 17v4"></path></svg></span>
    <div><div class="k">Platforms</div><div class="v"><em>Linux</em> · <em>Windows</em></div><div class="s"><em>UDS</em> и <em>named pipe</em> · контейнеры только на Linux</div></div>
  </div>
</div>

<div class="ah-section">
  <span class="ah-kicker">Сборки (Capabilities)</span>
  <h2>Соберите harness под задачу</h2>
  <p>Capability задаёт состав скиллов и поведение агента. Сборки взаимоисключающие:
    <code>engineering-suite</code> расширяет <code>mattpocock-suite</code>,
    <code>backend-orchestration</code> — <code>engineering-suite</code>, а
    <code>project-foundation</code> выбирается отдельно. Выберите сборку — команда установки
    и демонстрация выше обновятся.</p>
</div>

<div class="ah-cap-grid" id="ah-cap-grid" role="radiogroup" aria-label="Сборка harness">
  <button class="ah-cap" type="button" role="radio" aria-checked="false" data-capability="project-foundation">
    <span class="ah-cap-icon"><svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><ellipse cx="12" cy="5.5" rx="7" ry="3"></ellipse><path d="M5 5.5v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6M5 11.5v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6"></path></svg></span>
    <span class="ah-cap-check" aria-hidden="true"><svg viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="currentColor" stroke-width="3" aria-hidden="true"><path d="m5 12 4.5 4.5L19 6.5"></path></svg></span>
    <span class="ah-cap-name">project-foundation</span>
    <span class="ah-cap-desc">Лёгкая доменно-нейтральная база из пяти ключевых скиллов. Вариант по умолчанию.</span>
  </button>
  <button class="ah-cap" type="button" role="radio" aria-checked="false" data-capability="mattpocock-suite">
    <span class="ah-cap-icon"><svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><path d="m12 3 8 4.5-8 4.5-8-4.5L12 3Z"></path><path d="m4 12 8 4.5 8-4.5M4 16.5 12 21l8-4.5"></path></svg></span>
    <span class="ah-cap-check" aria-hidden="true"><svg viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="currentColor" stroke-width="3" aria-hidden="true"><path d="m5 12 4.5 4.5L19 6.5"></path></svg></span>
    <span class="ah-cap-name">mattpocock-suite</span>
    <span class="ah-cap-desc">Полный upstream-набор, закреплённый на проверенном коммите.</span>
  </button>
  <button class="ah-cap" type="button" role="radio" aria-checked="false" data-capability="engineering-suite">
    <span class="ah-cap-icon"><svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><path d="m14.5 6.5 3-3 3 3-3 3"></path><path d="m4 20 7.2-7.2M9.5 4.5l10 10-2.5 2.5-10-10z"></path></svg></span>
    <span class="ah-cap-check" aria-hidden="true"><svg viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="currentColor" stroke-width="3" aria-hidden="true"><path d="m5 12 4.5 4.5L19 6.5"></path></svg></span>
    <span class="ah-cap-name">engineering-suite</span>
    <span class="ah-cap-desc">Эпики и тикеты, триаж, двухосевое review, <code>qa-gate</code> и подготовка PR.</span>
  </button>
  <button class="ah-cap" type="button" role="radio" aria-checked="false" data-capability="backend-orchestration">
    <span class="ah-cap-icon"><svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><circle cx="6" cy="6" r="2.4"></circle><circle cx="18" cy="6" r="2.4"></circle><circle cx="12" cy="18" r="2.4"></circle><path d="M8.2 6h7.6M7.2 8.1l3.5 7.6M16.8 8.1l-3.5 7.6"></path></svg></span>
    <span class="ah-cap-check" aria-hidden="true"><svg viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="currentColor" stroke-width="3" aria-hidden="true"><path d="m5 12 4.5 4.5L19 6.5"></path></svg></span>
    <span class="ah-cap-name">backend-orchestration</span>
    <span class="ah-cap-desc">Роли и coordinator для распределённых систем: briefs, worktrees и ledger.</span>
  </button>
</div>

<p class="ah-note"><a href="getting-started/index.html">Как выбрать сборку и подключить её к проекту</a></p>

<div class="ah-section">
  <span class="ah-kicker">Возможности</span>
  <h2>Policy и исполнение разделены</h2>
  <p>Python принимает решения, Rust runtime хранит состояние и запускает процессы.
    Проверки выполняются по плану, а не всем набором.</p>
</div>

<div class="ah-feature-grid">
  <button class="ah-feature" type="button" data-feature="runtime" aria-haspopup="dialog">
    <span class="ah-feature-icon"><svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><rect x="4" y="4" width="16" height="16" rx="3"></rect><path d="M8 9h8M8 13h5M8 17h7"></path></svg></span>
    <b>Rust runtime и store</b>
    <span>Единственный writer operational state: SQLite WAL, lease с fencing, audit-цепочка
      и идемпотентные IPC-операции.</span>
    <span class="ah-feature-more">Быстрый просмотр →</span>
  </button>
  <button class="ah-feature" type="button" data-feature="verification" aria-haspopup="dialog">
    <span class="ah-feature-icon"><svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><path d="M5 12l4 4L19 6"></path><path d="M5 20h14"></path></svg></span>
    <b>Инкрементальные проверки</b>
    <span>ChangeImpact и VerificationPlan запускают только затронутые тесты; QA — полный
      clean-room на финальном SHA.</span>
    <span class="ah-feature-more">Быстрый просмотр →</span>
  </button>
  <button class="ah-feature" type="button" data-feature="gate" aria-haspopup="dialog">
    <span class="ah-feature-icon"><svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><path d="M12 3l8 4v5c0 5-3.4 8-8 9-4.6-1-8-4-8-9V7l8-4Z"></path><path d="m8.5 12 2.3 2.3L15.8 9"></path></svg></span>
    <b>Release Gate</b>
    <span>Публикация начинается только после полного прогона на финальном SHA и подтверждения
      человеком.</span>
    <span class="ah-feature-more">Быстрый просмотр →</span>
  </button>
  <button class="ah-feature" type="button" data-feature="hooks" aria-haspopup="dialog">
    <span class="ah-feature-icon"><svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><path d="M4 7h10M18 7h2M4 12h3M11 12h9M4 17h10M18 17h2"></path><circle cx="16" cy="7" r="2"></circle><circle cx="9" cy="12" r="2"></circle><circle cx="16" cy="17" r="2"></circle></svg></span>
    <b>Профили hooks</b>
    <span>Политика предупреждений и повторов без ослабления guard-ов на границах риска.</span>
    <span class="ah-feature-more">Быстрый просмотр →</span>
  </button>
  <button class="ah-feature" type="button" data-feature="console" aria-haspopup="dialog">
    <span class="ah-feature-icon"><svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><rect x="3" y="4" width="18" height="14" rx="2"></rect><path d="M8 21h8M12 18v3"></path></svg></span>
    <b>Веб-консоль</b>
    <span>TUI и браузер — клиенты одного Сервера консоли: задачи, оркестрация, отчёты
      и восстановление.</span>
    <span class="ah-feature-more">Быстрый просмотр →</span>
  </button>
  <button class="ah-feature" type="button" data-feature="security" aria-haspopup="dialog">
    <span class="ah-feature-icon"><svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><path d="M12 3l8 4v5c0 5-3.4 8-8 9-4.6-1-8-4-8-9V7l8-4Z"></path><path d="M9 12h6M12 9v6"></path></svg></span>
    <b>Безопасность и контейнеры</b>
    <span>Изоляция исполнителя, allowlist egress и сохранение native approval.</span>
    <span class="ah-feature-more">Быстрый просмотр →</span>
  </button>
</div>

<div class="ah-section">
  <span class="ah-kicker">Архитектура</span>
  <h2>Слои и границы</h2>
  <p>Python решает policy, Rust исполняет и хранит.</p>
</div>

<div class="ah-flow" id="ah-flow">
  <p class="ah-core-hint">Выберите клиента: запрос пройдёт по слоям до runtime-store. Узлы кликабельны.</p>
  <div class="ah-core-scroll"><div class="ah-core" id="ah-core"></div></div>
  <div class="ah-flow-note" id="ah-flow-note" aria-live="polite">
    <b>Web console · маршрут</b>
    <span>Выберите клиента или узел схемы.</span>
  </div>
  <div class="ah-flow-principles">
    <div class="ah-principle"><span class="tag">01</span><b>Один writer.</b> Python не пишет operational state в обход runtime.</div>
    <div class="ah-principle"><span class="tag">02</span><b>Идемпотентность.</b> Повтор после потерянного ответа возвращает тот же результат.</div>
    <div class="ah-principle"><span class="tag">03</span><b>Audit.</b> Хэш-цепочка и <code>ledger validate --full</code> находят удаление, вставку и перестановку.</div>
    <div class="ah-principle"><span class="tag">04</span><b>Recovery.</b> После SIGKILL runtime находит исполнение по меткам и завершает остановку.</div>
  </div>
</div>

<div class="ah-section">
  <span class="ah-kicker">Документация</span>
  <h2>Начало работы</h2>
  <p>Установите глобальный слой, подключите harness к проекту и проверьте окружение.</p>
</div>

<div class="ah-cards ah-cards--four">
  <a class="ah-card" href="getting-started/index.html">
    <span class="i"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><path d="M5 19 19 5M9 5h10v10"></path><path d="M5 5h5v5H5z"></path></svg></span>
    <b>Быстрый старт</b>
    <span>Требования, установка, init/adopt и health.</span>
  </a>
  <a class="ah-card" href="architecture/index.html">
    <span class="i"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><path d="m12 3 8 4.5-8 4.5-8-4.5L12 3Z"></path><path d="m4 12 8 4.5 8-4.5M4 16.5 12 21l8-4.5"></path></svg></span>
    <b>Архитектура</b>
    <span>Слои, ownership, runtime, store и безопасность.</span>
  </a>
  <a class="ah-card" href="reference/index.html">
    <span class="i"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v18H6.5A2.5 2.5 0 0 1 4 18.5v-13Z"></path><path d="M4 17.5h16"></path></svg></span>
    <b>Справочник</b>
    <span>CLI, конфигурация, hooks и агенты.</span>
  </a>
  <a class="ah-card" href="demo/index.html">
    <span class="i"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><rect x="3" y="4" width="18" height="14" rx="2"></rect><path d="M8 21h8M12 18v3"></path></svg></span>
    <b>Демо</b>
    <span>Веб-консоль и демонстрационные сценарии.</span>
  </a>
</div>

<dialog class="ah-dialog" id="ah-feature-dialog">
  <div class="ah-dialog-head">
    <div><span class="ah-kicker">Возможности</span><h3 id="ah-dialog-title"></h3></div>
    <button class="ah-dialog-close" type="button" aria-label="Закрыть">×</button>
  </div>
  <p id="ah-dialog-desc"></p>
  <pre class="ah-dialog-code"><code id="ah-dialog-code"></code></pre>
  <div class="ah-dialog-foot"><a class="ah-dialog-link" id="ah-dialog-link" href="architecture/index.html">Открыть раздел →</a></div>
</dialog>

<script>
  (function () {
    const scenarios = {
      "project-foundation": {
        bubble: "<b>Лёгкая база.</b> Пять ключевых скиллов, без оркестрации — быстрый старт.",
        done: "<b>Готово.</b> project-foundation: минимальная база без batch и coordinator.",
        lines: [
          ['dim', '== Skills =='],
          ['ok', '✓ project-foundation: 5 ключевых скиллов'],
          ['ok', '✓ snapshot: managed files на месте'],
          ['info', 'ℹ orchestration: не выбран — coordinator не нужен'],
          ['dim', '== Итог =='],
          ['sum', '<span class="ah-t-ok">ok=12</span> <span class="ah-t-warn">warn=1</span> <span class="ah-t-fail">fail=0</span> <span class="ah-t-dim">skipped=2</span>']
        ]
      },
      "mattpocock-suite": {
        bubble: "<b>Upstream-набор.</b> Закреплённый snapshot и проверенный коммит — без лишних слоёв.",
        done: "<b>Готово.</b> mattpocock-suite: upstream-набор закреплён и проверен.",
        lines: [
          ['dim', '== Skills =='],
          ['ok', '✓ upstream: 25 skills pinned'],
          ['ok', '✓ snapshot: v1.2.3 · 6acc160'],
          ['info', 'ℹ orchestration: не выбран — coordinator не нужен'],
          ['dim', '== Итог =='],
          ['sum', '<span class="ah-t-ok">ok=18</span> <span class="ah-t-warn">warn=2</span> <span class="ah-t-fail">fail=0</span> <span class="ah-t-dim">skipped=3</span>']
        ]
      },
      "engineering-suite": {
        bubble: "<b>Инженерный workflow.</b> Смотрю ledger, dispatch и готовность runtime.",
        done: "<b>Готово.</b> engineering-suite: workflow, review и QA готовы к работе.",
        lines: [
          ['dim', '== Оркестрация =='],
          ['ok', '✓ ledger: authority=runtime-store schema_version=7'],
          ['ok', '✓ незавершённых batch нет'],
          ['ok', '✓ активные dispatch посылают heartbeat вовремя'],
          ['ok', '✓ engineering-suite: 32 skills'],
          ['ok', '✓ runtime-store: read-only · schema 7'],
          ['info', 'ℹ Rust runtime: protocol 1.7 · serving'],
          ['warn', '⚠ Repo Map: minimal (parser bundle отсутствует)'],
          ['dim', '== Итог =='],
          ['sum', '<span class="ah-t-ok">ok=40</span> <span class="ah-t-warn">warn=4</span> <span class="ah-t-fail">fail=0</span> <span class="ah-t-dim">skipped=11</span>']
        ]
      },
      "backend-orchestration": {
        bubble: "<b>Оркестрация.</b> Включаю роли, coordinator, ledger и QA lane.",
        done: "<b>Готово.</b> backend-orchestration: coordinator, роли и ledger подняты.",
        lines: [
          ['dim', '== Оркестрация =='],
          ['ok', '✓ ledger: authority=runtime-store schema_version=7'],
          ['ok', '✓ coordinator: 3 роли готовы'],
          ['ok', '✓ незавершённых batch нет'],
          ['ok', '✓ активные dispatch посылают heartbeat вовремя'],
          ['warn', '⚠ QA lane: ожидает evidence'],
          ['dim', '== Итог =='],
          ['sum', '<span class="ah-t-ok">ok=46</span> <span class="ah-t-warn">warn=3</span> <span class="ah-t-fail">fail=0</span> <span class="ah-t-dim">skipped=9</span>']
        ]
      }
    };

    const features = {
      runtime: {
        title: "Rust runtime и store",
        desc: "Единственный writer operational state: SQLite WAL, lease с fencing, audit-цепочка и идемпотентные IPC-операции.",
        code: "$ harness health .\n✓ ledger: authority=runtime-store schema_version=7\n✓ audit chain: 306 records · valid\nℹ runtime: protocol 1.7 · serving",
        href: "architecture/index.html"
      },
      verification: {
        title: "Инкрементальные проверки",
        desc: "ChangeImpact и VerificationPlan запускают только затронутые тесты; QA — полный clean-room на финальном SHA.",
        code: "ChangeImpact → VerificationPlan\nfocused: tests/orchestration/test_runtime_client.py\nfull:    make verify (clean-room, final SHA)",
        href: "getting-started/index.html"
      },
      gate: {
        title: "Release Gate",
        desc: "Публикация начинается только после полного прогона на финальном SHA и подтверждения человеком.",
        code: "Release Gate\ncandidate: 6a7f748\ntarget:    master\ntree:      match\ndecision:  blocked · QA evidence missing",
        href: "architecture/index.html"
      },
      hooks: {
        title: "Профили hooks",
        desc: "Политика предупреждений и повторов без ослабления guard-ов на границах риска.",
        code: "// .harness/hook-policy.json\n{ \"profile\": \"standard\", \"policy_sha256\": \"…\" }",
        href: "reference/hooks/index.html"
      },
      console: {
        title: "Веб-консоль",
        desc: "TUI и браузер — клиенты одного Сервера консоли: задачи, оркестрация, отчёты и восстановление.",
        code: "$ harness console --web\nСервер консоли: http://127.0.0.1:…/?token=…\nЭкраны: Главная · Доска задач · Оркестрация · Отчёты",
        href: "demo/index.html"
      },
      security: {
        title: "Безопасность и контейнеры",
        desc: "Изоляция исполнителя, allowlist egress и сохранение native approval.",
        code: "supervisor: outside sandbox\nsockets:    mount denied\negress:     allowlist\nrootless:   Podman · SELinux",
        href: "architecture/index.html"
      }
    };

    const capCards = Array.from(document.querySelectorAll("[data-capability]"));
    const installCapability = document.getElementById("ah-install-capability");
    const bubble = document.getElementById("ah-hero-bubble");
    const output = document.querySelector("#ah-terminal-output code");
    const terminal = document.getElementById("ah-terminal-output");
    const play = document.getElementById("ah-terminal-play");
    const playLabel = play.querySelector(".ah-terminal-play-label");
    let selected = "engineering-suite";
    let timers = [];
    let running = false;

    function setRunning(value) {
      running = value;
      play.classList.toggle("is-running", value);
      playLabel.textContent = value ? "Стоп" : "Демо";
      play.setAttribute("aria-label", value ? "Остановить демонстрацию" : "Запустить демонстрацию");
    }

    function clearTimers() {
      timers.forEach((id) => window.clearTimeout(id));
      timers = [];
    }

    function append(html) {
      const line = document.createElement("span");
      line.className = "ah-terminal-line";
      line.innerHTML = html;
      output.appendChild(line);
      terminal.scrollTop = terminal.scrollHeight;
    }

    function runScenario(name) {
      const scenario = scenarios[name];
      if (!scenario) return;
      clearTimers();
      setRunning(true);
      output.innerHTML = '<span class="ah-t-prompt">$</span> <span class="ah-t-cmd">harness health .</span><span class="ah-cursor"></span>';
      bubble.innerHTML = scenario.bubble;
      let index = 0;

      function next() {
        if (index >= scenario.lines.length) {
          const cursor = output.querySelector(".ah-cursor");
          if (cursor) cursor.remove();
          setRunning(false);
          bubble.innerHTML = scenario.done;
          return;
        }
        const [kind, text] = scenario.lines[index++];
        if (kind === "sum") {
          append(text);
        } else if (kind === "dim") {
          append('<span class="ah-t-dim">' + text + '</span>');
        } else {
          append('<span class="ah-t-' + kind + '">' + text.slice(0, 1) + '</span>' + text.slice(1));
        }
        timers.push(window.setTimeout(next, 170));
      }

      timers.push(window.setTimeout(next, 380));
    }

    function selectCapability(name, run) {
      selected = name;
      capCards.forEach((card) => {
        const active = card.dataset.capability === name;
        card.classList.toggle("is-active", active);
        card.setAttribute("aria-checked", active ? "true" : "false");
      });
      installCapability.textContent = "python3 harness/bin/harness.py init . --capability " + name;
      if (run) runScenario(name);
    }

    capCards.forEach((card) => {
      card.addEventListener("click", () => selectCapability(card.dataset.capability, true));
    });

    play.addEventListener("click", () => {
      if (running) {
        clearTimers();
        setRunning(false);
        const cursor = output.querySelector(".ah-cursor");
        if (cursor) cursor.remove();
        bubble.innerHTML = "<b>Пауза.</b> Нажмите «Демо», чтобы запустить сценарий снова.";
        return;
      }
      runScenario(selected);
    });

    const copy = document.querySelector(".ah-copy");
    copy.addEventListener("click", () => {
      const command = document.getElementById("ah-install-global").textContent.trim() + "\n" +
        document.getElementById("ah-install-capability").textContent.trim();
      navigator.clipboard.writeText(command).then(() => {
        copy.classList.add("is-copied");
        copy.querySelector(".ah-copy-label").textContent = "Copied!";
        window.setTimeout(() => {
          copy.classList.remove("is-copied");
          copy.querySelector(".ah-copy-label").textContent = "Copy";
        }, 1400);
      });
    });

    const dialog = document.getElementById("ah-feature-dialog");
    const dialogTitle = document.getElementById("ah-dialog-title");
    const dialogDesc = document.getElementById("ah-dialog-desc");
    const dialogCode = document.getElementById("ah-dialog-code");
    const dialogLink = document.getElementById("ah-dialog-link");
    document.querySelectorAll("[data-feature]").forEach((card) => {
      card.addEventListener("click", () => {
        const feature = features[card.dataset.feature];
        if (!feature) return;
        dialogTitle.textContent = feature.title;
        dialogDesc.textContent = feature.desc;
        dialogCode.textContent = feature.code;
        dialogLink.href = feature.href;
        dialog.showModal();
      });
    });
    dialog.querySelector(".ah-dialog-close").addEventListener("click", () => dialog.close());
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog) dialog.close();
    });

    selectCapability(selected, false);
    timers.push(window.setTimeout(() => runScenario(selected), 1100));
  })();
</script>
