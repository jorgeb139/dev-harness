# Project Memory and Orchestrated Plans

## Goal

Evolve the harness from a plan-and-checkpoint helper into a portable execution system
that preserves project context, learned project rules, the active plan, and the exact
handoff point between sessions or agents. The system must improve continuity without
storing conversation transcripts or internal reasoning.

## Scope

This change covers project identity, generated technical context, project-scoped memory,
structured plans, execution state, logical phases, role contracts, mode recommendations,
review loops, completion criteria, and plan history. It remains runtime-neutral: the
harness may run with one agent changing roles or with multiple host-provided agents.

It does not implement a vendor-specific agent dispatcher, semantic vector database,
conversation archive, or automatic modification of global harness rules.

## Design Decisions

### 1. Project identity and isolation

Each initialized project stores `.harness/project-identity.json` with:

- project name;
- absolute local root;
- normalized Git remote when available;
- identity schema version;
- context fingerprint and timestamps.

At session start the harness compares the current root, project name, and remote with the
stored identity. A mismatch is a hard stop for reuse of project plans, memory, history, or
active tasks. The user must confirm initialization for the new identity before any old
project state is loaded.

The identity is local path plus project name, enriched by the normalized remote. A missing
remote is valid; a conflicting remote is not silently accepted.

### 2. Project context

Initialization generates `PROJECT-CONTEXT.md` with the project's name, purpose, stack,
runtime, package manager, build and test commands, directory structure, module graph,
entry points, data flows, test topology, deployment notes, and known risks.

`AGENTS.md` remains the source for behavioral rules and links to `PROJECT-CONTEXT.md`,
`ARCHITECTURE.md`, `MUST-DO.md`, the active plan, execution state, and project memory.
`CLAUDE.md` may import `AGENTS.md`, but no vendor-specific file becomes the canonical
source.

The context is loaded at initialization and reused on later sessions. A deterministic
fingerprint detects changes to relevant manifests, commands, structure, and architecture.
The harness reports stale context and offers a refresh; it does not regenerate the full
context on every session.

### 3. Memory and learning

Project memory lives under `.harness/memory/` and is isolated by project identity. Entries
store a stable ID, rule or learning, scope, source, occurrence count, confidence, status,
created/updated timestamps, and supersession links. Secrets, tokens, credentials, and raw
conversation content must never be persisted.

The learning policy is:

- An explicit instruction equivalent to "this must always be done" is promoted directly to
  an active project rule and the user is notified.
- The same correction requested more than once is promoted directly to an active project
  rule, without asking for approval, and the user is notified.
- An uncertain match is recorded as a candidate instead of being promoted automatically.
- A general improvement to the harness itself requires explicit user approval and is kept
  separate from project memory.

Rule precedence is, from strongest to weakest:

```text
current explicit user instruction
> explicit project rule
> learned project memory
> AGENTS.md / CLAUDE.md rules
> general harness skills
> agent defaults
```

Approved global harness improvements are versioned in the harness repository. Project
memory never crosses an identity boundary.

### 4. Plan and execution state

`.harness/plan.json` is the canonical machine-readable plan. It contains the plan ID,
original scope, approved scope, assumptions, impact analysis, logical phases, tasks,
dependencies, owner role, reviewer roles, acceptance criteria, test obligations, evidence,
and change history.

`.harness/execution-state.json` is the mutable execution pointer. It contains the current
phase and task, status, last completed task, next action, branch, verified commit, blockers,
attempt count, selected agent mode, token estimates, and checkpoint metadata.

`docs/plans/ACTIVE-PLAN.md` is a generated human-readable projection of both files. The
runtime updates JSON first and regenerates the Markdown projection, so there is one
operational source of truth and no Markdown parsing requirement for state transitions.

Tasks have stable IDs and statuses. Advancing to a task is rejected unless the task exists,
its dependencies are complete, and the previous task has the required implementation,
review, test, and evidence gates. The current phase and current task are always explicit.

Minor ordering, subtask, or evidence changes may update the draft automatically. Scope,
architecture, data, permissions, or public-contract changes pause execution, preserve the
original plan, record the proposed modification, and request user approval.

### 5. Orchestrator and specialized roles

The initial role is a read-only orchestrator. Before implementation it loads identity,
context, memory, and history; maps affected components; analyzes callers and callees;
checks happy and sad paths; identifies scope boundaries; verifies dependencies; and asks
questions until material uncertainty reaches the 95% confidence gate. It may update a
draft plan and questions, but cannot change code, active rules, or permanent memory before
plan approval.

The role contracts are distinct even when one agent executes them sequentially:

