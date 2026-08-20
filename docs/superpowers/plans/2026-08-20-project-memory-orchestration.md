# Project Memory and Orchestrated Plans Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add project identity, reusable context, learned project memory, structured plans, resumable execution state, role-based review loops, and plan history to dev-harness.

**Architecture:** Keep Python standard-library modules as the deterministic runtime and Bash as the portable hook/test layer. Store the machine source of truth in `.harness/plan.json` and `.harness/execution-state.json`, generate `docs/plans/ACTIVE-PLAN.md` for humans, and expose specialized role contracts through skills. One host agent may execute the roles sequentially, while a host runtime that supports subagents may map them to separate agents; the user always chooses the mode after seeing the recommendation and token estimates.

**Tech Stack:** Python 3 standard library, Bash, JSON, Markdown, Git, existing Claude Code hooks, Codex-discoverable skills.

## Global Constraints

- The current explicit user instruction overrides project rules, learned project memory, `AGENTS.md`/`CLAUDE.md`, general skills, and agent defaults.
- Project memory is isolated by project identity; secrets, credentials, tokens, transcripts, and internal reasoning are never persisted.
- The orchestrator must reach the existing 95% confidence gate by evidence or questions before implementation.
- The user chooses monoagent, mixed, or multiagent execution after receiving the recommendation, operation summary, risks, and approximate token ranges for each option.
- Unit tests target at least 90% coverage of changed production code; target 100% when the marginal cost is low and tests remain meaningful.
- Integration tests cover real module/service boundaries when applicable; E2E tests cover critical UI, API, or deployable journeys when applicable.
- The same blocker is retried at most three times before the task becomes blocked with a persisted handoff.
- State and memory writes are atomic, identity-checked, and fail closed on malformed or cross-project data.
- No new runtime dependency is added; use Python and Bash already required by the repository.
- Version both plugin manifests to `0.4.0` when the implementation is complete.

---

## File Map

### New files

- `scripts/harness_store.py`: atomic JSON/text writes, file locking, UTC timestamps, fingerprints, and secret-pattern detection.
- `scripts/harness_state.py`: importable execution-state implementation extracted from the current hyphenated CLI.
- `scripts/harness_context.py`: identity discovery, project fingerprinting, deterministic context inventory, and context Markdown rendering.
- `scripts/harness_memory.py`: project-rule schema, duplicate-correction matching, promotion, precedence metadata, and notification records.
- `scripts/harness_plan.py`: plan schema, phase/task validation, generated Markdown projection, mode decision persistence, and archive preparation.
- `scripts/harness-project.py`: portable CLI wrapper for `init`, `identity`, `context`, and `memory` operations.
- `scripts/harness-plan.py`: portable CLI wrapper for plan validation, rendering, mode recording, and archive operations.
- `templates/PROJECT-CONTEXT.md`: context document template with explicit unknown/not-detected markers.
- `templates/COMPLETION-POLICY.md`: task, phase, and plan completion gates.
- `templates/MEMORY-README.md`: project-memory storage rules and precedence.
- `skills/project-context/SKILL.md`: context initialization, fingerprint, and refresh contract.
- `skills/project-memory/SKILL.md`: learning, promotion, notification, and identity-isolation contract.
- `tests/test-harness-store.sh`: persistence and secret-scan tests.
- `tests/test-harness-project.sh`: identity, context, and memory lifecycle tests.
- `tests/test-harness-plan.sh`: plan schema, rendering, task gates, mode decision, and archive tests.

### Modified files

