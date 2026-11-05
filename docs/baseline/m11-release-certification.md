# M11 — Release Certification and Handover · Gate Evidence

Date: 2026-11-05 · Architecture: `vlsm-1.0.0` / app `1.0.0` · Roadmap:
`MILESTONES.md` §M11 · Test command: `make release-check`

## Scope executed this session

- Phase 1 (M0–M10) was already PASS before this session; M11 is the v1.0
  release gate. This session executed the M11 acceptance criteria against the
  current working tree (which includes the M8–M10 changes recorded in
  `DELIVERY.md`).

## M11-AC-001 · All mandatory tests pass (recorded output)

`make release-check` (backend pytest + ruff; frontend `tsc -b && vite build` +
oxlint). Full log: `docs/evidence/m11/release-check.log`.

| Gate | Result |
| --- | --- |
| `pytest -q` | **223 passed**, 5 warnings (17.91 s) — includes M8/M9/M10 gate suites |
| `ruff check .` | All checks passed (E, F, I, W) |
| `npm run build` | tsc + vite build exit 0 (594 kB main chunk, chunk-size advisory only) |
| `npm run lint` | 0 errors, 1 pre-existing advisory (`react(set-state-in-effect)` in `src/ui.tsx`, present since M6) |

These UI-only failures-and-fixes were also run this session (see AC-002).

## M11-AC-002 · Accessibility checks pass

`frontend/a11y.mjs` (axe-core 4.11.1, WCAG 2/2.1 A+AA) against a live stack:
backend `:8001` (isolated `m11-gate.db`, seeded — dev `netspace.db` untouched)
+ vite dev `:5173`. Full log: `docs/evidence/m11/a11y.log`.

- **First run: FAIL** — 10 violation entries: `label` (critical) on Ark
  `clipboard` readonly CIDR inputs (dashboard 12, networks 12) and
  `number-input` spinbuttons (planner 10); `color-contrast` (serious) on the
  `.badge.ok` text (`#12805c` on `#e3f6ee`, 3.96:1) across pages and the
  sidebar brand pill.
- **Fixes (frontend only, no API/dependency change):**
  - `ui.tsx`: `NumberField` gained a `label` prop forwarded as `aria-label`
    (`CopyValue` likewise); all 6 `NumberField` call sites pass explicit,
    row-scoped labels (Planner labels include the department name).
  - `styles.css`: `--ok` darkened `#12805c → #0f6b4d` (5.78:1 on `--ok-soft`);
    `.brand small` uses `--side-ink` directly instead of inherited
    `--side-ink-strong` at `opacity: .6` (≈8.5:1, up from the blended ≈4:1) and
    gets a solid `--side-bg-2` background so axe can resolve the pill's own
    background    instead of a page-level fallback); `--ok` stays high-contrast in dark
    theme (`#3ddc97` on dark surfaces, ≈10:1).
- **Final run: PASS — 0 violations on all 7 pages** (dashboard, calculator,
  vlsm-planner, plans, networks, ip-addresses, departments).
Smoke regression after the fix: `ui-smoke.log`: 27 PASS,
  exit 0.

## M11-AC-003 · Documentation reviewed and complete

- New deliverables: `docs/USER-GUIDE.md` (roles, pages, planning → plan
  activation, inventory lifecycle, exports, error semantics) and
  `docs/RUNBOOKS.md` (start/stop, health, backup/restore drill, migrations,
  upgrade rollback, first-responder table, release verification).
- Review pass over the existing set: README verification section updated (was
  stale: "204 tests" → `make release-check` + 223 tests + a11y/smoke lines);
  `docs/README.md` index now lists USER-GUIDE/RUNBOOKS; `API.md` Reports
  section now states the M8-AC-004 export authentication requirement;
  `ARCHITECTURE.md` last-updated line records the M11 UI/token change per the
  documented maintenance policy.
