# Reference

Commands and project configuration, process labels, hooks, and the skill catalog. Each section answers the
question "how is it configured", not "how do I do it": step-by-step scenarios live in the guides.

<div class="ah-cards ah-cards--four">
  <a class="ah-card" href="cli/">
    <span class="i">⌘</span>
    <b>CLI and configuration</b>
    <span>Install and update commands, configuration fields, health, memory, project graph.</span>
  </a>
  <a class="ah-card" href="labels/">
    <span class="i">◇</span>
    <b>Labels</b>
    <span>Label axes, the single-state-label rule, and pipeline transitions.</span>
  </a>
  <a class="ah-card" href="hooks/">
    <span class="i">⌁</span>
    <b>Hooks</b>
    <span>Profiles, critical guards, and the table of connected checks.</span>
  </a>
  <a class="ah-card" href="skills/">
    <span class="i">✓</span>
    <b>Skills</b>
    <span>Overrides, the upstream set, and first-party additions.</span>
  </a>
</div>

## Glossary

<div class="ah-ref-glossary" id="ah-ref-glossary">
  <div class="ah-ref-glossary-head">
    <div>
      <b>All project terms</b>
      <span>Definitions, English equivalents, and notes on how these concepts should not be named. A dictionary for documentation, the CLI, and configuration.</span>
    </div>
    <a class="md-button md-button--primary" href="glossary/">Open the glossary</a>
  </div>
  <form class="ah-ref-glossary-search" action="glossary/" method="get" role="search">
    <input type="search" name="term" placeholder="Find a term: capability, lease, supervisor…" aria-label="Search the glossary" autocomplete="off" spellcheck="false">
    <button type="submit">Search</button>
  </form>
  <div class="ah-ref-glossary-links" role="group" aria-label="Term categories">
    <a href="glossary/?category=architecture">Architecture and code <span>42</span></a>
    <a href="glossary/?category=files">File system and runtime <span>23</span></a>
    <a href="glossary/?category=tasks">Tasks and artifacts <span>45</span></a>
    <a href="glossary/?sort=az">Alphabetical A–Z</a>
  </div>
</div>

## How it works

All commands take the path to the target project and do not depend on the current directory. The project
configuration is a strict contract: an unknown field stops the work and is not ignored. For details, see
the [CLI reference](cli.md).
