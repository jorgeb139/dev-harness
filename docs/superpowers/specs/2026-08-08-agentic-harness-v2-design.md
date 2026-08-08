# Agentic Harness v2 Design

## Goal

Convert dev-harness from a collection of behavioral rules into a portable execution
system that can plan, delegate, validate, checkpoint, and resume work without losing the
exact next action between agent sessions.

## Scope

The harness will provide a runtime-neutral orchestration contract. It will not hard-code a
Claude, Codex, or vendor-specific agent API. Instead, it will persist the execution state,
define specialized role instructions, and expose deterministic commands that a host agent
or plugin hook can call.

## Architecture

### 1. Persistent state

`docs/plans/ACTIVE-PLAN.md` remains the human-readable plan. A companion machine-readable
state file stores the current phase, task, owner, branch, last verified commit, evidence,
blockers, and next action. The state transitions are:

```text
pending -> in_progress -> blocked -> in_progress -> completed
```

Invalid transitions fail closed. Every checkpoint records a timestamp, task identifier,
test command, result summary, and the next action. Completed plans move their state and
handoff into `docs/plans/done/`.

### 2. Specialized roles

The harness adds role skills with explicit inputs and outputs:

- `planning-director`: discovers affected flows, components, dependencies, contracts,
  data, risks, unknowns, and questions before implementation.
- `security-review`: reviews secrets, permissions, inputs, data, migrations, and
  destructive operations before and after implementation.
- `regression-review`: identifies affected behavior, establishes a baseline, runs targeted
  and full regression checks, and records failures without disabling tests.
- `test-strategy`: selects unit, integration, and E2E layers from the architecture and
  sets a cost-aware coverage target.
- `checkpoint-handoff`: writes a resumable state snapshot for the next agent.

The host runtime may map these roles to real subagents. When it cannot spawn subagents,
the main agent executes the same role contracts sequentially.

### 3. Test policy

Unit tests target at least 90% coverage for new or changed production code. The target may
rise to 100% when the marginal cost is low and tests remain behavioral rather than
artificial. Integration tests are required at real module or service boundaries. E2E tests
are required for critical user journeys when the project has a UI, public API, or complete
deployable flow. Pure documentation, configuration, or isolated algorithm changes do not
inherit an artificial E2E requirement.

Coverage tools and commands must be discovered from the project before use; the harness
must not assume a package manager, test runner, or coverage provider.

### 4. Execution loop

```text
init -> discover -> plan -> approve -> choose mode -> start task
     -> implement -> security -> regression -> test strategy -> checkpoint
     -> next task | blocked | complete
```

The planning director must resolve material uncertainty using the 95% confidence gate.
The stage validator can close a stage only when security, regression, test objectives, and
the handoff state are all green.

## Error handling and safety

- Missing or malformed state is a hard stop before implementation.
- An unknown test command is recorded as an unresolved verification gap, not treated as
  passing.
- High-risk changes require explicit user confirmation and rollback evidence.
- State writes are atomic so an interrupted process does not leave a half-written record.
- Hooks remain fail-open for unrelated sessions, but fail closed when a project declares an
  active plan and attempts to advance without a valid checkpoint.

## Alternatives considered

1. **Skills only:** smallest change, but relies on model compliance and has weak recovery.
2. **Skills plus Markdown handoff:** improves continuity but cannot reliably validate state.
3. **Portable state machine plus role skills and hooks:** recommended. It adds real recovery
   and validation while keeping the agent backend replaceable.

## Success criteria

- A new session can identify the exact active task, owner, verified commit, blocker, and next
  action from files alone.
- The planner produces an impact map and questions before implementation starts.
- Security, regression, and test strategy are distinct review gates.
- Unit coverage policy is explicit and cost-aware, with integration/E2E selected by evidence.
- State transitions and malformed plans are tested without external dependencies.
