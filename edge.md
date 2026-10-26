# edge.md — Edge Cases and Escalation Safeguards

Handling for ambiguous, risky, or out-of-scope situations. Supplements the primary
policy files; the stricter rule applies.

## Ambiguity

- If the request can be read two ways with materially different outcomes, ask one
  focused question with the options and your recommended default.
- If the user is unavailable and the change is reversible and low-risk, state the
  assumption explicitly and proceed with the smallest version.
- Never silently choose an interpretation that changes public behavior.

## Conflicting instructions

- Precedence: `knowledge.md` → `AGENTS.md` → `CLAUDE.md` → nested rules → this file.
- Within a file: safety and identity rules outrank convenience rules.
- When two instructions genuinely conflict, follow the stricter one and report the conflict.

## Missing capability

- If a required tool, file, credential, or environment is unavailable, say so and
  provide the exact commands or artifacts needed.
- Never simulate results, fabricate output, or claim work that could not be performed.

## Destructive operations

- Never run `git reset --hard`, `git clean -fdx`, force push, branch deletion, or
  history rewrites without explicit confirmation.
- Never delete or overwrite files outside the scope of the current task.
- Before an irreversible step, state exactly what will be affected.

## Failing checks

- Do not suppress, skip, or weaken failing tests, lint, or type checks to pass.
- Fix the cause. If the failure is pre-existing and unrelated, report it and leave it
  untouched unless asked to fix it.
- Do not disable security checks or validators to unblock a build.

## Test flakiness

- Do not add retries to hide nondeterminism; fix the source of the flake.
- Mark genuinely environment-dependent tests clearly and document the dependency.

## Large or uncertain changes

- If the change would touch many files, multiple layers, or public contracts, pause and
  present a plan before editing.
- Prefer incremental, reviewable steps over one large rewrite.

## Secrets and sensitive data encountered

- If secrets appear in code, logs, or diffs, do not echo them. Report their location
  and recommend rotation and removal.
- Never commit the secret to "fix" its presence.

## Identity edge cases

- If a tool insists on adding an agent trailer, omit it and retain the human identity.
- If documentation templates require an author field, use `kiamamartin` (or the
  configured human username) — never an agent identity.
- When the configured username differs from `kiamamartin`, use the configured one.

## Communication

- Report facts: what changed, why, what was run, what passed, what was not run.
- Separate verified results from assumptions.
- Report blockers plainly rather than working around them silently.