# Workflow {#workflow-guide}

The harness leads the work from an idea to a merge in five steps. Not every task goes through all five.
The entry point decides which steps are skipped entirely and which run once for a whole epic.

## Five steps {#steps}

### Entry points {#entries}

<div class="ah-scenarios" role="radiogroup" aria-label="Workflow entry point">
  <button class="ah-scenario is-active" type="button" data-scenario="full" role="radio" aria-checked="true" tabindex="0">
    <span class="ah-scenario-kicker">Scenario</span>
    <b>All stages (full cycle)</b>
    <span class="ah-scenario-desc">Idea → specification → tickets → implementation → publication. Nothing is skipped.</span>
    <span class="ah-scenario-skip">Skipped: nothing</span>
  </button>
  <button class="ah-scenario" type="button" data-scenario="single" role="radio" aria-checked="false" tabindex="-1">
    <span class="ah-scenario-kicker">1</span>
    <b>One ticket from outside (bug / small feature)</b>
    <span class="ah-scenario-desc">A bug report or a small feature that fits in one session. <code>/triage</code> brings the issue to <code>status::ready</code> and to the <code>hitl</code>/<code>afk</code> mode, and then one implementation step follows.</span>
    <span class="ah-scenario-skip">Skipped: design, specification, decomposition</span>
  </button>
  <button class="ah-scenario" type="button" data-scenario="epic" role="radio" aria-checked="false" tabindex="-1">
    <span class="ah-scenario-kicker">2</span>
    <b>An epic-sized task (the scope is known)</b>
    <span class="ah-scenario-desc">The scope of work is known and needs decomposition. You work it out in one session, then <code>/to-spec</code> → <code>/to-tickets</code> → implementation of each ticket.</span>
    <span class="ah-scenario-skip">Skipped: Wayfinder</span>
  </button>
  <button class="ah-scenario" type="button" data-scenario="large" role="radio" aria-checked="false" tabindex="-1">
    <span class="ah-scenario-kicker">3</span>
    <b>A large scope (the path is unclear)</b>
    <span class="ah-scenario-desc"><code>/wayfinder</code> keeps a decision map until no open questions remain, and then hands the work to <code>/to-spec</code>. The work runs in several sessions.</span>
    <span class="ah-scenario-skip">Skipped: nothing</span>
  </button>
</div>

<div class="ah-route">
  <span class="ah-route-label">Route</span>
  <span class="ah-route-flow" id="ah-workflow-route" aria-live="polite">
    <a class="ah-command" href="#idea">/grilling</a><span class="ah-route-or">or</span><a class="ah-command" href="../../skills/wayfinder/">/wayfinder</a><span class="ah-route-arrow">→</span><a class="ah-command" href="#spec">/to-spec</a><span class="ah-route-arrow">→</span><a class="ah-command" href="#tickets">/to-tickets</a><span class="ah-route-arrow">→</span><a class="ah-command" href="../implement/">/implement</a><span class="ah-route-arrow">→</span><a class="ah-command" href="../../skills/to-pull-requests/">/to-pull-requests</a>
  </span>
</div>

