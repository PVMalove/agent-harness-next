---
title: Agent Harness Next
description: A portable harness for coding agents.
hide:
  - navigation
  - toc
---

<div class="ah-hero">
  <div class="ah-hero-head">
    <span class="ah-eyebrow"><i></i> Agent Harness Next · beta</span>
    <h1>A harness for coding agents</h1>
  </div>
  <div class="ah-hero-copy">
    <p class="ah-lead">Agent Harness Next installs skills, hooks, and context documents into a project.
      It runs orchestration through a Rust runtime and a local runtime store, and keeps Python as the
      policy layer.</p>
    <div class="ah-actions">
      <a class="md-button md-button--primary" href="getting-started/index.html">Get started</a>
      <a class="md-button" href="architecture/index.html">Architecture</a>
      <a class="md-button" href="demo/index.html">Demo</a>
    </div>

    <div class="ah-quickstart" id="ah-quickstart">
      <div class="ah-steps" role="tablist" aria-label="Run order">
        <button class="ah-step is-active" type="button" role="tab" id="ah-tab-install" aria-selected="true" aria-controls="ah-panel-install" data-step="install" data-copy-label="Copy the install commands">
          <span class="ah-step-num">1</span><span class="ah-step-name">Install</span>
        </button>
        <span class="ah-step-arrow" aria-hidden="true">→</span>
        <button class="ah-step" type="button" role="tab" id="ah-tab-console" aria-selected="false" aria-controls="ah-panel-console" data-step="console" data-copy-label="Copy the web console command" tabindex="-1">
          <span class="ah-step-num">2</span><span class="ah-step-name">Web console</span>
        </button>
        <span class="ah-step-arrow" aria-hidden="true">→</span>
        <button class="ah-step" type="button" role="tab" id="ah-tab-task" aria-selected="false" aria-controls="ah-panel-task" data-step="task" data-copy-label="Copy the agent prompt" tabindex="-1">
          <span class="ah-step-num">3</span><span class="ah-step-name">First task</span>
        </button>
      </div>

      <div class="ah-install" id="ah-install">
        <div class="ah-install-head">
          <span class="ah-install-label" id="ah-step-label">Install</span>
          <button class="ah-copy" type="button" aria-label="Copy the install commands">
            <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><rect x="9" y="9" width="11" height="11" rx="2"></rect><path d="M5 15V5a2 2 0 0 1 2-2h10"></path></svg>
            <span class="ah-copy-label">Copy</span>
          </button>
        </div>

        <div class="ah-step-panel" id="ah-panel-install" role="tabpanel" aria-labelledby="ah-tab-install" tabindex="0">
          <div class="ah-install-lines" id="ah-install-lines">
            <div class="ah-install-line"><span class="ah-prompt">$</span><code id="ah-install-global">python3 bin/install-global.py --target-home "$HOME" --runtime claude --runtime codex</code></div>
            <div class="ah-install-line"><span class="ah-prompt">$</span><code id="ah-install-capability">python3 harness/bin/harness.py init . --capability engineering-suite</code></div>
          </div>
          <p class="ah-step-note">Install the global layer first, then connect the harness to the project.</p>
        </div>

        <div class="ah-step-panel" id="ah-panel-console" role="tabpanel" aria-labelledby="ah-tab-console" tabindex="0" hidden>
          <div class="ah-install-lines">
            <div class="ah-install-line"><span class="ah-prompt">$</span><code id="ah-console-command">python3 harness/bin/harness.py console . --web</code></div>
          </div>
          <p class="ah-step-note">The server picks a free local port and prints a URL with an access token. Open it in the browser.</p>
        </div>

        <div class="ah-step-panel" id="ah-panel-task" role="tabpanel" aria-labelledby="ah-tab-task" tabindex="0" hidden>
          <div class="ah-agent-prompt" id="ah-agent-prompt">Inspect this project and the harness. Read README, CONTEXT.md, and .harness/project.json. Ask me about the goal, stack, and acceptance criteria, then propose the first task and draft its specification. For a new project use start-project; for an existing one use integrate-project. Do not change anything without my confirmation.</div>
          <p class="ah-step-note">Paste the prompt into the agent chat.</p>
        </div>
      </div>
    </div>

    <p class="ah-install-note">
      <span>Requires</span>
      <span class="ah-req"><svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="m8 9-3 3 3 3M16 9l3 3-3 3M13 6l-2 12"></path></svg> Python 3.12+</span>
      <span class="ah-req" title="rust-version 1.89 in native/harness-runtime/Cargo.toml"><svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><circle cx="12" cy="12" r="3.2"></circle><path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3M5.3 5.3l2.1 2.1M16.6 16.6l2.1 2.1M18.7 5.3l-2.1 2.1M7.4 16.6l-2.1 2.1"></path></svg> Rust 1.89+</span>
      <span class="ah-req"><svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><circle cx="6" cy="6" r="2.2"></circle><circle cx="18" cy="6" r="2.2"></circle><circle cx="12" cy="18" r="2.2"></circle><path d="M8 7.5 11 16M16 7.5 13 16"></path></svg> Git</span>
      <span>See the <a href="getting-started/index.html">quick start</a> for details.</span>
    </p>
  </div>

  <div class="ah-art">
    <div class="ah-terminal-wrap">
      <div class="ah-mascot ah-mascot--perch">
        <img src="../assets/mascot.svg" alt="Voxel mascot of Agent Harness Next" width="108" height="140">
        <div class="ah-bubble" id="ah-hero-bubble"><b>Hi, I am H›.</b> I will show a demo <code>harness health</code>.</div>
      </div>
      <div class="ah-terminal" id="ah-hero-terminal">
        <div class="ah-terminal-bar">
          <span class="ah-terminal-dots"><i></i><i></i><i></i></span>
          <span class="ah-terminal-title">harness · runtime-store</span>
          <span class="ah-terminal-beta">beta</span>
          <span class="ah-terminal-demo">demo</span>
          <button class="ah-terminal-play" id="ah-terminal-play" type="button" aria-label="Run the demonstration">
            <svg class="ah-play-icon" viewBox="0 0 24 24" width="11" height="11" fill="currentColor" aria-hidden="true"><path d="M8 5v14l11-7z"></path></svg>
            <svg class="ah-stop-icon" viewBox="0 0 24 24" width="11" height="11" fill="currentColor" aria-hidden="true"><rect x="6" y="6" width="12" height="12" rx="1"></rect></svg>
            <span class="ah-terminal-play-label">Demo</span>
          </button>
        </div>
        <pre class="ah-terminal-output" id="ah-terminal-output" aria-live="polite"><code><span class="ah-t-prompt">$</span> <span class="ah-t-cmd">harness health .</span>
