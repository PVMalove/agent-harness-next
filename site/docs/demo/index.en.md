# Web console

The TUI and the browser are clients of one Console server. Below is an interactive demo: choose a
section in the console menu, and the description and details in the block under it update.

<div class="ah-demo-wrap">
  <iframe class="ah-demo" id="ah-demo-frame" src="console.html#home" title="Web console demo" loading="lazy"></iframe>
</div>

<p class="ah-demo-note">The data is for demonstration: commands do not run, and files do not change.
  If the console did not load, <a href="console.html" target="_blank" rel="noreferrer">open
  the demo on a separate page</a>.</p>

<div class="ah-demo-about" markdown="1">
<img class="ah-demo-about-mascot" src="../../assets/mascot.svg" alt="Voxel mascot of Agent Harness Next" width="120" height="156">

<div class="ah-demo-about-current" aria-live="polite">
<p class="ah-demo-about-kicker">Current screen</p>
<p class="ah-demo-about-title" id="ah-demo-title">Home</p>
<p class="ah-demo-about-text" id="ah-demo-text">Harness health, runtime-store, skills, project context, and recent tasks.</p>
</div>

## What the web console is

The web console is the browser client of the Console server. The TUI and the browser show the same
facts: harness state, tasks, orchestration, reports, and recovery. The console does not replace
the CLI and does not make decisions for a human: it reads the state and shows what happened and
what to do next.

### What it shows

- harness and runtime-store health: checks, warnings, errors, and skips;
- the task board: specs, columns, blockers, acceptance criteria, and the ticket prompt;
- agent activity and orchestration: batches, dispatch, QA lane, and routes;
- role reports and evidence: what was checked, what remains, and where the blocker is;
- publication: candidate, Release Gate, preflight, and the PR/MR draft;
- install and runtime: versions, adapters, containers, and harness commands.

### Screens

| Screen | What it shows |
| --- | --- |
| Home | Harness health, runtime-store, skills, project context, and recent tasks. |
| Diagnostics | Checks, skips, reasons, and the fix command. |
| Update | Diff of managed files, modes, runtime-store migration, and conflicts. |
| Project | The current project, the adoption scheme, the install plan, and checks. |
| Task board | Specs, columns, cards, blockers, and acceptance criteria. |
| Agent activity | Agent sessions, the route, and observed events. |
| Orchestration | Pipeline, batches, dispatch, QA lane, and analytics. |
| Reports | Role reports, evidence, quality, and publication readiness. |
| Publish | Candidate, Release Gate, preflight, and the PR/MR draft. |
| Harness | Install, runtime, adapters, containers, and commands. |
| Repo Map | Index of symbols and links, files, symbols, and the module map. |
| Settings | project.json, orchestration.json, the settings wizard, and history. |
| Help | Screens, commands, hotkeys, and the console limits. |

### How to read the console

On the left are the stable sections, while roles and statuses are filters inside "Agent activity" and "Orchestration".
The header shows the connection state: `online` means that the server responds, but it does not mean
that all checks passed. A skipped check does not count as passed.

The console is read-only: it shows facts and suggests commands, but it does not run them. Decisions about
approve, rerun, publication, and merge stay with a human.

### Limits of the demo

- the data and events are for demonstration, and any match with a real project is accidental;
- commands, approve, publication, and merge do not run;
- files, Git, and `.harness` are not read and not changed;
- no network connection is used: all states switch in memory.
</div>

<script>
  (function () {
    const frame = document.getElementById("ah-demo-frame");
    const title = document.getElementById("ah-demo-title");
    const text = document.getElementById("ah-demo-text");
    const screens = {
      home: ["Home", "Harness health, runtime-store, skills, project context, and recent tasks."],
      diagnostics: ["Diagnostics", "Checks: what was checked, what was skipped, the reasons, and the fix command."],
      "update-harness": ["Update", "Diff of managed files, update modes, runtime-store migration, and conflicts."],
      "open-project": ["Project", "The current project, the project list, the adoption scheme, the install plan, and checks."],
      board: ["Task board", "Specs, columns, cards, blockers, acceptance criteria, and the ticket prompt."],
      "agent-activity": ["Agent activity", "Agent sessions, filters by role and status, the route, and observed events."],
      orchestration: ["Orchestration", "Pipeline, batches, dispatch, QA lane, and orchestration analytics."],
      reports: ["Reports", "Role reports, evidence, quality, and publication readiness."],
      publish: ["Publish", "Candidate, Release Gate, preflight, the PR/MR draft, and evidence."],
      harness: ["Harness", "Install, runtime, adapters, containers, and harness commands."],
      "repo-map": ["Repo Map", "Index of symbols and links, files, symbols, and the module map."],
      configuration: ["Settings", "project.json, orchestration.json, the settings wizard, and change history."],
      help: ["Help", "Screens, commands, hotkeys, and the console limits."]
    };
    let bound = false;

    function update(name) {
      const entry = screens[name] || ["Web console", "Choose a section in the console menu — the description appears here."];
      title.textContent = entry[0];
      text.textContent = entry[1];
    }

    function bind() {
      if (bound || !frame.contentWindow) return;
      bound = true;
      const sync = () => {
        const route = frame.contentWindow.location.hash.slice(1).split("?")[0] || "home";
        update(route);
      };
      frame.contentWindow.addEventListener("hashchange", sync);
      sync();
    }

    frame.addEventListener("load", bind);
    if (frame.contentDocument && frame.contentDocument.readyState === "complete") bind();
  })();
</script>