<ol class="ah-pipeline" aria-label="The five workflow steps">
  <li class="ah-step is-active" data-step="design">
    <span class="ah-step-num" aria-hidden="true">01</span>
    <div class="ah-step-body">
      <div class="ah-step-head"><h3>Design</h3><span class="ah-step-skip" hidden>SKIPPED</span></div>
      <p>The step removes uncertainty and records the decisions and the boundaries.</p>
    </div>
    <div class="ah-step-side">
      <span class="ah-step-label">Led by</span>
      <div class="ah-step-commands">
      <a class="ah-command" href="#idea" title="Working out the idea: the core of the stage">/grilling</a>
      <a class="ah-command" href="#idea" title="Working out the idea in an existing repository">/grill-with-docs</a>
      <a class="ah-command" href="../../skills/wayfinder/" data-command="wayfinder" title="Wayfinder: a decision map for a large scope">/wayfinder</a>
    </div>
      <span class="ah-wayfinder-note" id="ah-wayfinder-note" hidden>Wayfinder is not needed: the scope of work is already known</span>
    </div>
  </li>
  <li class="ah-step is-active" data-step="spec">
    <span class="ah-step-num" aria-hidden="true">02</span>
    <div class="ah-step-body">
      <div class="ah-step-head"><h3>Specification</h3><span class="ah-step-skip" hidden>SKIPPED</span></div>
      <p>The discussion becomes the single source of truth and is published to the tracker.</p>
    </div>
    <div class="ah-step-side">
      <span class="ah-step-label">Led by</span>
      <div class="ah-step-commands">
      <a class="ah-command" href="#spec" title="Specification: /to-spec">/to-spec</a>
    </div>
    </div>
  </li>
  <li class="ah-step is-active" data-step="tickets">
    <span class="ah-step-num" aria-hidden="true">03</span>
    <div class="ah-step-body">
      <div class="ah-step-head"><h3>Tickets</h3><span class="ah-step-skip" hidden>SKIPPED</span></div>
      <p>The specification is cut into vertical slices with blocking links.</p>
    </div>
    <div class="ah-step-side">
      <span class="ah-step-label">Led by</span>
      <div class="ah-step-commands">
      <a class="ah-command" href="#tickets" title="Decomposition: /to-tickets">/to-tickets</a>
    </div>
    </div>
  </li>
  <li class="ah-step is-active" data-step="implementation">
    <span class="ah-step-num" aria-hidden="true">04</span>
    <div class="ah-step-body">
      <div class="ah-step-head"><h3>Implementation</h3><span class="ah-step-skip" hidden>SKIPPED</span></div>
      <p>Test first, implementation, independent review, QA.</p>
    </div>
    <div class="ah-step-side">
      <span class="ah-step-label">Led by</span>
      <div class="ah-step-commands">
      <a class="ah-command" href="../implement/" title="The full implementation route">/implement</a>
      <a class="ah-command" href="../fast-implement/" title="The short implementation route">/fast-implement</a>
      <a class="ah-command" href="../../skills/to-guide/" title="A guide for a person on the hitl route">/to-guide</a>
    </div>
    </div>
  </li>
  <li class="ah-step is-active" data-step="publish">
    <span class="ah-step-num" aria-hidden="true">05</span>
    <div class="ah-step-body">
      <div class="ah-step-head"><h3>Publication</h3><span class="ah-step-guard">merge — a human</span></div>
      <p>A PR to the integration branch, a merge by a human, and the closing of the ticket.</p>
    </div>
    <div class="ah-step-side">
      <span class="ah-step-label">Led by</span>
      <div class="ah-step-commands">
      <a class="ah-command" href="../../skills/to-pull-requests/" title="Preparing the PR and handing it to a human">/to-pull-requests</a>
    </div>
    </div>
  </li>
</ol>

<div class="ah-guardrail" role="note">
  <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><path d="M12 3l8 4v5c0 5-3.4 8-8 9-4.6-1-8-4-8-9V7l8-4Z"></path><path d="M9 12h6M12 9v6"></path></svg>
  <div><b>A human always performs the merge.</b> No step opens or merges a PR by itself.</div>
</div>

<div class="ah-askmatt">
  <span class="ah-askmatt-icon" aria-hidden="true">?</span>
  <div>
    <b>Not sure which step to start from?</b> Run
    <a class="ah-command" href="../../skills/ask-matt/">/ask-matt</a>. The agent finds the entry point
    for an issue or a hard bug. It describes the main path, the entries for incoming issues and hard
    bugs, and the branches outside this scheme.
  </div>
</div>

<figure class="ah-diagram">
  <div class="ah-diagram-bar">
    <figcaption>Which commands lead from each entry point to the merge, and what is skipped.</figcaption>
    <button class="ah-diagram-expand" type="button" aria-haspopup="dialog">Expand</button>
    <a class="ah-diagram-open" href="../../assets/diagrams/workflow-entries.html" target="_blank" rel="noopener">Open separately ↗</a>
  </div>
  <iframe class="ah-diagram-frame" data-theme-sync src="../../assets/diagrams/workflow-entries.html" title="Entry points and the five workflow steps" loading="lazy"></iframe>
</figure>

## Working out the idea {#idea}

