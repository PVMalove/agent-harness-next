# Guides

Choose a route for your task or find a chapter by title. Installation and project settings belong in [Getting started](../getting-started/index.md). Translations of skills, hooks and agents belong in [Reference](../reference/index.md).

<div data-ah-directory>
  <div class="ah-ref-glossary">
    <div class="ah-ref-glossary-head">
      <div>
        <b>All guides</b>
        <span>Chapters by route, command and topic. Search filters the cards below.</span>
      </div>
    </div>
    <form class="ah-ref-glossary-search" role="search">
      <input type="search" aria-label="Find a guide chapter" placeholder="Find a chapter: implement, QA, worktree…" autocomplete="off" spellcheck="false">
      <button type="submit">Search</button>
      <button type="button" data-ah-clear>Clear</button>
    </form>
    <p role="status" aria-live="polite"></p>
  </div>

  <section data-ah-group>
    <h2>Working on a task</h2>
    <div class="ah-cards ah-cards--four">
      <a class="ah-card" data-ah-entry href="workflow/">
        <span class="i">→</span>
        <b>Workflow</b>
        <span>Choose a route from the task state: stages, artifacts and the next step.</span>
      </a>
      <a class="ah-card" data-ah-entry href="implement/">
        <span class="i">⌘</span>
        <b>/implement</b>
        <span>Full route: specification, tickets, roles, gates and PR.</span>
      </a>
      <a class="ah-card" data-ah-entry href="fast-implement/">
        <span class="i">⚡</span>
        <b>/fast-implement</b>
        <span>A small ticket in the current session without a separate batch.</span>
      </a>
      <a class="ah-card" data-ah-entry href="tdd/">
        <span class="i">✓</span>
        <b>TDD</b>
        <span>Red-green-refactor and independent expectations.</span>
      </a>
      <a class="ah-card" data-ah-entry href="code-review/">
        <span class="i">◇</span>
        <b>Code review</b>
        <span>Standards and spec review before QA.</span>
      </a>
      <a class="ah-card" data-ah-entry href="qa-gate/">
        <span class="i">◈</span>
        <b>QA gate and Release Gate</b>
        <span>Local QA, clean-room verification and publishing.</span>
      </a>
      <a class="ah-card" data-ah-entry href="examples/">
        <span class="i">▣</span>
        <b>Full examples</b>
        <span>End-to-end scenarios on concrete tasks.</span>
      </a>
      <a class="ah-card" data-ah-entry href="troubleshooting/">
        <span class="i">⌁</span>
        <b>Troubleshooting</b>
        <span>Refusal reasons and next actions.</span>
      </a>
    </div>
  </section>

  <section data-ah-group>
    <h2>Orchestration and concepts</h2>
    <div class="ah-cards ah-cards--four">
      <a class="ah-card" data-ah-entry href="../harness-guide/">
        <span class="i">✦</span>
        <b>How Harness works</b>
        <span>Capabilities, roles, checks and harness boundaries.</span>
      </a>
      <a class="ah-card" data-ah-entry href="../backend-orchestration/">
        <span class="i">⊕</span>
        <b>Orchestration</b>
        <span>Setup, runs, reports, clean-room QA and recovery.</span>
      </a>
      <a class="ah-card" data-ah-entry href="../console-configuration/">
        <span class="i">⌂</span>
        <b>Configuration in the console</b>
        <span>Drafts, versions and applying configuration.</span>
      </a>
      <div class="ah-card" data-ah-entry>
        <span class="i">◫</span>
        <b>Concepts</b>
        <span>Hooks, worktrees and context management.</span>
        <span class="ah-card-links">
          <a href="../concepts/hooks/">Hooks</a>
          <a href="../concepts/worktrees/">Worktrees</a>
          <a href="../concepts/context/">Context</a>
        </span>
      </div>
    </div>
  </section>

  <div data-ah-directory-art>
    <p class="ah-core-hint">Full route from idea to PR. Choose a stage for details.</p>
    <div class="ah-flow" id="ah-guide-diagram"><div class="ah-core-flow" id="ah-guide-flow"></div><div class="ah-flow-note" id="ah-guide-note" aria-live="polite"></div></div>
  </div>
</div>