- `scripts/harness-state.py`: remain the stable executable entry point and delegate to `harness_state.py`.
- `scripts/session-start.sh`: validate identity, load context/memory summary, and report structured plan state.
- `scripts/pre-commit-gate.sh`: validate identity, plan, execution state, and generated Markdown before commit.
- `commands/init.md`: install every required runtime/template file and initialize identity/context/plan directories.
- `templates/AGENTS.md`: reference context, memory, plan, state, completion policy, and role contracts.
- `templates/CLAUDE.md`: preserve generic import of `AGENTS.md`.
- `templates/PLAN-template.md`: describe generated projection and structured plan fields.
- `templates/HANDOFF-template.md`: include identity, phase/task, mode choice, blockers, and review evidence.
- `templates/MUST-DO.md`: document automatic promotion of repeated project corrections and notification.
- `skills/agent-orchestrator/SKILL.md`: make recommendation-only behavior and user choice explicit.
- `skills/planning-director/SKILL.md`: require backward/forward impact graph, happy/sad paths, and scope boundary.
- `skills/plan-manager/SKILL.md`: use `.harness/plan.json` and `.harness/execution-state.json` as operational sources.
- `skills/stage-validator/SKILL.md`: enforce task/phase gates from structured state.
- `skills/checkpoint-handoff/SKILL.md`: persist the new state and generated projection.
- `skills/retrospective/SKILL.md`: distinguish project-rule promotion from harness-wide approval.
- `README.md`: document initialization, memory, context, plan files, execution modes, archive, and version `0.4.0`.
- `tests/test-harness-state.sh`: test task-ID/dependency/reviewer gates and new state paths.
- `tests/test-session-start.sh`: test identity/context/memory/state initialization and mismatch behavior.
- `tests/test-pre-commit-gate.sh`: test malformed/cross-project plan and state rejection.
- `tests/validate.sh`: include all new files, schemas, skills, commands, wrappers, and version assertions.
- `.claude-plugin/plugin.json`: bump version to `0.4.0`.
- `.codex-plugin/plugin.json`: bump version to `0.4.0`.

## Phase 1: Persistent Foundations

**Objective:** Provide tested, reusable primitives for atomic state, identity, context, and safe file handling.

**Success evidence:** New shell tests pass, malformed JSON fails closed, secret-like content is rejected, and an initialized temporary project can be identified and fingerprinted without external packages.

### Task 1.1: Extract shared storage primitives

**Files:**
- Create: `scripts/harness_store.py`
- Create: `tests/test-harness-store.sh`
- Modify: `scripts/harness-state.py`
- Create: `scripts/harness_state.py`

**Interfaces:**
- `harness_store.py` produces `utc_now() -> str`, `load_json(path: Path) -> dict`, `atomic_write_json(path: Path, value: object) -> None`, `atomic_write_text(path: Path, content: str) -> None`, `locked(path: Path) -> ContextManager[None]`, `fingerprint_files(root: Path, relative_paths: Iterable[str]) -> str`, and `find_sensitive_patterns(text: str) -> list[str]`.
- `harness_state.py` consumes the storage functions and produces `main(argv: list[str] | None = None) -> int`; `scripts/harness-state.py` delegates to it without changing the executable command path.

- [ ] **Step 1: Write failing storage tests**

  In `tests/test-harness-store.sh`, create a temporary project and run a Python test block that imports the new module from `scripts/`. Assert that `atomic_write_json` creates valid JSON, a second write replaces the full file, `load_json` rejects malformed JSON with `ValueError`, and `fingerprint_files` changes when a listed file changes.

- [ ] **Step 2: Run the focused test and verify failure**

  Run: `bash tests/test-harness-store.sh`

  Expected: `FAIL` because `scripts/harness_store.py` does not exist yet.

- [ ] **Step 3: Implement the storage module**

  Move the current `now`, `atomic_write`, and `StateLock` behavior into `harness_store.py`, preserve UTF-8 and `os.replace`, add `fsync`, use SHA-256 for fingerprints, and return only pattern names from `find_sensitive_patterns`. Patterns must cover common API keys, bearer tokens, private-key headers, passwords, and credential-bearing URLs without storing the matching value.

- [ ] **Step 4: Extract the state implementation without behavior drift**

  Move the current state functions and parser into `scripts/harness_state.py`, import storage primitives, and replace `scripts/harness-state.py` with:

  ```python
  #!/usr/bin/env python3
  from harness_state import main

  if __name__ == "__main__":
      raise SystemExit(main())
  ```