<div class="ah-tool-grid">
  <article class="ah-tool-card">
    <header class="ah-tool-head"><code>/grilling</code><span class="ah-tool-tag">Core of the stage</span></header>
    <p><code>/grilling</code> is the core of the stage. The agent models the plan as a decision tree and asks
      questions along the frontier, that is, only those whose prerequisites are already closed. Each round
      starts with a short summary of what has settled. When the frontier is empty, the agent shows a
      summary of the decisions and asks for confirmation, and then the work moves to <code>/to-spec</code>.</p>
    <footer class="ah-tool-foot"><b>Artifacts:</b> a summary of decisions; the handoff to <code>/to-spec</code>.</footer>
  </article>
  <article class="ah-tool-card">
    <header class="ah-tool-head"><code>/grill-me</code><span class="ah-tool-tag">From scratch, no repository</span></header>
    <p><code>/grill-me</code> is a thin wrapper for designing from scratch, when there is no repository yet. It
      leaves a summary of decisions.</p>
    <footer class="ah-tool-foot"><b>Artifacts:</b> a summary of decisions.</footer>
  </article>
  <article class="ah-tool-card">
    <header class="ah-tool-head"><code>/grill-with-docs</code><span class="ah-tool-tag">Preferred for a project</span></header>
    <p><code>/grill-with-docs</code> is the same shell for work in an existing repository. It is preferred
      because it also keeps the glossary and the architecture decisions.</p>
    <footer class="ah-tool-foot"><b>Artifacts:</b> a glossary and ADRs.</footer>
  </article>
  <article class="ah-tool-card">
    <header class="ah-tool-head"><code>/domain-modeling</code><span class="ah-tool-tag">Domain reinforcement</span></header>
    <p><code>/domain-modeling</code> strengthens design in existing code. It compares terms with the glossary,
      clarifies vague concepts, checks claims against the code, and writes the agreements into
      <code>CONTEXT.md</code> at once. It proposes an architecture decision only when the decision is hard to
      reverse, is not obvious without context, and was a real choice between alternatives.</p>
    <footer class="ah-tool-foot"><b>Artifacts:</b> <code>CONTEXT.md</code>; an ADR for a hard-to-reverse decision.</footer>
  </article>
</div>

## Specification {#spec}

<code>/to-spec</code> does not interview again. It synthesizes what the discussion already covered. First it
studies the domain vocabulary and the decisions of the affected area, outlines the seams — the points
where the feature will be tested — and proposes a name for the integration branch. Then it writes the
specification to a file and publishes it to the tracker. The publication does not pass the body inline;
it reads the body from the file.

What the specification contains:

<div class="ah-blueprint">
  <div class="ah-blueprint-row"><code>Problem Statement</code><span>what the problem is</span><span class="ah-badge">Context</span></div>
  <div class="ah-blueprint-row"><code>Solution</code><span>what changes</span><span class="ah-badge">Solution</span></div>
  <div class="ah-blueprint-row"><code>User Stories</code><span>what the user needs and why</span><span class="ah-badge">User</span></div>
  <div class="ah-blueprint-row"><code>Implementation Decisions</code><span>modules, interfaces, and decisions, without code paths</span><span class="ah-badge">Architecture</span></div>
  <div class="ah-blueprint-row"><code>Testing Decisions</code><span>which seams are tested and at which level</span><span class="ah-badge ah-badge--primary">Seams</span></div>
  <div class="ah-blueprint-row"><code>Out of Scope</code><span>what the work explicitly does not include</span><span class="ah-badge ah-badge--warn">Guardrail</span></div>
  <div class="ah-blueprint-row"><code>Integration Branch</code><span>the exact name of the branch that receives the work</span><span class="ah-badge">Branch</span></div>
</div>

!!! warning "Important for controlling the agent"

    The Out of Scope section limits the scope. Without an explicit prohibition, the agent tends to add
    incidental caching or an infrastructure change. After publication, the integration branch is created
    from the base branch of the project. Nobody resets or deletes an existing branch.

## Decomposition {#tickets}

`/to-tickets` turns the specification into tickets — vertical slices. Each slice is verified
independently and fits in one fresh context window. Nothing is published until you explicitly approve
the split. The agent shows the slices, the blocking edges, and the estimate, and then refines them
from your remarks.

- A slice is not a layer. A ticket that "adds a layer" cannot be verified on its own.
- A blocking edge marks a dependency on a result, not an overlap of files.
- An estimate in story points on the Fibonacci scale gives the route label: `pipeline::fast` for a
  small scope and `pipeline::full` for a significant one.
- The execution mode `hitl` or `afk` decides who implements the ticket: a person following a guide or an agent.