- orchestrator/planner: scope, impact graph, phases, risks, questions, and mode estimate;
- implementer: one approved task and its acceptance criteria;
- security reviewer: secrets, inputs, permissions, data, destructive operations, and
  security regressions;
- regression reviewer: affected flows, baseline, forward/backward compatibility within
  the approved scope, and targeted/full regression evidence;
- test reviewer: unit, integration, E2E, coverage, and test completeness;
- stage validator: aggregate gate before the next logical phase;
- checkpoint/handoff manager: resumable state for the next session or agent;
- retrospective: completed-plan lessons and improvement proposals.

The reviewer roles must confirm that the requested scope is satisfied and that no invented
scope or unsupported behavior was introduced.

### 6. Agent-mode recommendation

The harness never chooses monoagent or multiagent automatically. The orchestrator presents
the user with:

- the recommended mode;
- how monoagent execution would work;
- how multiagent execution would work;
- estimated token ranges for both;
- coordination overhead, risks, and expected benefits;
- the evidence and complexity factors behind the recommendation.

The user chooses the mode. The selected mode, rationale, and estimates are persisted in
the plan and execution state. If the scope changes enough to alter the recommendation,
the harness reports the new estimates and waits for a new user decision. Estimates are
explicitly approximate; actual usage is recorded when the host runtime exposes it.

### 7. Review and test loop

Every logical task follows:

```text
implement -> security review -> regression review -> test review
          -> corrections -> repeat until green -> checkpoint -> next task
```

Unit tests target at least 90% coverage of changed production code. The target may be 100%
when the marginal cost is low and the tests remain meaningful. Integration tests are
required at real module or service boundaries when applicable. E2E tests are required for
critical UI, API, or deployable user journeys. If a layer is not applicable, the plan must
record evidence explaining why.

The same failing blocker is retried up to three times. After the third failure, the task
becomes `blocked`, the handoff is persisted, and the user is asked how to proceed.

### 8. Completion and history

`COMPLETION-POLICY.md` defines the exact criteria for a task, phase, and plan to be
complete. A task requires acceptance criteria, implementation evidence, required tests,
security and regression reviews, and a valid checkpoint. A phase additionally requires
all its tasks to be complete and the stage validator to be green. A plan additionally
requires all phases complete, no unresolved blockers, a final validation, and a
retrospective.

Completed plans are archived as one Markdown plan per plan ID under
`docs/plans/history/`, together with its final structured state, handoff, evidence index,
and retrospective. The archive contains execution facts, not conversation transcripts or
internal reasoning.

## Lifecycle

```text
initialize
  -> validate project identity
  -> load or refresh context
  -> load project memory and active state
  -> orchestrator analysis and questions
  -> user approves plan and chooses agent mode
  -> implement task
  -> security/regression/test review loop
  -> checkpoint and mark task complete
  -> validate phase and advance
  -> archive completed plan and run retrospective
```

## Safety and Failure Handling

- Missing, malformed, stale, or cross-project state fails closed before implementation.
- Identity mismatch never falls back to another project's memory or active plan.
- Destructive changes, permission changes, data changes, and public-contract changes require
  the existing destructive-change gate and explicit user authorization.
- Memory and context writes are sanitized and checked for secrets.
- Unknown test commands or missing evidence are gaps, never passing results.
- State writes remain atomic and recoverable.
- Hooks enforce mechanical invariants; Markdown instructions alone are not treated as
  enforcement.

## Alternatives Considered

1. **Rules and Markdown only:** lowest implementation cost, but weak validation, poor
   task identity, and high drift risk.
2. **Structured plan plus state and generated Markdown:** recommended. It preserves human
   readability, enables deterministic transitions, supports resumable handoffs, and works
   with one agent or multiple host agents.
3. **Mandatory multiagent runtime:** stronger isolation in some environments, but higher
   token cost, coordination complexity, and vendor coupling. It is intentionally left as
   an adapter rather than a requirement.

## Acceptance Criteria

- A fresh session validates project identity before loading project state.
- A new project cannot inherit another project's plan, memory, or history.
- Initialization creates or refreshes a reusable technical context with a detectable
  fingerprint.
- The orchestrator produces an impact map, happy/sad path analysis, scope boundary,
  questions, confidence assessment, and monoagent/multiagent token estimates before work.
- The user explicitly chooses the execution mode and the decision is recoverable from files.
- Plan tasks are structured, sectioned, dependency-aware, and validated before advancing.
- A reviewer loop enforces security, regression, test completeness, and scope adherence.
- Repeated corrections become project rules with notification and no approval prompt.
- Every completed plan has a standalone Markdown history entry and completion evidence.
- State and plan updates survive a session or agent change without requiring conversation
  history.