<span class="ah-t-dim">Press “Demo” to run the scenario.</span><span class="ah-cursor"></span></code></pre>
      </div>
      <p class="ah-demo-note">Demonstration data. The site does not check the state of your installed Harness.</p>
    </div>
  </div>
</div>

<div class="ah-specs">
  <div class="ah-spec">
    <span class="ah-spec-icon"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><circle cx="12" cy="12" r="3.2"></circle><path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3M5.3 5.3l2.1 2.1M16.6 16.6l2.1 2.1M18.7 5.3l-2.1 2.1M7.4 16.6l-2.1 2.1"></path></svg></span>
    <div><div class="k">Runtime</div><div class="v">Rust <em>std threads</em></div><div class="s">supervisor, OCI, reconcile</div></div>
  </div>
  <div class="ah-spec">
    <span class="ah-spec-icon"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><ellipse cx="12" cy="5.5" rx="7" ry="3"></ellipse><path d="M5 5.5v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6M5 11.5v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6"></path></svg></span>
    <div><div class="k">State</div><div class="v">SQLite <em>WAL</em></div><div class="s">schema 7 · audit chain</div></div>
  </div>
  <div class="ah-spec">
    <span class="ah-spec-icon"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2"></rect><path d="m8 10 2 2-2 2M13 14h4"></path></svg></span>
    <div><div class="k">Runtimes</div><div class="v"><em>Claude Code</em> · <em>Codex</em></div><div class="s">native hooks and skills</div></div>
  </div>
  <div class="ah-spec">
    <span class="ah-spec-icon"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><rect x="3" y="4" width="18" height="13" rx="2"></rect><path d="M8 21h8M12 17v4"></path></svg></span>
    <div><div class="k">Platforms</div><div class="v"><em>Linux</em> · <em>Windows</em></div><div class="s"><em>UDS</em> and <em>named pipe</em> · containers on Linux only</div></div>
  </div>
