# Project Memory

Project-scoped learning is stored in `.harness/memory/memory.json`. The store is bound to
the initialized project identity and must not be copied between projects. A mismatched
identity is an error; it is never a reason to reuse another project's memory.

Each entry records a stable rule ID, the original rule text, project scope, source,
occurrences, confidence, status, timestamps, and project identity. The original text is
kept for display while matching normalizes only case, whitespace, punctuation, and common
English/Spanish approval phrases.

- `memory always --text ...` creates an active explicit project rule immediately and emits
  `MEMORY UPDATED: <rule-id>`.
- `memory correction --text ...` creates a candidate on its first exact normalized form.
  The second occurrence promotes it to an active learned rule and emits the same update.
- Non-exact or otherwise uncertain corrections remain candidates. No semantic service,
  conversation transcript, or internal reasoning is stored.
- API keys, bearer tokens, private keys, passwords, and credential-bearing URLs are
  rejected before any memory write.

Rule precedence, strongest first:

1. Current explicit user instruction
2. Explicit project rule
3. Learned project memory
4. `AGENTS.md` / `CLAUDE.md` rules
5. General harness skills
6. Agent defaults

Harness-wide improvements belong in their own approved, versioned workflow and are never
stored in project memory.
