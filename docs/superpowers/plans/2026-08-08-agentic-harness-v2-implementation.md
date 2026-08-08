# Agentic Harness v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a portable execution layer that persists plan state, delegates specialized review roles, enforces evidence gates, and resumes work from an exact handoff.

**Architecture:** A Python-standard-library state CLI owns atomic JSON state and Markdown handoffs. Skills define the planner, security, regression, test-strategy, and checkpoint contracts. Existing shell hooks and plan skills call the state CLI without binding the harness to a vendor-specific agent API.

**Tech Stack:** Bash, Python 3 standard library, Markdown, JSON, existing Claude Code hooks, Codex/Claude skills.

## Global Constraints

- Preserve runtime neutrality: no new external package or vendor-specific agent SDK.
- Unit coverage policy targets at least 90% of new or changed production code; 100% only when cheap and behavioral.
- Integration tests are required at real module/service boundaries; E2E is required only for critical complete user flows.
- High-risk changes require security evidence, rollback evidence, and explicit user confirmation.
- State writes must be atomic and invalid state transitions must fail closed.
- All work stays on `codex/agentic-harness-v2`; integration remains PR -> `develop` -> `main`.

## Stage 1: State engine and resumable handoff

**Success criteria:** `harness-state.py` can initialize, validate, start, checkpoint, block, complete, show, and resume a plan without external dependencies; invalid transitions fail; state and handoff survive a fresh process.

### Task 1: State contract tests

**Files:**
- Create: `tests/test-harness-state.sh`
- Test target: `scripts/harness-state.py`

- [ ] Write failing shell tests for `init`, `show`, `start`, `checkpoint`, `block`, `resume`, and `complete` using a temporary project directory.
- [ ] Assert required fields: `status`, `plan_id`, `phase`, `task`, `owner`, `branch`, `last_verified_commit`, `next_action`, `evidence`, `blockers`, `updated_at`, and `history`.
- [ ] Assert invalid transitions and missing required values return non-zero without corrupting the prior JSON file.
- [ ] Run `bash tests/test-harness-state.sh`; expected result is failure because the CLI does not exist yet.

### Task 2: Implement the atomic state CLI

**Files:**
- Create: `scripts/harness-state.py`
- Modify: `tests/test-harness-state.sh` only if the observed failure exposes an incorrect test expectation.

**Interface:**

```text
python3 scripts/harness-state.py init --plan-id ID --plan-file PATH --branch BRANCH --owner OWNER --phase N --task N.M --next-action TEXT
python3 scripts/harness-state.py start --task N.M --next-action TEXT
python3 scripts/harness-state.py checkpoint --commit SHA --test-command CMD --result TEXT --next-action TEXT
python3 scripts/harness-state.py block --reason TEXT --next-action TEXT
python3 scripts/harness-state.py resume --next-action TEXT
python3 scripts/harness-state.py complete --commit SHA --test-command CMD --result TEXT
python3 scripts/harness-state.py show [--json]
python3 scripts/harness-state.py validate
```

- [ ] Implement JSON state version `1` with the required fields and valid statuses `pending`, `in_progress`, `blocked`, and `completed`.
- [ ] Implement transition validation: `pending -> in_progress`, `in_progress -> blocked|completed`, and `blocked -> in_progress`; reject all other transitions.
- [ ] Implement atomic writes with a temporary file in the same directory followed by `os.replace`, preserving the previous file when validation fails.
- [ ] Append a history event for every successful transition and checkpoint with ISO-8601 UTC timestamp.
- [ ] Generate `docs/plans/ACTIVE-PLAN.HANDOFF.md` from the current state on every successful mutation, including exact next action and blockers.
- [ ] Run `bash tests/test-harness-state.sh`; expected result is `ALL OK`.

### Task 3: State-engine regression coverage

**Files:**
- Modify: `tests/test-harness-state.sh`

- [ ] Add tests for interrupted writes simulated by an invalid update and verify the previous valid state remains readable.
- [ ] Add tests for malformed JSON and missing handoff fields; `validate` must fail with a useful error.
- [ ] Run `bash tests/test-harness-state.sh` and `bash tests/validate.sh`; both must pass before Stage 1 closes.

## Stage 2: Director, safety, regression, and test-strategy roles

**Success criteria:** Every role has explicit inputs, outputs, evidence requirements, and handoff behavior; the plan template records impact and test decisions.