- [ ] **Step 5: Run focused and existing state tests**

  Run: `bash tests/test-harness-store.sh && bash tests/test-harness-state.sh`

  Expected: `ALL OK` from both scripts.

- [ ] **Step 6: Commit the independently testable foundation**

  ```bash
  git add scripts/harness_store.py scripts/harness_state.py scripts/harness-state.py tests/test-harness-store.sh
  git commit -m "refactor: extract harness storage primitives"
  ```

### Task 1.2: Add identity and deterministic project context

**Files:**
- Create: `scripts/harness_context.py`
- Create: `scripts/harness-project.py`
- Create: `templates/PROJECT-CONTEXT.md`
- Create: `tests/test-harness-project.sh`

**Interfaces:**
- `harness_context.py` produces `discover_identity(root: Path) -> dict`, `validate_identity(root: Path, stored: dict) -> list[str]`, `context_fingerprint(root: Path) -> str`, `build_context_inventory(root: Path) -> dict`, and `render_context(inventory: dict) -> str`.
- `scripts/harness-project.py identity init|check` writes `.harness/project-identity.json`; `context init|check|refresh` writes `PROJECT-CONTEXT.md`; commands return non-zero on identity mismatch or malformed files.

- [ ] **Step 1: Write failing identity/context tests**

  In `tests/test-harness-project.sh`, create temporary Git-like projects with a package manifest, test directory, and README. Assert that identity initialization records the absolute root and project name, context rendering includes detected files and explicit unknown markers, a changed manifest changes the fingerprint, and `identity check` rejects a copied identity whose root or remote differs.

- [ ] **Step 2: Run the focused test and verify failure**

  Run: `bash tests/test-harness-project.sh`

  Expected: `FAIL` because the project CLI and context module do not exist yet.

- [ ] **Step 3: Implement identity discovery**

  Derive the project name from the nearest directory unless a manifest provides a name. Read `git rev-parse --show-toplevel` and `git config --get remote.origin.url` when available, normalize the remote by removing credentials and trailing `.git`, and store path plus name plus remote. Treat a missing remote as valid and any conflicting remote as a mismatch.

- [ ] **Step 4: Implement context inventory and rendering**

  Inventory only deterministic facts: manifests, common runtime files, top-level directories, test directories, executable health/build/test scripts, and detected commands. Render unknown purpose, deployment, and risk fields as `Not detected; user/agent must verify`, never as invented facts. Include schema version, identity ID, fingerprint, generated timestamp, and refresh instructions.

- [ ] **Step 5: Implement the portable project CLI**

  Make `scripts/harness-project.py` import the context module from its own directory, parse `identity` and `context` subcommands, create `.harness/`, and write files atomically. `identity check` must exit `2` on mismatch; `context check` must report `fresh` or `stale` without rewriting.

- [ ] **Step 6: Run the focused test and shell syntax checks**

  Run: `bash tests/test-harness-project.sh && python3 -m py_compile scripts/harness_context.py scripts/harness-project.py`

  Expected: `ALL OK` and no compiler output.

- [ ] **Step 7: Commit the context deliverable**

  ```bash
  git add scripts/harness_context.py scripts/harness-project.py templates/PROJECT-CONTEXT.md tests/test-harness-project.sh
  git commit -m "feat: add project identity and context"
  ```

## Phase 2: Memory and Structured Plans

**Objective:** Make learned rules, phases, tasks, dependencies, evidence, and generated plans deterministic and resumable.

**Success evidence:** A temporary project can record an explicit always-rule, auto-promote a repeated correction, reject a cross-project memory load, validate task dependencies, render the active plan, and reject an invalid state advance.

### Task 2.1: Implement project memory and learning promotion

**Files:**
- Create: `scripts/harness_memory.py`
- Create: `templates/MEMORY-README.md`
- Modify: `scripts/harness-project.py`
- Modify: `tests/test-harness-project.sh`

