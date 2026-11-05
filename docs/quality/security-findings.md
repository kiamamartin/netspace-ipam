# Security findings report — M9 (M9-AC-002, M9-AC-003, M9-AC-006)

Date: 2026-11-05 · Roadmap: `MILESTONES.md` §M9 · Scope: v1 API surface
(`backend/app`), tests reachable in this repository.

## Verdict

**No unresolved critical or high-severity findings.** Findings S-01–S-06
below are controls verified by executed tests; the residual-risk register
(R-01–R-10 shared with `docs/quality/milestone-status.json`) lists the
accepted limitations.

## Verified controls

| ID | Control | Evidence (executed) |
| --- | --- | --- |
| S-01 | Authentication enforced on every mutating endpoint and on report exports; anonymous state-changing requests get `401` | `tests/test_auth.py::test_anonymous_write_denied`, `::test_exports_require_authentication` |
| S-02 | Role matrix: `viewer`/`operator`/`admin` enforced server-side; forbidden writes get `403`; user administration is admin-only; last-admin and self-deactivation are protected | `tests/test_auth.py` (role matrix + user lifecycle tests) |
| S-03 | Login rate limiting (5 per 60 s per client IP) and 1 MiB request-body cap (`413`) | `tests/test_auth.py::test_login_rate_limited`, `::test_request_body_size_limited` |
| S-04 | Injection attempts through query search are inert data (parameterized SQLAlchemy; no string-built SQL); stored rows untouched | `tests/test_input_abuse.py::test_sql_injection_via_search_is_inert` |
| S-05 | Malformed payloads (broken JSON, wrong types, oversized fields, invalid pagination/enums/path segments) end as structured `422/404` in the documented error envelope — never a stack trace or driver internals | `tests/test_input_abuse.py`, envelope handler `app/core/errors.py` |
| S-06 | Database failure surfaces as a structured `500 internal_error` envelope; recovery is immediate without restart; a failed commit leaves no partial rows | `tests/test_resilience.py` (M9-AC-004) |

Transport-layer and secrets controls outside this suite (see residual risks):

- Bearer tokens are signed (`app/core/security.py`) with `NETSPACE_AUTH_SECRET`
  from environment; no passwords are stored in the repository (seed reads
  `NETSPACE_SEED_*_PASSWORD`).
- TLS termination is a deployment-level control (nginx/Docker compose) and is
  therefore part of M10 evidence, not this report.

## Residual risks (accepted, tracked)

| Ref | Risk | Disposition |
| --- | --- | --- |
| R-04 | Headless UI tests run `--disable-gpu`; GPU-only regressions cannot be detected by automation | Documented; UI smoke suite + manual check required at release |
| R-05 | Docker daemon unavailable on the build machine; transport/TLS evidence deferred to M10 deployment drill | M10 blocker, tracked |
| Login limiter | In-process per-client-IP limiter; on multi-replica deployments the limit is per-process | Accepted for v1 single-container deployment; review before horizontally scaled deployments |
| Bearer lifetime | Fixed token lifetime (`jwt_expires_minutes`); no refresh/revocation | Accepted for v1; admin can deactivate accounts immediately (S-02) |
| Rate limit keying | Client IP taken from `X-Forwarded-For` — trustworthy only behind the controlled reverse proxy | Accepted; ensure only the trusted proxy sets/removes the header in production |

## Method

Manual review of the API surface against the roadmap §M9 threat list
(concurrency abuse, input abuse, authorization bypass, database failure,
performance, recovery), then each item pinned by an automated test named
above. Nothing in this report is unverified.