### Task 4: Planning and security role skills

**Files:**
- Create: `skills/planning-director/SKILL.md`
- Create: `skills/security-review/SKILL.md`

- [ ] Define `planning-director` as a mandatory pre-implementation role requiring repository discovery, flow/component/dependency/contract/data impact mapping, uncertainty inventory, and 95% verification or user questions.
- [ ] Define `security-review` as a pre- and post-implementation gate covering secrets, inputs, permissions, authentication, data, migrations, destructive operations, dependencies, and rollback.
- [ ] Require each role to write evidence and unresolved blockers into the active plan or handoff, never only into conversation text.

### Task 5: Regression and test-strategy role skills

**Files:**
- Create: `skills/regression-review/SKILL.md`
- Create: `skills/test-strategy/SKILL.md`

- [ ] Define `regression-review` to establish a baseline, map affected flows, run targeted tests and the full available suite, and prohibit disabling tests to obtain green output.
- [ ] Define `test-strategy` to select unit, integration, and E2E tests from the project architecture and to discover the project’s real commands before running them.
- [ ] Encode the coverage rule: at least 90% of changed production code; target 100% only when the marginal cost is low and tests remain behavioral.
- [ ] Encode integration requirements for real boundaries and E2E requirements for critical complete user journeys, with explicit not-applicable evidence when no such flow exists.

### Task 6: Checkpoint role and plan schema

**Files:**
- Create: `skills/checkpoint-handoff/SKILL.md`
- Create: `templates/HANDOFF-template.md`
- Modify: `templates/PLAN-template.md`

- [ ] Define checkpoint timing after every task, before context compaction, before session end, and when blocked.
- [ ] Add plan fields for impact map, open questions, security status, regression status, test layers, coverage target, current state file, and handoff file.
- [ ] Add a handoff template with completed work, failed approaches, evidence, blockers, last verified commit, and exact next action.

## Stage 3: Orchestration, hooks, initialization, and validation

**Success criteria:** A fresh session prints the active execution state, the plan cannot advance without required role evidence, initialization installs the state CLI, and the complete harness suite passes.

### Task 7: Integrate lifecycle skills and hooks

**Files:**
- Modify: `skills/plan-manager/SKILL.md`
- Modify: `skills/stage-validator/SKILL.md`
- Modify: `scripts/session-start.sh`
- Modify: `scripts/pre-commit-gate.sh`
- Modify: `hooks/hooks.json`

- [ ] Require `planning-director` before plan approval and `agent-orchestrator` after approval.
- [ ] Require `security-review`, `regression-review`, `test-strategy`, and `checkpoint-handoff` before stage closure.
- [ ] Make session start show state and handoff summaries when configured, while preserving fail-open behavior for projects without the harness.
- [ ] Block commits on a declared active plan when state is malformed or the current task lacks a checkpoint, without blocking unrelated projects.

### Task 8: Initialize and document the orchestrator

**Files:**
- Modify: `commands/init.md`
- Modify: `README.md`
- Modify: `.claude-plugin/plugin.json`
- Modify: `.codex-plugin/plugin.json`
- Modify: `tests/validate.sh`
- Modify: `tests/test-session-start.sh`
- Modify: `tests/test-pre-commit-gate.sh`
- Modify: `tests/test-harness-state.sh`
- Create: `templates/CLAUDE.md`

- [ ] Copy the state CLI, `AGENTS.md`, and `CLAUDE.md` import template during initialization without overwriting existing project files.
- [ ] Document the full lifecycle, role mapping, recovery commands, coverage policy, and when integration/E2E tests are required.
- [ ] Bump both plugin manifests from `0.2.1` to `0.3.0` for the new orchestration architecture.
- [ ] Extend validation to check every new skill, template, command, state schema, and version.

### Task 9: Full verification and handoff

**Files:**
- Modify: `docs/plans/ACTIVE-PLAN.md`
- Create: `docs/plans/done/2026-08-08-agentic-harness-v2.md`

- [ ] Run `bash tests/validate.sh`, `git diff --check`, and every focused test.
- [ ] Run `.harness/health.sh` if configured; otherwise record that it is not applicable to this plugin repository.
- [ ] Complete security, regression, test-strategy, and handoff evidence in the active plan.
- [ ] Move the completed plan and state artifacts to `docs/plans/done/`.
