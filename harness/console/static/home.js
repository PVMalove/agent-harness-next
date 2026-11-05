/* Home is a request/response client of ConsoleServer; it owns no project facts. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const home = $('home');
  const unavailable = home.dataset.unavailable;
  const labels = JSON.parse(home.dataset.labels);
  const label = (key, values = {}) => Object.entries(values).reduce((text, [name, value]) => text.replace(`{${name}}`, String(value)), labels[key]);
  const text = (id, value) => { $(id).textContent = value ?? unavailable; };
  const number = value => Number.isSafeInteger(value) && value >= 0;
  const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
  const nullable = (value, check) => value === null || check(value);
  const string = value => typeof value === 'string';
  const fields = (value, schema) => object(value) && Object.entries(schema).every(([key, check]) => check(value[key]));
  const validSnapshot = snapshot => fields(snapshot, {
    version: value => value === 1,
    health: value => fields(value, {ok: number, warn: number, fail: number, skipped: number}),
    problems: value => Array.isArray(value) && value.every(problem => fields(problem, {status: string, id: string, message: string})),
    problems_total: number, harness_version: string, drift: string,
    active_batches: value => nullable(value, number),
    repo_map: value => fields(value, {tier: item => nullable(item, string), message: string,
      head_map: item => nullable(item, card => fields(card, {origin: string, commit: string, files: number, edges: number, estimated_tokens: number}))}),
    memory: value => fields(value, {
      state: item => nullable(item, state => fields(state, {status: string, message: string})),
      policy: item => nullable(item, policy => fields(policy, {
        enabled: flag => typeof flag === 'boolean', active: flag => typeof flag === 'boolean',
        source_types: list => Array.isArray(list) && list.every(string),
        indexed: count => nullable(count, number), top_k: count => nullable(count, number),
        max_tokens: count => nullable(count, number), problem: string, inactive: string,
      })),
    }),
  }) && snapshot.problems.length <= snapshot.problems_total;

  function problemList(id, problems) {
    const rows = problems.map(problem => {
      const row = document.createElement('div');
      row.className = 'check-row';
      const icon = document.createElement('span');
      icon.className = 'check-icon';
      if (['ok', 'warn', 'fail', 'skipped'].includes(problem.status)) icon.classList.add(problem.status);
      icon.textContent = problem.status;
      const main = document.createElement('span');
      main.className = 'check-main';
      const title = document.createElement('b');
      title.textContent = problem.id;
      const detail = document.createElement('small');
      detail.textContent = problem.message;
      main.append(title, detail);
      row.append(icon, main);
      return row;
    });
    if (!rows.length) {
      const empty = document.createElement('p');
      empty.className = 'muted';
      empty.textContent = labels.empty;
      rows.push(empty);
    }
    $(id).replaceChildren(...rows);
  }

  function render(snapshot, reply) {
    const health = snapshot.health;
    const total = health.ok + health.warn + health.fail + health.skipped;
    let x = 0;
    for (const key of ['ok', 'warn', 'fail', 'skipped']) {
      text(`health-${key}`, health[key]);
      const width = total ? health[key] / total * 100 : 0;
      $(`strip-${key}`).setAttribute('x', String(x));
      $(`strip-${key}`).setAttribute('width', String(width));
      x += width;
    }
    $('health-strip').setAttribute('aria-label', `${home.dataset.passed}: ${health.ok}; ${home.dataset.warning}: ${health.warn}; ${home.dataset.failed}: ${health.fail}; ${home.dataset.skipped}: ${health.skipped}`);
    text('home-facts', `${home.dataset.passed}: ${health.ok} · ${home.dataset.warning}: ${health.warn} · ${home.dataset.failed}: ${health.fail} · ${home.dataset.skipped}: ${health.skipped}`);
    text('home-checked', `${new Intl.DateTimeFormat(document.documentElement.lang, {timeStyle: 'medium'}).format(new Date())} · ${label('checks', {count: total})}`);
    text('problem-count', `${snapshot.problems.length} / ${snapshot.problems_total}`);
    text('problems-limit', label('problems', {shown: snapshot.problems.length, total: snapshot.problems_total}));
    problemList('attention-list', snapshot.problems);
    problemList('home-checks', snapshot.problems);
    text('harness-version', snapshot.harness_version);
    text('harness-drift', snapshot.drift);
    text('repo-map-tier', snapshot.repo_map.tier);
    const map = snapshot.repo_map.head_map;
    text('repo-map-head', map ? `${map.origin} · ${map.commit}` : labels.noMap);
    text('repo-map-detail', map ? `${snapshot.repo_map.message} · ${map.files} files · ${map.edges} edges · ≈${map.estimated_tokens} tokens` : snapshot.repo_map.message);
    const memory = snapshot.memory;
    text('memory-state', memory.state ? `${memory.state.status}: ${memory.state.message}` : null);
    const policy = memory.policy;
    text('memory-policy', policy ? `enabled=${policy.enabled} · active=${policy.active} · ${policy.source_types.join(', ')} · indexed=${policy.indexed ?? '—'} · top_k=${policy.top_k ?? '—'} · max_tokens=${policy.max_tokens ?? '—'} · ${policy.problem} ${policy.inactive}` : null);
    text('active-batches', snapshot.active_batches);
    text('health-mode-note', online ? labels.online : labels.offline);
    text('snapshot-status', `${reply.cached ? labels.cached : labels.fresh} · ${reply.age_seconds} s`);
  }

  let socket = null;
  let pending = null;
  let sequence = 0;
  let online = false;
  let refreshTimer = null;
  let requestTimer = null;
  let reconnectTimer = null;
  let generation = 0;
  let attempts = 0;
  let received = false;
  let stopped = false;
  function state(value) {
    document.body.dataset.connection = value;
    $('connection-state').className = `conn-chip ${value === 'unavailable' ? 'offline' : value}`;
    $('connection-state').querySelector('span').textContent = labels[value];
    $('connection-banner').hidden = value === 'connected';
    text('connection-message', value === 'unavailable' ? labels.serverUnavailable : labels.waiting);
    $('snapshot-stale').hidden = !received || value === 'connected';
    $('home-refresh').disabled = pending !== null || value !== 'connected';
  }
  function request(force = false) {
    if (!socket || socket.readyState !== WebSocket.OPEN || pending !== null) return;
    clearTimeout(refreshTimer);
    pending = `home-${++sequence}`;
    socket.send(JSON.stringify({id: pending, type: 'home.snapshot', force, online}));
    $('home-refresh').disabled = true;
    requestTimer = setTimeout(() => socket.close(), 30000);
  }
  function connect() {
    if (stopped) return;
    clearTimeout(reconnectTimer);
    clearTimeout(refreshTimer);
    clearTimeout(requestTimer);
    pending = null;
    const current = ++generation;
    const previous = socket;
    state(received && attempts < 5 ? 'reconnecting' : 'unavailable');
    const connection = new WebSocket(`ws://${location.host}/ws`);
    socket = connection;
    if (previous) previous.close();
    connection.onopen = () => { if (current === generation) { clearTimeout(requestTimer); request(); } };
    connection.onmessage = event => {
      if (current !== generation || stopped) return;
      let reply;
      try { reply = JSON.parse(event.data); } catch { socket.close(); return; }
      if (!object(reply) || reply.id !== pending) return;
      if (reply.v !== 1 || reply.type !== 'home.snapshot' || reply.ok !== true || typeof reply.cached !== 'boolean' || typeof reply.age_seconds !== 'number' || !Number.isFinite(reply.age_seconds) || reply.age_seconds < 0 || !validSnapshot(reply.snapshot)) {
        socket.close();
        return;
      }
      clearTimeout(requestTimer);
      pending = null;
      render(reply.snapshot, reply);
      received = true;
      attempts = 0;
      state('connected');
      if (!online) refreshTimer = setTimeout(() => request(), 15000);
    };
    connection.onclose = () => {
      if (current !== generation || stopped) return;
      clearTimeout(requestTimer);
      clearTimeout(refreshTimer);
      pending = null;
      attempts += 1;
      state(received && attempts < 5 ? 'reconnecting' : 'unavailable');
      clearTimeout(reconnectTimer);
      reconnectTimer = setTimeout(connect, Math.min(8000, 500 * 2 ** Math.min(attempts - 1, 4)));
    };
    connection.onerror = () => connection.close();
    requestTimer = setTimeout(() => connection.close(), 30000);
  }
  $('home-refresh').addEventListener('click', () => request(true));
  $('connection-retry').addEventListener('click', () => { attempts = 0; connect(); });
  document.querySelectorAll('[data-health-mode]').forEach(button => button.addEventListener('click', () => {
    if (pending !== null) return;
    online = button.dataset.healthMode === 'online';
    document.querySelectorAll('[data-health-mode]').forEach(item => {
      const selected = item === button;
      item.classList.toggle('on', selected);
      item.setAttribute('aria-pressed', String(selected));
    });
    request(true);
  }));

  const closeNav = () => {
    document.body.classList.remove('nav-open');
    $('menu-toggle').setAttribute('aria-expanded', 'false');
    $('nav-scrim').hidden = true;
  };
  $('menu-toggle').addEventListener('click', () => {
    const open = document.body.classList.toggle('nav-open');
    $('menu-toggle').setAttribute('aria-expanded', String(open));
    $('nav-scrim').hidden = !open;
  });
  $('nav-scrim').addEventListener('click', closeNav);
  function collapse(value) {
    document.body.classList.toggle('nav-collapsed', value);
    $('nav-collapse').setAttribute('aria-expanded', String(!value));
    $('nav-collapse').setAttribute('aria-label', value ? labels.expand : labels.collapse);
    try { localStorage.setItem('harness-nav-collapsed', value ? '1' : '0'); } catch { /* Storage is optional. */ }
  }
  $('nav-collapse').addEventListener('click', () => collapse(!document.body.classList.contains('nav-collapsed')));
  try { collapse(localStorage.getItem('harness-nav-collapsed') === '1'); } catch { /* Storage is optional. */ }
  function navigate() {
    const route = location.hash.slice(1) || 'home';
    const links = [...document.querySelectorAll('[data-nav-route]')];
    const selected = links.find(link => link.dataset.navRoute === route) || links[0];
    links.forEach(link => { if (link === selected) link.setAttribute('aria-current', 'page'); else link.removeAttribute('aria-current'); });
    const isHome = selected.dataset.navRoute === 'home';
    home.hidden = !isHome;
    $('section-unavailable').hidden = isHome;
    text('section-title', selected.title);
    closeNav();
  }
  window.addEventListener('hashchange', navigate);
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') closeNav();
    if (event.ctrlKey || event.metaKey || event.altKey || /INPUT|TEXTAREA|SELECT/.test(event.target.tagName)) return;
    const routes = {'g': 'home', 'd': 'diagnostics', 'o': 'orchestration', '?': 'help'};
    if (routes[event.key]) location.hash = routes[event.key];
  });
  window.addEventListener('pagehide', () => { stopped = true; generation += 1; clearTimeout(reconnectTimer); clearTimeout(requestTimer); clearTimeout(refreshTimer); if (socket) socket.close(); });
  navigate();
  connect();
})();