**Interfaces:**
- `harness_memory.py` produces `memory_path(root: Path) -> Path`, `load_memory(root: Path) -> dict`, `record_learning(root: Path, text: str, source: str, explicit_always: bool = False) -> dict`, `record_correction(root: Path, text: str) -> dict`, `promote_repeated_correction(root: Path, text: str) -> dict`, and `precedence() -> list[str]`.
- Each entry uses `id`, `rule`, `scope`, `source`, `occurrences`, `confidence`, `status`, `created_at`, `updated_at`, `project_identity`, and optional `supersedes`/`notification` fields.

- [ ] **Step 1: Write failing memory tests**

  Extend `tests/test-harness-project.sh` with assertions that an explicit always-rule becomes active immediately, the second equivalent correction becomes active without an approval flag, the command emits a notification containing the rule ID, an uncertain correction remains `candidate`, secrets are rejected, and a memory created under a different identity cannot be loaded.

- [ ] **Step 2: Run the focused test and verify failure**

  Run: `bash tests/test-harness-project.sh`

  Expected: `FAIL` because no memory schema or CLI command exists.

- [ ] **Step 3: Implement normalized correction matching**

  Normalize only whitespace, case, punctuation, and common Spanish/English approval phrases; keep the original rule text for display. Match exact normalized hashes first. If the similarity is ambiguous, create a candidate and do not promote it. Never use an opaque semantic service or store conversation history.

- [ ] **Step 4: Implement safe promotion and notification**

  Write entries with atomic storage after scanning the rule text for sensitive patterns. For explicit `always`, set `status` to `active` and `source` to `explicit_always`. For a repeated exact correction, set `status` to `active`, increment `occurrences`, set `source` to `repeated_correction`, and print `MEMORY UPDATED: ...` without asking for approval. Keep harness-wide proposals outside this file.

- [ ] **Step 5: Expose project CLI memory commands**

  Add `memory list`, `memory always --text`, and `memory correction --text` to `scripts/harness-project.py`. Each command must validate identity before reading or writing `.harness/memory/`.

- [ ] **Step 6: Run focused tests and syntax checks**

  Run: `bash tests/test-harness-project.sh && python3 -m py_compile scripts/harness_memory.py scripts/harness-project.py`

  Expected: `ALL OK` and no compiler output.

- [ ] **Step 7: Commit the memory deliverable**

  ```bash
  git add scripts/harness_memory.py scripts/harness-project.py templates/MEMORY-README.md tests/test-harness-project.sh
  git commit -m "feat: persist project learning rules"
  ```

### Task 2.2: Add canonical plan JSON and generated Markdown

**Files:**
- Create: `scripts/harness_plan.py`
- Create: `scripts/harness-plan.py`
- Modify: `scripts/harness_state.py`
- Modify: `scripts/harness-state.py`
- Create: `tests/test-harness-plan.sh`
- Modify: `tests/test-harness-state.sh`

**Interfaces:**
- `harness_plan.py` produces `load_plan(path: Path) -> dict`, `validate_plan(plan: dict) -> None`, `task_index(plan: dict) -> dict[str, dict]`, `render_markdown(plan: dict, state: dict | None) -> str`, `record_mode_decision(plan_path: Path, state_path: Path, decision: dict) -> None`, and `archive_plan(root: Path, plan: dict, state: dict, handoff: str) -> Path`.
- `harness_state.py` consumes `plan_path` and produces `validate_task_transition(value: dict, plan: dict, target_phase: str, target_task: str) -> None`; `advance` must reject unknown task IDs, incomplete dependencies, and missing review evidence.

- [ ] **Step 1: Write failing plan tests**

  In `tests/test-harness-plan.sh`, create a JSON plan with two phases and dependent tasks. Assert that the valid plan loads, an unknown task ID fails, a dependency advance fails before completion, `render_markdown` contains the current-task marker and section checkboxes, mode recording persists recommendation/choice/estimates, and `archive_plan` writes one Markdown history file plus structured state.

- [ ] **Step 2: Run the focused test and verify failure**

  Run: `bash tests/test-harness-plan.sh`

  Expected: `FAIL` because the plan module and JSON files do not exist.

