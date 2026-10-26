# database.md — Database Nested Rules

Applies when editing models, migrations, queries, or seed data.

- Use the project's migration tool; never edit applied migrations. Add a new migration.
- Migrations must be reversible when the project supports rollback.
- Preserve existing constraints (uniqueness, foreign keys, checks) unless a change is approved.
- Enforce invariants at both the database and service layers where the project does so.
- Parameterize queries; never interpolate user input into SQL.
- Keep destructive migrations (drop column/table) behind explicit approval and a data plan.
- Seed and fixture data must not contain secrets.
- Verify migrations against a clean database before declaring completion.