</div>

<div class="ah-section">
  <span class="ah-kicker">Builds (capabilities)</span>
  <h2>Build the harness for your task</h2>
  <p>A capability sets the skill set and the agent behavior. The builds are mutually exclusive:
    <code>engineering-suite</code> extends <code>mattpocock-suite</code>,
    <code>backend-orchestration</code> extends <code>engineering-suite</code>, and
    <code>project-foundation</code> is selected on its own. Select a build — the install command
    and the demonstration above update.</p>
</div>

<div class="ah-cap-grid" id="ah-cap-grid" role="radiogroup" aria-label="Harness build">
  <button class="ah-cap" type="button" role="radio" aria-checked="false" data-capability="project-foundation">
    <span class="ah-cap-icon"><svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><ellipse cx="12" cy="5.5" rx="7" ry="3"></ellipse><path d="M5 5.5v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6M5 11.5v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6"></path></svg></span>
    <span class="ah-cap-check" aria-hidden="true"><svg viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="currentColor" stroke-width="3" aria-hidden="true"><path d="m5 12 4.5 4.5L19 6.5"></path></svg></span>
    <span class="ah-cap-name">project-foundation</span>
    <span class="ah-cap-desc">A light, domain-neutral base of five key skills. The default option.</span>
  </button>
  <button class="ah-cap" type="button" role="radio" aria-checked="false" data-capability="mattpocock-suite">
    <span class="ah-cap-icon"><svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><path d="m12 3 8 4.5-8 4.5-8-4.5L12 3Z"></path><path d="m4 12 8 4.5 8-4.5M4 16.5 12 21l8-4.5"></path></svg></span>
    <span class="ah-cap-check" aria-hidden="true"><svg viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="currentColor" stroke-width="3" aria-hidden="true"><path d="m5 12 4.5 4.5L19 6.5"></path></svg></span>
    <span class="ah-cap-name">mattpocock-suite</span>
    <span class="ah-cap-desc">The full upstream set, pinned to a verified commit.</span>
  </button>
  <button class="ah-cap" type="button" role="radio" aria-checked="false" data-capability="engineering-suite">
    <span class="ah-cap-icon"><svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><path d="m14.5 6.5 3-3 3 3-3 3"></path><path d="m4 20 7.2-7.2M9.5 4.5l10 10-2.5 2.5-10-10z"></path></svg></span>
    <span class="ah-cap-check" aria-hidden="true"><svg viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="currentColor" stroke-width="3" aria-hidden="true"><path d="m5 12 4.5 4.5L19 6.5"></path></svg></span>
    <span class="ah-cap-name">engineering-suite</span>
    <span class="ah-cap-desc">Epics and tickets, triage, two-axis review, <code>qa-gate</code>, and PR preparation.</span>
  </button>
  <button class="ah-cap" type="button" role="radio" aria-checked="false" data-capability="backend-orchestration">
    <span class="ah-cap-icon"><svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><circle cx="6" cy="6" r="2.4"></circle><circle cx="18" cy="6" r="2.4"></circle><circle cx="12" cy="18" r="2.4"></circle><path d="M8.2 6h7.6M7.2 8.1l3.5 7.6M16.8 8.1l-3.5 7.6"></path></svg></span>
    <span class="ah-cap-check" aria-hidden="true"><svg viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="currentColor" stroke-width="3" aria-hidden="true"><path d="m5 12 4.5 4.5L19 6.5"></path></svg></span>
    <span class="ah-cap-name">backend-orchestration</span>
    <span class="ah-cap-desc">Roles and a coordinator for distributed systems: briefs, worktrees, and a ledger.</span>
  </button>