- [ ] **Step 3: Implement schema validation**

  Require `schema_version`, `plan_id`, `original_scope`, `approved_scope`, `phases`, `impact_analysis`, `mode_options`, and `history`. Require every phase to have a stable ID, ordered tasks, and measurable objectives. Require every task to have an ID, status, owner role, reviewer roles, dependencies, acceptance criteria, test obligations, and evidence.

- [ ] **Step 4: Implement generated Markdown projection**

  Render plan metadata, current phase/task, mode recommendation and user choice, scope, impact graph, questions, each logical section, task checkboxes, acceptance criteria, evidence, review statuses, and phase validation. Escape user-provided Markdown-sensitive text and mark the file as generated.

- [ ] **Step 5: Integrate task validation with the state machine**

  Add `--plan-json` to the state CLI. On `advance`, load and validate the plan before mutating state. Require the current task to contain an implementation checkpoint and green security, regression, and test evidence. Preserve existing atomic writes and invalid-transition errors.

- [ ] **Step 6: Implement plan CLI and archive**

  Add `plan validate`, `plan render`, `plan mode`, and `plan archive` to `scripts/harness-plan.py`. `plan archive` must refuse incomplete plans, write `docs/plans/history/<plan-id>.md`, copy final JSON/state/handoff/evidence metadata, and leave no active pointer for a completed plan.

- [ ] **Step 7: Run focused and state tests**

  Run: `bash tests/test-harness-plan.sh && bash tests/test-harness-state.sh`

  Expected: both scripts print `ALL OK`; the existing state lifecycle remains valid while invalid task transitions now fail.

- [ ] **Step 8: Commit the structured plan deliverable**

  ```bash
  git add scripts/harness_plan.py scripts/harness-plan.py scripts/harness_state.py scripts/harness-state.py tests/test-harness-plan.sh tests/test-harness-state.sh
  git commit -m "feat: add structured plans and task gates"
  ```

## Phase 3: Initialization, Hooks, and Role Contracts

**Objective:** Make every new project initialize the persisted context correctly and make all host agents follow the same orchestration and review contracts.

**Success evidence:** Initialization creates all required files without overwriting user files, session start fails closed on identity mismatch, pre-commit rejects malformed active state, and skills describe the same persisted workflow.

### Task 3.1: Upgrade initialization and templates

**Files:**
- Modify: `commands/init.md`
- Modify: `templates/AGENTS.md`
- Modify: `templates/CLAUDE.md`
- Modify: `templates/PLAN-template.md`
- Modify: `templates/HANDOFF-template.md`
- Modify: `templates/MUST-DO.md`
- Create: `templates/COMPLETION-POLICY.md`
- Modify: `tests/validate.sh`

**Interfaces:**
- `commands/init.md` consumes the new `harness-project.py` and `harness-plan.py` wrappers and produces `.harness/project-identity.json`, `PROJECT-CONTEXT.md`, `.harness/memory/`, `.harness/plan.json`, `.harness/execution-state.json`, generated `docs/plans/ACTIVE-PLAN.md`, and completion policy without overwriting existing project files.

- [ ] **Step 1: Update validation expectations first**

  Add checks in `tests/validate.sh` for `PROJECT-CONTEXT.md`, `COMPLETION-POLICY.md`, `MEMORY-README.md`, both wrappers, all new skills, and references from `commands/init.md` and `templates/AGENTS.md`.

- [ ] **Step 2: Run the validator and verify the new checks fail**

  Run: `bash tests/validate.sh`

  Expected: `FAIL` identifying the first missing new template or reference.

- [ ] **Step 3: Update initialization instructions**

  Describe the exact copy order, identity check, context inventory, health command discovery, memory directory creation, empty-plan creation, and generated Markdown render. State that existing files are never overwritten and identity mismatch requires user confirmation before new initialization.

