# CLAUDE.md — Agent Compatibility Layer

Compatibility file for tools that read `CLAUDE.md`. It reinforces `knowledge.md` and
`AGENTS.md`; it does not replace or weaken them. When in doubt, the stricter rule wins.

## Must

- Inspect before editing: read the implementation, callers, tests, and config.
- Make the smallest correct change that fixes the root cause.
- Preserve public interfaces, schemas, endpoints, and defaults unless authorized.
- Run the smallest relevant test first; never claim a pass you did not observe.
- Keep token use low: targeted search, relevant sections only, no repeated dumps.
- Keep scope tight: no unrelated fixes, refactors, or documentation.

## Must not

- Add the agent as Git author, co-author, trailer, or contributor.
- Reference an agent identity other than the username `kiamamartin`.
- Commit, push, amend, rebase, or rewrite history without explicit authorization.
- Discard local changes or run destructive commands without confirmation.
- Add dependencies without justification and approval.
- Print, log, or commit secrets.
- Fabricate test results, file contents, or command output.

## Commit messages

- Describe the change and its purpose. Do not mention the agent or the process.
- Retain the operator's configured Git identity.

## When blocked

- State the blocker, what was attempted, and the exact information or access needed.
- Do not guess at completion or produce placeholder artifacts that imply success.