</div>

<div class="ah-roles-route" id="ah-roles-route" hidden>
  <div class="ah-roles-head">
    <b>Role route for backend-orchestration</b>
    <span>Coordinator drives the task through roles; each stage opens the matching documentation.</span>
  </div>
  <div class="ah-role-steps" role="list">
    <div class="ah-role-step" role="listitem"><a href="skills/coordinator/"><span class="n">01</span><b>Coordinator</b><span>brief and dispatch</span></a><span class="ah-role-arrow" aria-hidden="true">→</span></div>
    <div class="ah-role-step" role="listitem"><a href="skills/developer/"><span class="n">02</span><b>Developer</b><span>implementation in the zone</span></a><span class="ah-role-arrow" aria-hidden="true">→</span></div>
    <div class="ah-role-step" role="listitem"><a href="skills/code-review-role/"><span class="n">03</span><b>Code review</b><span>two axes</span></a><span class="ah-role-arrow" aria-hidden="true">→</span></div>
    <div class="ah-role-step" role="listitem"><a href="skills/qa/"><span class="n">04</span><b>QA</b><span>full gate</span></a><span class="ah-role-arrow" aria-hidden="true">→</span></div>
    <div class="ah-role-step" role="listitem"><a href="guides/orchestration/publish/"><span class="n">05</span><b>Publish</b><span>PR after confirmation</span></a></div>
  </div>
  <p class="ah-roles-note">A worktree separates working files and branches; process permissions are configured separately. QA runs the full gate; a PR opens after a separate confirmation.</p>
</div>

<p class="ah-note"><a href="getting-started/index.html">How to choose a build and connect it to a project</a></p>

<div class="ah-section">
  <span class="ah-kicker">Features</span>
  <h2>Policy and execution are separate</h2>
  <p>Python makes decisions. The Rust runtime stores state and starts processes.
    Checks run by plan, not as one full set.</p>
</div>

