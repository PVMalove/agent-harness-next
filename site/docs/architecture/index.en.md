# Architecture

Policy and execution are separate. Python makes decisions. The Rust runtime stores operational state
and starts processes. Git stays the owner of history and candidates.

<div class="ah-cards">
  <a class="ah-card" href="overview/">
    <span class="i">◇</span>
    <b>Overview</b>
    <span>Layers and ownership, the delivery model, the Discovery Pipeline, and trust boundaries.</span>
  </a>
  <a class="ah-card" href="runtime/">
    <span class="i">⌁</span>
    <b>Rust runtime</b>
    <span>The process and IPC, the runtime store, the supervisor and OCI, reconcile, verification, and security.</span>
  </a>
  <a class="ah-card" href="../getting-started/">
    <span class="i">✓</span>
    <b>Quick start</b>
    <span>Requirements, installation, connecting to a project, and the first commands.</span>
  </a>
</div>

## How to read

Start with the overview. It explains who owns what and why the runtime store is the only writer of
operational state. Then go to the Rust runtime page, which covers the process, IPC, the store, the
supervisor, and the failure domains. The full normative contracts stay in the repository ADRs. The
public pages explain the model and do not replace the ADRs.