- [ ] **Step 4: Update templates and completion policy**

  Link `AGENTS.md` to context, memory, plan, state, handoff, and completion policy. Add explicit role sequencing, scope adherence, happy/sad path analysis, user-owned mode choice, and repeated-correction notification. Define task, phase, and plan completion as measurable checklists in `templates/COMPLETION-POLICY.md`.

- [ ] **Step 5: Run validator and Markdown reference checks**

  Run: `bash tests/validate.sh`

  Expected: `ALL OK` after all references and templates are present.

- [ ] **Step 6: Commit the initialization deliverable**

  ```bash
  git add commands/init.md templates/AGENTS.md templates/CLAUDE.md templates/PLAN-template.md templates/HANDOFF-template.md templates/MUST-DO.md templates/COMPLETION-POLICY.md tests/validate.sh
  git commit -m "feat: initialize project memory workflow"
  ```

### Task 3.2: Update session and pre-commit enforcement

**Files:**
- Modify: `scripts/session-start.sh`
- Modify: `scripts/pre-commit-gate.sh`
- Modify: `tests/test-session-start.sh`
- Modify: `tests/test-pre-commit-gate.sh`

**Interfaces:**
- `session-start.sh` consumes `.harness/harness-project.py`, `.harness/harness-plan.py`, `.harness/execution-state.json`, and `PROJECT-CONTEXT.md`, and emits identity status, context freshness, memory summary, current phase/task, next action, selected mode, and active rules.
- `pre-commit-gate.sh` consumes the same files and exits `2` for protected branches, malformed/cross-project identity, invalid plan, invalid state, stale generated Markdown, or a failing health check.

- [ ] **Step 1: Add failing hook cases**

  Add temporary-project cases for fresh identity, stale context, identity mismatch, active memory notification, invalid plan task, and generated Markdown drift. Preserve the current fail-open behavior when no harness exists.

- [ ] **Step 2: Run hook tests and verify failure**

  Run: `bash tests/test-session-start.sh && bash tests/test-pre-commit-gate.sh`

  Expected: `FAIL` for the new cases because hooks do not call the new CLIs.

- [ ] **Step 3: Implement session-start loading**

  Add bounded Python calls with the existing 60-second health timeout. On identity mismatch, emit a clear stop message and do not print project memory, plan, or history. On a valid project, print the reusable context summary and current structured state before generic rules.

- [ ] **Step 4: Implement pre-commit gates**

  Keep branch and health checks, then validate identity, plan, state, and Markdown projection. Do not block unrelated sessions with no `.harness/` files. Never treat an unknown test command or missing evidence as green.

- [ ] **Step 5: Run all hook tests**

  Run: `bash tests/test-session-start.sh && bash tests/test-pre-commit-gate.sh`

  Expected: `ALL OK` from both scripts.

- [ ] **Step 6: Commit the enforcement deliverable**

  ```bash
  git add scripts/session-start.sh scripts/pre-commit-gate.sh tests/test-session-start.sh tests/test-pre-commit-gate.sh
  git commit -m "feat: enforce project identity and plan state"
  ```

### Task 3.3: Align skills with the persisted workflow

**Files:**
- Create: `skills/project-context/SKILL.md`
- Create: `skills/project-memory/SKILL.md`
- Modify: `skills/agent-orchestrator/SKILL.md`
- Modify: `skills/planning-director/SKILL.md`
- Modify: `skills/plan-manager/SKILL.md`
- Modify: `skills/stage-validator/SKILL.md`
- Modify: `skills/checkpoint-handoff/SKILL.md`
- Modify: `skills/retrospective/SKILL.md`
- Modify: `README.md`
- Modify: `tests/validate.sh`

**Interfaces:**
- Skills consume the same file contracts and use the same role names, statuses, precedence, review gates, and mode-decision fields. No skill may tell an agent to auto-select a mode or write internal reasoning to disk.

- [ ] **Step 1: Add validation assertions for the contracts**

  Require `project-context` and `project-memory` frontmatter, 95% confidence, happy/sad paths, scope/no-invented-scope wording, explicit user mode choice, monoagent/multiagent estimates, 90% coverage, three-blocker rule, identity mismatch, generated plan, and completion policy references.