A ticket gets the state label `status::ready`, or `status::blocked` if it waits for another ticket of the
same package. Only a confirmed merge and the closing of the predecessor remove the blocking.

<figure class="ah-diagram">
  <div class="ah-diagram-bar">
    <figcaption>How a ticket moves through the labels <code>status::ready</code>, <code>status::in-progress</code>, and <code>status::blocked</code>.</figcaption>
    <button class="ah-diagram-expand" type="button" aria-haspopup="dialog">Expand</button>
    <a class="ah-diagram-open" href="../../assets/diagrams/ticket-status.html" target="_blank" rel="noopener">Open separately ↗</a>
  </div>
  <iframe class="ah-diagram-frame" data-theme-sync src="../../assets/diagrams/ticket-status.html" title="The state label of a ticket" loading="lazy"></iframe>
</figure>

## Orchestrating the Discovery Pipeline {#discovery}

The paths approved during design are recorded as part of the agreement, saved in the specification, and
assigned to specific tickets. Before implementation, the harness builds a Context Package from these paths,
the tests, and the decisions. The package is a deterministic data set for the roles of one batch. The
coordinator registers the package in the ledger and checks its freshness by the hashes of the sources
before each dispatch.

For details on the runtime and the store, see the [architecture overview](../architecture/overview.md).

## Next {#next}

- [“/implement”](implement.md)
- [“/fast-implement”](fast-implement.md)
- [Architecture overview](../architecture/overview.md)

