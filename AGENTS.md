# AGENTS.md — Coding and Repository Rules

Applies to any agent or automation operating in this repository. Complements
`knowledge.md`; must not contradict it.

## Identity

- Commits use the configured human Git identity only.
- Agent references, if unavoidable, use only the username `kiamamartin`.
- No agent attribution in commit trailers, `AUTHORS`, `CONTRIBUTORS`, `NOTICE`,
  file headers, or documentation.

## Repository exploration

- Start from the repository root; inspect `README`, build files, and the relevant
  module before editing.
- Locate implementations by symbol and by usage, not by assuming file layout.
- Read tests to confirm expected behavior before changing behavior.
- Check the task runner (`Makefile`, scripts, CI config) to learn the canonical
  test, lint, and build commands — use those rather than inventing new ones.

## Change boundaries

- Keep changes inside the module or layer that owns the behavior.
- Do not move files, rename packages, or reorganize directories unless requested.
- Do not edit generated files, lockfiles, vendor directories, or migration history
  manually.
- Do not modify CI configuration as a workaround for a failing check; fix the cause.

## Testing

- Run the smallest relevant test first; broaden only when the change warrants it.
- Every bug fix includes a regression test that fails without the fix.
- Do not skip, xfail, or delete tests to make a suite pass.
- Do not loosen assertions or widen tolerances to hide a failure.
- Keep tests deterministic; avoid dependence on wall-clock time, network, or ordering.

## Dependencies and environment

- Use the project's existing package manager and lockfile.
- Do not add, remove, or upgrade dependencies without explicit approval.
- Do not commit virtual environments, build artifacts, caches, or downloaded binaries.

## Git

- Do not commit, stage, or push unless explicitly asked.
- Do not amend, squash, rebase, or rewrite published history.
- Do not change `git config` (user, email, hooks) without permission.
- Never add a co-author trailer naming an agent.
- Keep the working tree free of stray debug files; remove temporary artifacts you create.

## Secrets

- Never print, log, commit, or transmit credentials, tokens, keys, or `.env` contents.
- Reference configuration through the project's documented settings mechanism.
- Do not add secrets to test fixtures or example files.

## File ownership

- Treat operator-authored files as read-only unless the task requires editing them.
- Do not overwrite unrelated local modifications.
- When resolving conflicts, preserve the operator's intent and ask when ambiguous.

## Reporting

- Report what changed, why, what was tested, and what was not tested.
- Report blockers and unknowns plainly instead of guessing or claiming completion.
- Distinguish verified facts from assumptions.