- [ ] **Step 2: Write the context and memory skills**

  `project-context` must define initialization, fingerprint refresh, unknown handling, and identity validation. `project-memory` must define explicit-always promotion, repeated-correction promotion without approval, notification, candidate handling, secret exclusion, and rule precedence.

- [ ] **Step 3: Update orchestration and review skills**

  `agent-orchestrator` must present recommendation plus monoagent/mixed/multiagent estimates and wait for the user. `planning-director` must produce the backward/forward impact graph, happy/sad matrix, scope boundary, evidence, and questions. `plan-manager`, `stage-validator`, and `checkpoint-handoff` must refer to JSON source files and generated Markdown. `retrospective` must separate project learning from harness changes requiring approval.

- [ ] **Step 4: Update README operational documentation**

  Document the exact initialization command flow, file layout, identity mismatch behavior, memory policy, plan lifecycle, completion/archive paths, role sequencing, user-owned mode choice, estimated-token limitations, and version `0.4.0`.

- [ ] **Step 5: Run validator and skill reference checks**

  Run: `bash tests/validate.sh`

  Expected: `ALL OK` with every skill and contract present.

- [ ] **Step 6: Commit the role-contract deliverable**

  ```bash
  git add skills README.md tests/validate.sh
  git commit -m "docs: align skills with orchestrated workflow"
  ```

## Phase 4: Completion, Coverage, and Release

**Objective:** Close plans safely, prove behavior with the full test matrix, enforce the coverage target, and publish version `0.4.0` metadata.

**Success evidence:** Full validation passes, Python unit coverage for changed modules is at least 90%, integration shell tests pass, archive behavior is verified, and both manifests report `0.4.0`.

### Task 4.1: Add completion/archive and retrospective integration

**Files:**
- Modify: `scripts/harness_plan.py`
- Modify: `scripts/harness-plan.py`
- Modify: `skills/retrospective/SKILL.md`
- Modify: `tests/test-harness-plan.sh`
- Modify: `templates/COMPLETION-POLICY.md`

**Interfaces:**
- `archive_plan` consumes a fully green plan/state/handoff and produces a history Markdown file, final JSON snapshot, evidence index, and retrospective input; incomplete or blocked plans return a non-zero status without moving files.

- [ ] **Step 1: Add failing completion tests**

  Assert that incomplete, blocked, or missing-review plans cannot archive; a complete plan archives exactly once; the active plan pointer is removed; and the archive contains no transcript or secret-like content.

- [ ] **Step 2: Run the focused test and verify failure**

  Run: `bash tests/test-harness-plan.sh`

  Expected: `FAIL` for completion/archive cases before the new gate is complete.

- [ ] **Step 3: Implement completion gates**

  Require all tasks complete, all phase validators green, no blockers, final checkpoint, security/regression/test evidence, and retrospective metadata. Use an archive directory created with `mkdir`, refuse overwrite of an existing plan ID, and write files atomically.

- [ ] **Step 4: Run completion tests**

  Run: `bash tests/test-harness-plan.sh`

  Expected: `ALL OK` and a temporary `docs/plans/history/` containing the expected plan artifacts.

- [ ] **Step 5: Commit the completion deliverable**

  ```bash
  git add scripts/harness_plan.py scripts/harness-plan.py skills/retrospective/SKILL.md tests/test-harness-plan.sh templates/COMPLETION-POLICY.md
  git commit -m "feat: archive completed harness plans"
  ```

### Task 4.2: Run full verification, coverage, and version release

**Files:**
- Modify: `.claude-plugin/plugin.json`
- Modify: `.codex-plugin/plugin.json`
- Modify: `tests/validate.sh`
- Modify: `README.md`
- Create: `tests/test-python-coverage.sh`

**Interfaces:**
- `tests/test-python-coverage.sh` runs Python unit tests against `harness_store.py`, `harness_state.py`, `harness_context.py`, `harness_memory.py`, and `harness_plan.py`, and exits non-zero below 90% executable-line coverage. It uses an installed `coverage` command when available and the standard-library `trace` fallback otherwise; the selected method and percentage are printed.