<div class="ah-feature-grid">
  <button class="ah-feature" type="button" data-feature="runtime" aria-haspopup="dialog">
    <span class="ah-feature-icon"><svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><rect x="4" y="4" width="16" height="16" rx="3"></rect><path d="M8 9h8M8 13h5M8 17h7"></path></svg></span>
    <b>Rust runtime and store</b>
    <span>The only writer of operational state: SQLite WAL, leases with fencing, an audit chain,
      and idempotent IPC operations.</span>
    <span class="ah-feature-more">Quick look →</span>
  </button>
  <button class="ah-feature" type="button" data-feature="verification" aria-haspopup="dialog">
    <span class="ah-feature-icon"><svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><path d="M5 12l4 4L19 6"></path><path d="M5 20h14"></path></svg></span>
    <b>Incremental checks</b>
    <span>ChangeImpact and VerificationPlan run only the affected tests; QA runs a full
      clean-room check on the final SHA.</span>
    <span class="ah-feature-more">Quick look →</span>
  </button>
  <button class="ah-feature" type="button" data-feature="gate" aria-haspopup="dialog">
    <span class="ah-feature-icon"><svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><path d="M12 3l8 4v5c0 5-3.4 8-8 9-4.6-1-8-4-8-9V7l8-4Z"></path><path d="m8.5 12 2.3 2.3L15.8 9"></path></svg></span>
    <b>Release Gate</b>
    <span>Publication starts only after a full run on the final SHA and a human confirmation.</span>
    <span class="ah-feature-more">Quick look →</span>
  </button>
  <button class="ah-feature" type="button" data-feature="hooks" aria-haspopup="dialog">
    <span class="ah-feature-icon"><svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><path d="M4 7h10M18 7h2M4 12h3M11 12h9M4 17h10M18 17h2"></path><circle cx="16" cy="7" r="2"></circle><circle cx="9" cy="12" r="2"></circle><circle cx="16" cy="17" r="2"></circle></svg></span>
    <b>Hook profiles</b>
    <span>A policy for warnings and retries that does not weaken the guards at risk boundaries.</span>
    <span class="ah-feature-more">Quick look →</span>
  </button>
  <button class="ah-feature" type="button" data-feature="console" aria-haspopup="dialog">
    <span class="ah-feature-icon"><svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><rect x="3" y="4" width="18" height="14" rx="2"></rect><path d="M8 21h8M12 18v3"></path></svg></span>
    <b>Web console</b>
    <span>The TUI and the browser are clients of one Console Server: tasks, orchestration, reports,
      and recovery.</span>
    <span class="ah-feature-more">Quick look →</span>
  </button>
  <button class="ah-feature" type="button" data-feature="security" aria-haspopup="dialog">
    <span class="ah-feature-icon"><svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><path d="M12 3l8 4v5c0 5-3.4 8-8 9-4.6-1-8-4-8-9V7l8-4Z"></path><path d="M9 12h6M12 9v6"></path></svg></span>
    <b>Security and containers</b>
    <span>Worker isolation, an egress allowlist, and preserved native approval.</span>
    <span class="ah-feature-more">Quick look →</span>
  </button>
</div>

<section class="ah-section" aria-labelledby="ah-task-title">
  <span class="ah-kicker">Architecture</span>
  <h2 id="ah-task-title">How a task runs</h2>
  <p>Python builds context from Repo Map and enabled RAG memory, prepares a brief, and obtains
    human or auto-policy approval. Rust receives requests over IPC, executes the plan,
    and returns observations; Python sends results back to the console client.</p>
</section>

<div class="ah-flow ah-core-region" aria-labelledby="ah-task-title">
  <div class="ah-core-controls" id="ah-core-controls" role="group" aria-label="Diagram route">
    <button class="md-button" type="button" data-core-route="launch" aria-pressed="true" disabled>Run task</button>
    <button class="md-button" type="button" data-core-route="context" aria-pressed="false" disabled>Context</button>
    <button class="md-button" type="button" data-core-route="state" aria-pressed="false" disabled>Read state</button>
    <button class="md-button" type="button" data-core-route="recovery" aria-pressed="false" disabled>Recover execution</button>
  </div>
  <p class="ah-core-hint">Select a component or route. Each line carries a request (blue) and a response (green). This is a demonstration.</p>
  <div class="ah-core is-isometric" id="ah-core"></div>
  <div class="ah-flow-note" id="ah-flow-note" aria-live="polite" aria-atomic="true">
    <b>Python → IPC → Rust</b>
    <span>Plan and approval → execution → state and response. See the documentation below for details.</span>
  </div>
  <div class="ah-core-links">
    <a href="architecture/index.html">Explore the architecture →</a>
    <a href="diagrams/harness-core.architecture.html">Full relationship model · Archify →</a>
  </div>
</div>

<dialog class="ah-dialog" id="ah-feature-dialog">
  <div class="ah-dialog-head">
    <div><span class="ah-kicker">Features</span><h3 id="ah-dialog-title"></h3></div>
    <button class="ah-dialog-close" type="button" aria-label="Close">×</button>
  </div>
  <p id="ah-dialog-desc"></p>
  <pre class="ah-dialog-code"><code id="ah-dialog-code"></code></pre>
  <div class="ah-dialog-foot"><a class="ah-dialog-link" id="ah-dialog-link" href="architecture/index.html">Open the section →</a></div>
</dialog>