<script>
  (function () {
    const scenarios = {
      full: {
        active: ["design", "spec", "tickets", "implementation", "publish"],
        skipped: [],
        wayfinder: "both",
        route: '<a class="ah-command" href="#idea">/grilling</a><span class="ah-route-or">or</span><a class="ah-command" href="../../skills/wayfinder/">/wayfinder</a><span class="ah-route-arrow">→</span><a class="ah-command" href="#spec">/to-spec</a><span class="ah-route-arrow">→</span><a class="ah-command" href="#tickets">/to-tickets</a><span class="ah-route-arrow">→</span><a class="ah-command" href="../implement/">/implement</a><span class="ah-route-arrow">→</span><a class="ah-command" href="../../skills/to-pull-requests/">/to-pull-requests</a>'
      },
      single: {
        active: ["implementation", "publish"],
        skipped: ["design", "spec", "tickets"],
        wayfinder: "none",
        route: '<a class="ah-command" href="../../skills/triage/">/triage</a><span class="ah-route-arrow">→</span><code class="ah-status-pill">status::ready</code><span class="ah-route-arrow">→</span><a class="ah-command" href="../implement/">/implement</a><span class="ah-route-or">or</span><a class="ah-command" href="../fast-implement/">/fast-implement</a><span class="ah-route-or">/</span><a class="ah-command" href="../../skills/to-guide/">/to-guide</a>'
      },
      epic: {
        active: ["design", "spec", "tickets", "implementation", "publish"],
        skipped: [],
        wayfinder: "skip",
        route: '<a class="ah-command" href="#idea">/grilling</a><span class="ah-route-arrow">→</span><a class="ah-command" href="#spec">/to-spec</a><span class="ah-route-arrow">→</span><a class="ah-command" href="#tickets">/to-tickets</a><span class="ah-route-arrow">→</span><a class="ah-command" href="../implement/">/implement</a><span class="ah-route-skip">Wayfinder — SKIPPED</span>'
      },
      large: {
        active: ["design", "spec", "tickets", "implementation", "publish"],
        skipped: [],
        wayfinder: "yes",
        route: '<a class="ah-command" href="../../skills/wayfinder/">/wayfinder</a><span class="ah-route-arrow">→</span><a class="ah-command" href="#spec">/to-spec</a><span class="ah-route-arrow">→</span><a class="ah-command" href="#tickets">/to-tickets</a><span class="ah-route-arrow">→</span><a class="ah-command" href="../implement/">/implement</a><span class="ah-route-arrow">→</span><a class="ah-command" href="../../skills/to-pull-requests/">/to-pull-requests</a>'
      }
    };
    const buttons = Array.from(document.querySelectorAll("[data-scenario]"));
    const steps = Array.from(document.querySelectorAll("[data-step]"));
    const route = document.getElementById("ah-workflow-route");
    const wayfinder = document.querySelector("[data-command='wayfinder']");
    const wayfinderNote = document.getElementById("ah-wayfinder-note");

    function select(name, focus) {
      const scenario = scenarios[name];
      if (!scenario) return;
      buttons.forEach((button) => {
        const active = button.dataset.scenario === name;
        button.classList.toggle("is-active", active);
        button.setAttribute("aria-checked", active ? "true" : "false");
        button.tabIndex = active ? 0 : -1;
        if (active && focus) button.focus();
      });
      steps.forEach((step) => {
        const id = step.dataset.step;
        const skipped = scenario.skipped.includes(id);
        step.classList.toggle("is-active", scenario.active.includes(id));
        step.classList.toggle("is-skipped", skipped);
        const badge = step.querySelector(".ah-step-skip");
        if (badge) badge.hidden = !skipped;
      });
      if (wayfinder) {
        wayfinder.classList.toggle("is-skipped", scenario.wayfinder === "skip");
      }
      wayfinderNote.hidden = scenario.wayfinder !== "skip";
      route.innerHTML = scenario.route;
      animate(scenario);
    }

    const reduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const pipeline = document.querySelector(".ah-pipeline");
    const scenarioGrid = document.querySelector(".ah-scenarios");
    const pulse = document.createElement("span");
    pulse.className = "ah-rail-pulse";
    pulse.setAttribute("aria-hidden", "true");
    pipeline.appendChild(pulse);
    let pulseAnimation = null;

    function restart(element, index) {
      element.style.setProperty("--i", index);
      element.classList.remove("is-entering");
      void element.offsetWidth;
      element.classList.add("is-entering");
    }

    function animate(scenario) {
      if (reduced) return;
      let n = 0;
      steps.forEach((step) => {
        if (scenario.active.includes(step.dataset.step)) restart(step, n++);
      });
      Array.from(route.children).forEach((child, i) => child.style.setProperty("--i", i));
      route.classList.remove("is-entering");
      void route.offsetWidth;
      route.classList.add("is-entering");
      movePulse(scenario);
    }

    function movePulse(scenario) {
      if (pulseAnimation) pulseAnimation.cancel();
      const active = steps.filter((step) => scenario.active.includes(step.dataset.step));
      if (active.length < 2 || !pulse.animate) { pulse.style.opacity = "0"; return; }
      const center = (step) => step.offsetTop + step.querySelector(".ah-step-num").offsetTop + 16 - 5;
      const from = center(active[0]);
      const to = center(active[active.length - 1]);
      pulseAnimation = pulse.animate([
        { transform: "translateY(" + from + "px)", opacity: 0 },
        { opacity: 1, offset: 0.12 },
        { opacity: 1, offset: 0.88 },
        { transform: "translateY(" + to + "px)", opacity: 0 }
      ], { duration: 400 + active.length * 520, iterations: Infinity, easing: "ease-in-out" });
    }

    if (!reduced && "IntersectionObserver" in window) {
      scenarioGrid.classList.add("is-motion");
      Array.from(scenarioGrid.children).forEach((card, i) => card.style.setProperty("--i", i));
      const observer = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          scenarioGrid.classList.add("is-visible");
          observer.disconnect();
        });
      }, { threshold: 0.15 });
      observer.observe(scenarioGrid);
    }

    function remember(name) {
      try {
        const url = new URL(window.location.href);
        if (name === "full") url.searchParams.delete("scenario");
        else url.searchParams.set("scenario", name);
        window.history.replaceState(null, "", url);
      } catch (error) { /* the address is not required for the switch to work */ }
    }

    buttons.forEach((button, index) => {
      button.addEventListener("click", () => {
        select(button.dataset.scenario);
        remember(button.dataset.scenario);
      });
      button.addEventListener("keydown", (event) => {
        const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[event.key];
        if (!step && event.key !== "Home" && event.key !== "End") return;
        event.preventDefault();
        const next = event.key === "Home" ? 0
          : event.key === "End" ? buttons.length - 1
          : (index + step + buttons.length) % buttons.length;
        select(buttons[next].dataset.scenario, true);
        remember(buttons[next].dataset.scenario);
      });
    });
    const requested = new URLSearchParams(window.location.search).get("scenario");
    select(scenarios[requested] ? requested : "full");
  })();
</script>
