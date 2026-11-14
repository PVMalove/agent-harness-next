# Agent prompt blocks

The web console's Task Board builds the "Agent prompt" of a ticket in the planner's `/to-guide`
format. Two of its blocks are fixed text: ARCHITECTURE INVARIANTS and IMPLEMENTATION DISCIPLINE.
For each block the board takes the first source that has it:

1. the epic's `## Architecture invariants` or `## Implementation discipline` section, which
   `/to-tickets` writes into the epic body;
2. the same `##` section of this file, the project-wide default.

The body of a section is copied verbatim up to the next `##` heading. An empty or missing section
leaves the block out. Text outside these two sections is ignored. Fill the sections below with
rules that hold for every epic of this project, or leave a section empty to have no default.

## Architecture invariants

## Implementation discipline