<script>
  (function () {
    const scenarios = {
      "project-foundation": {
        bubble: "<b>A light base.</b> Five key skills and no orchestration — a quick start.",
        done: "<b>Done.</b> project-foundation: a minimal base without a batch or a coordinator.",
        lines: [
          ['dim', '== Skills =='],
          ['ok', '✓ project-foundation: 5 key skills'],
          ['ok', '✓ snapshot: managed files in place'],
          ['info', 'ℹ orchestration: not selected — no coordinator needed'],
          ['dim', '== Summary =='],
          ['sum', '<span class="ah-t-ok">ok=12</span> <span class="ah-t-warn">warn=1</span> <span class="ah-t-fail">fail=0</span> <span class="ah-t-dim">skipped=2</span>']
        ]
      },
      "mattpocock-suite": {
        bubble: "<b>The upstream set.</b> A pinned snapshot and a verified commit — no extra layers.",
        done: "<b>Done.</b> mattpocock-suite: the upstream set is pinned and verified.",
        lines: [
          ['dim', '== Skills =='],
          ['ok', '✓ upstream: 25 skills pinned'],
          ['ok', '✓ snapshot: v1.2.3 · 6acc160'],
          ['info', 'ℹ orchestration: not selected — no coordinator needed'],
          ['dim', '== Summary =='],
          ['sum', '<span class="ah-t-ok">ok=18</span> <span class="ah-t-warn">warn=2</span> <span class="ah-t-fail">fail=0</span> <span class="ah-t-dim">skipped=3</span>']
        ]
      },
      "engineering-suite": {
        bubble: "<b>The engineering workflow.</b> I check the ledger, the dispatches, and the runtime readiness.",
        done: "<b>Done.</b> engineering-suite: the workflow, review, and QA are ready.",
        lines: [
          ['dim', '== Orchestration =='],
          ['ok', '✓ ledger: authority=runtime-store schema_version=7'],
          ['ok', '✓ no unfinished batches'],
          ['ok', '✓ heartbeat: 300 s by default'],
          ['ok', '✓ engineering-suite: 32 skills'],
          ['ok', '✓ runtime-store: read-only · schema 7'],
          ['info', 'ℹ Rust runtime: protocol 1.7 · serving'],
          ['warn', '⚠ Repo Map: minimal (parser bundle missing)'],
          ['dim', '== Summary =='],
          ['sum', '<span class="ah-t-ok">ok=40</span> <span class="ah-t-warn">warn=4</span> <span class="ah-t-fail">fail=0</span> <span class="ah-t-dim">skipped=11</span>']
        ]
      },
      "backend-orchestration": {
        bubble: "<b>Orchestration.</b> I enable the roles, the coordinator, the ledger, and the QA lane.",
        done: "<b>Done.</b> backend-orchestration: the coordinator, roles, and ledger are up.",
        lines: [
          ['dim', '== Orchestration =='],
          ['ok', '✓ ledger: authority=runtime-store schema_version=7'],
          ['ok', '✓ coordinator: 3 roles ready'],
          ['ok', '✓ no unfinished batches'],
          ['ok', '✓ heartbeat: 300 s by default'],
          ['warn', '⚠ QA lane: waiting for evidence'],
          ['dim', '== Summary =='],
          ['sum', '<span class="ah-t-ok">ok=46</span> <span class="ah-t-warn">warn=3</span> <span class="ah-t-fail">fail=0</span> <span class="ah-t-dim">skipped=9</span>']
        ]
      }
    };

    const features = {
      runtime: {
        title: "Rust runtime and store",
        desc: "The only writer of operational state: SQLite WAL, leases with fencing, an audit chain, and idempotent IPC operations.",
        code: "$ harness health .\n✓ ledger: authority=runtime-store schema_version=7\n✓ audit chain: 306 records · valid\nℹ runtime: protocol 1.7 · serving",
        href: "architecture/index.html"
      },
      verification: {
        title: "Incremental checks",
        desc: "ChangeImpact and VerificationPlan run only the affected tests; QA runs a full clean-room check on the final SHA.",
        code: "ChangeImpact → VerificationPlan\nfocused: tests/orchestration/test_runtime_client.py\nfull:    make verify (clean-room, final SHA)",
        href: "getting-started/index.html"
      },
      gate: {
        title: "Release Gate",
        desc: "Publication starts only after a full run on the final SHA and a human confirmation.",
        code: "Release Gate\ncandidate: 6a7f748\ntarget:    master\ntree:      match\ndecision:  blocked · QA evidence missing",
        href: "architecture/index.html"
      },
      hooks: {
        title: "Hook profiles",
        desc: "A policy for warnings and retries that does not weaken the guards at risk boundaries.",
        code: "// .harness/hook-policy.json\n{ \"profile\": \"standard\", \"policy_sha256\": \"…\" }",
        href: "reference/hooks/index.html"
      },
      console: {
        title: "Web console",
        desc: "The TUI and the browser are clients of one Console Server: tasks, orchestration, reports, and recovery.",
        code: "$ python3 harness/bin/harness.py console . --web\nConsole Server: free port · URL with access token\nScreens: Home · Task board · Orchestration · Reports",
        href: "demo/index.html"
      },
      security: {
        title: "Security and containers",
        desc: "Worker isolation, an egress allowlist, and preserved native approval.",
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
    const copy = document.querySelector(".ah-copy");
    const rolesRoute = document.getElementById("ah-roles-route");
    const steps = Array.from(document.querySelectorAll(".ah-step"));
    const stepPanels = Array.from(document.querySelectorAll(".ah-step-panel"));
    const stepLabel = document.getElementById("ah-step-label");
    let selected = "engineering-suite";
    let timers = [];
    let running = false;

    function setStep(name, focus) {
      steps.forEach((button) => {
        const active = button.dataset.step === name;
        button.classList.toggle("is-active", active);
        button.setAttribute("aria-selected", active ? "true" : "false");
        button.tabIndex = active ? 0 : -1;
        if (active) {
          stepLabel.textContent = button.querySelector(".ah-step-name").textContent;
          copy.setAttribute("aria-label", button.dataset.copyLabel || "Copy");
          if (focus) button.focus();
        }
      });
      stepPanels.forEach((panel) => {
        panel.hidden = panel.id !== "ah-panel-" + name;
      });
    }

    steps.forEach((button, index) => {
      button.addEventListener("click", () => setStep(button.dataset.step));
      button.addEventListener("keydown", (event) => {
        if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
        event.preventDefault();
        let next = index;
        if (event.key === "ArrowLeft") next = (index - 1 + steps.length) % steps.length;
        if (event.key === "ArrowRight") next = (index + 1) % steps.length;
        if (event.key === "Home") next = 0;
        if (event.key === "End") next = steps.length - 1;
        setStep(steps[next].dataset.step, true);
      });
    });

    function setRunning(value) {
      running = value;
      play.classList.toggle("is-running", value);
      playLabel.textContent = value ? "Stop" : "Demo";
      play.setAttribute("aria-label", value ? "Stop the demonstration" : "Run the demonstration");
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
      rolesRoute.hidden = name !== "backend-orchestration";
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
        bubble.innerHTML = "<b>Paused.</b> Press “Demo” to run the scenario again.";
        return;
      }
      runScenario(selected);
    });

    function copyPayload() {
      const panel = stepPanels.find((item) => !item.hidden);
      if (!panel) return "";
      const prompt = panel.querySelector(".ah-agent-prompt");
      if (prompt) return prompt.textContent.trim();
      return Array.from(panel.querySelectorAll("code"))
        .map((code) => code.textContent.trim())
        .join("\n");
    }

    copy.addEventListener("click", () => {
      const text = copyPayload();
      if (!text) return;
      navigator.clipboard.writeText(text).then(() => {
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

    setStep("install");
    selectCapability(selected, false);
    timers.push(window.setTimeout(() => runScenario(selected), 1100));
  })();
</script>