- Not stale: `docs/DATA.md` (seed), `docs/quality/*` (M9/M10 artifacts).
- Doc-review record: staleness check (`find backend/app frontend/src -newer
  docs/ARCHITECTURE.md`) after edits → only build caches and the files touched
  by this session's fixes remain newer, all mirrored above.

## M11-AC-004 · Blockers closed

Assessed against the risk register (`docs/quality/milestone-status.json` §risks):

| Risk | Release verdict |
| --- | --- |
| R-02 (Windows DLL block) | Not a blocker; this release certifies the Linux deployment path; pin unchanged |
| R-03 / R-04 (GPU compositor / headless GPU) | Not a blocker; documented limitation — dialogs avoid filter/backdrop-filter paths (R-03); GPU-only regressions are outside automated coverage |
| R-05 (Docker daemon) | RESOLVED (M10): systemd daemon at `/var/run/docker.sock` |
| R-01 (legacy pre-Alembic dev DB) | Not a release blocker: migration gates run on empty/isolated DBs; remediating the operator's legacy local file stays a documented operator task (RUNBOOKS §5) |
| R-08 / R-09 / R-10 | Phase 2 (M12+) scope, explicitly out of the v1.0 gate |
| R-07 (CRLF warnings) | Cosmetic; no normalization applied |
| **R-06 (tree uncommitted)** | **Blocks AC-006 only** (tag requires an operator-authorized commit); see AC-006 |

No open security or functional release blocker. Security posture:
`docs/quality/security-findings.md` — no unresolved critical/high; controls
S-01..S-06 test-backed (auth on exports included).

## M11-AC-005 · Release evidence complete

- Test report: this document (+ `docs/evidence/m11/` archive: release-check,
  a11y, ui-smoke, backend-startup logs).
- Documentation: USER-GUIDE, RUNBOOKS, API, ARCHITECTURE, DATA, quality dossier
  (`performance-targets`, `security-findings`, `recovery`,
  `service-diagnostics`), baseline gates M0–M10.
- Live-stack reproducibility: a11y/smoke were executed against a stack whose
  database was migrated 0001→0003 and seeded via the documented commands;
  backend startup log archived.

## M11-AC-006 · Release candidate tagged (human identity)

**PENDING operator authorization** (risk R-06: the working tree carries large
uncommitted operator changes — nothing may be staged or committed without an
explicit ask). All other criteria are PASS; the tag can be cut the moment a
commit of this baseline is authorized: everything above + `git tag
netspace-v1.0.0-rc1 <commit>` with the configured human identity, no agent
attribution (AGENTS.md), tag hash recorded here afterwards.

## M11-AC-007 · Universal Milestone Gate (§3) checklist

```text
[✓]  1. Scope and prerequisites documented (MILESTONES.md §M11; depends M10, PASS).
[✓]  2. Deliverables exist and are reviewed (API docs, user guide, runbooks,
        test report, evidence archive; review pass this session).
[✓]  3. Implementation complete for scope (a11y fixes + gate target + docs).
[✓]  4. Automated tests executed (223 passed, recorded).
[✓]  5. Lint/format/type checks pass (ruff clean; oxlint 1 pre-existing
        advisory; tsc clean).
[✓]  6. Security/compatibility checks pass (M9 dossier; exports auth;
        no secrets in source — M1 gate + no new material added).
[✓]  7. Existing functionality preserved (smoke 27 PASS; the a11y changes only
        added aria-labels and recolored two tokens).
[✓]  8. Docs and setup instructions updated.
[✓]  9. Git diff contains only intended changes (frontend a11y fixes, Makefile,
        docs; no unrelated edits — see AC-006 for the staged-tag caveat).
[✓] 10. Evidence and status recorded (this file; milestone-status.json).
```

## Verdict

**M11: PASS on AC-001…AC-005 and AC-007; AC-006 (tag) pending a single
operator authorization.** v1.0 release candidate otherwise certified.