- [ ] **Step 1: Add the coverage test harness**

  Create direct Python unit tests inside the shell runner for public success/error paths, then run them under the selected coverage tool. Exclude only CLI wrapper boilerplate and `if __name__ == "__main__"` guards; record exclusions in the script, not in a hidden configuration file.

- [ ] **Step 2: Run coverage and identify uncovered paths**

  Run: `bash tests/test-python-coverage.sh`

  Expected before completing tests: a numeric report and `FAIL` if coverage is below 90%.

- [ ] **Step 3: Add tests for uncovered public behavior**

  Cover malformed JSON, atomic replacement, lock release, identity mismatch, stale context, safe memory candidate handling, repeated correction promotion, plan dependency rejection, reviewer-gate rejection, mode recording, Markdown rendering, and archive refusal/success.

- [ ] **Step 4: Bump both plugin manifests**

  Change only the version fields in `.claude-plugin/plugin.json` and `.codex-plugin/plugin.json` from `0.3.0` to `0.4.0`, then update all exact-version assertions and README references.

- [ ] **Step 5: Run the complete verification matrix**

  ```bash
  bash tests/test-python-coverage.sh
  bash tests/test-harness-store.sh
  bash tests/test-harness-state.sh
  bash tests/test-harness-project.sh
  bash tests/test-harness-plan.sh
  bash tests/test-session-start.sh
  bash tests/test-pre-commit-gate.sh
  bash tests/validate.sh
  ```

  Expected: every command exits `0`, every test script prints `ALL OK`, coverage is `>= 90%`, and both manifests report `0.4.0`.

- [ ] **Step 6: Run final security and regression review**

  Inspect `git diff origin/develop...HEAD` for secrets, unsafe writes, unintended permissions, cross-project reads, unbounded subprocesses, and scope drift. Re-run the full matrix after any correction.

- [ ] **Step 7: Create the final implementation commit**

  ```bash
  git add .claude-plugin/plugin.json .codex-plugin/plugin.json README.md tests
  git commit -m "feat: add project memory orchestration"
  ```

## Stage Gates

### Gate after Phase 1

- [ ] `tests/test-harness-store.sh` passes.
- [ ] `tests/test-harness-state.sh` passes.
- [ ] Security review confirms atomic writes, lock release, and secret-pattern non-persistence.
- [ ] Handoff records the last verified commit and the next Phase 2 task.

### Gate after Phase 2

- [ ] `tests/test-harness-project.sh` and `tests/test-harness-plan.sh` pass.
- [ ] Identity mismatch and invalid plan transitions fail closed.
- [ ] Security, regression, and test evidence fields are required before advance.
- [ ] Generated Markdown matches JSON source.

### Gate after Phase 3

- [ ] `tests/test-session-start.sh`, `tests/test-pre-commit-gate.sh`, and `tests/validate.sh` pass.
- [ ] Hooks remain silent/open when no harness is initialized.
- [ ] Skills consistently state that the user chooses the agent mode.

### Gate after Phase 4

- [ ] Full verification matrix passes.
- [ ] Changed Python code meets `>=90%` unit coverage.
- [ ] Final archive/completion review is green.
- [ ] Version is `0.4.0` in both plugin manifests.

## Execution Notes

At execution start, run `dev-harness:agent-orchestrator` against this plan and present the
user with the exact current `T/F/S/R/D` values and approximate ranges. The preliminary
classification is high complexity: `T=9`, `F=25`, `S=4`, `R=high`, `D=long`. Based on the
existing matrix, the preliminary estimates are:

- Monoagent: `225k-450k` tokens.
- Multiagent: `580k-1.16M` tokens.
- Mixed: `465k-940k` tokens, depending on which review and test tasks are delegated.

These are planning estimates only. The user must choose the mode before Task 1.1 starts,
and the selected mode plus the final estimates must be recorded in the active plan and
execution state.
