# backend.md — Backend Nested Rules

Applies when editing backend code (API, services, domain logic, workers).

- Match the existing framework and layering; keep business logic out of route handlers.
- Validate input at the boundary and enforce invariants in the domain/service layer.
- Use parameterized queries and the ORM's safe patterns; never build SQL by string
  concatenation with user input.
- Keep changes additive to request/response schemas unless a breaking change is approved.
- Preserve existing HTTP status codes and error-shape conventions.
- Add or update tests for validation, error paths, and boundary conditions.
- Never log secrets, tokens, full credentials, or sensitive payloads.
- Do not change authentication or authorization behavior without explicit approval.
- Handle concurrency-sensitive operations transactionally; document the isolation assumption.
- Do not introduce new frameworks or major libraries without approval.