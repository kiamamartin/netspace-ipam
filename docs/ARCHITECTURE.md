# NetSpace IPAM — Architecture

_Last updated: 2026-10-16 (after: Ark UI design-system adoption, dark mode,
dialog compositing fix + modal blur/focus, enterprise demo seed). See
[README.md](README.md) for the docs maintenance policy that keeps this file
current._

## Overview

```
Browser (React 19 + Ark UI)          FastAPI backend
┌──────────────────────────┐        ┌──────────────────────────────┐
│ App shell (sidebar/topbar)│  HTTP  │ app/api      route handlers  │
│ pages/*      thin views   │ ─────► │ app/services domain + VLSM   │
│ ui.tsx      Ark wrappers  │  JSON  │ app/models   SQLAlchemy ORM   │
│ api.ts      typed client  │ ◄───── │ app/schemas  Pydantic DTOs    │
└──────────────────────────┘        │ db + Alembic migrations      │
                                    └──────────────────────────────┘
```

Every allocation, validation and report is computed server-side; the UI is a
thin client over the REST API (`docs/API.md`).

## Backend (`backend/`)

| Path | Responsibility |
| --- | --- |
| `app/main.py` | App factory, CORS, router mounting, `/health` |
| `app/api/` | Route handlers per resource (networks, subnets, ip-addresses, departments, allocation-plans, calculator, reports, dashboard, audit-events) |
| `app/services/` | Domain logic: IP math, the VLSM engine (`vlsm-1.0.0`), plan activation, report builders (CSV/XLSX/PDF) |
| `app/models/` | SQLAlchemy models (networks, subnets, ip_addresses, departments, plans, audit_events) |
| `app/schemas/` | Pydantic request/response contracts |
| `app/db/` | Engine/session wiring (SQLite by default, `backend/netspace.db`) |
| `migrations/` | Alembic migrations (`alembic upgrade head`) |
| `tests/` | pytest suite (155 tests) + `ruff` lint |
| `scripts/seed_enterprise.py` | Seeds the "Aurora Dynamics" enterprise dataset through the service layer (see [DATA.md](DATA.md)) |

Invariants enforced server-side on every write: containment, alignment,
overlap detection, and a full audit trail per mutation.

## Frontend (`frontend/`)

Vite + React 19 + TypeScript. **Ark UI** (`@ark-ui/react`) provides all
interactive behavior headlessly (accessible dialogs, menus, selects…); the
visual layer is a custom design system in `styles.css` keyed on
`[data-scope='…'][data-part='…']` selectors and CSS custom properties.

| File | Responsibility |
| --- | --- |
| `src/main.tsx` | Entry: `initTheme()` before first paint, then render |
| `src/App.tsx` | Shell: sectioned sidebar, topbar (theme toggle + print), routes, `ToastHost`/`ConfirmHost` mounts |
| `src/api.ts` | Typed fetch client; errors normalized to `ApiError { status, code, message, details }` |
| `src/feedback.ts` | Non-component engines: `toaster`/`notify` (toasts), `confirmAction` (promise-based confirm) |
| `src/theme.ts` | Light/dark state: `data-theme` on `<html>`, localStorage (`netspace-theme`), OS fallback, `useTheme()` hook |
| `src/ui.tsx` | Ark-based primitives + icons (see mapping below) |
| `src/kv.tsx` | Key/value grid helper |
| `src/styles.css` | Full design system: tokens, components, Ark part styling, print stylesheet |
| `src/pages/` | Dashboard, Calculator, Planner, Plans, Networks, IpAddresses, Departments |

### UI primitive mapping (page code → Ark component)

| Our wrapper | Ark component | Used for |
| --- | --- | --- |
| `Modal` | `Dialog` | All create/edit forms (networks, subnets, IPs, departments) |
| `confirmAction()` | `Dialog role="alertdialog"` | Replaces `window.confirm` for destructive actions |
| `notify.success/error()` | `Toast` + `createToaster` | Mutation feedback (bottom-end, max 3) |
| `TextField` | `Field` | Labeled inputs with aria wiring + invalid state |
| `SelectField` | `Select` + `createListCollection` | Filters and pickers (environment, status, subnet) |
| `NumberField` | `NumberInput` | Numeric inputs (hosts, VLAN, reserved) |
| `PaginationBar` | `Pagination` | Backend-paginated lists (page window with ellipses) |
| `Meter` | `Progress` | Utilization bars (gradient; `hot` for ≥85%) |
| `RowMenu` | `Menu` | Per-row actions (mark status, edit, delete) |
| `Tip` | `Tooltip` | Hover hints on icon buttons |
| `CopyValue` | `Clipboard` | One-click copy of CIDRs/addresses |
| — | `Tabs` | Calculator tool switcher |

### Data flow

- Pages call `api.get/post/patch/delete` → FastAPI; non-2xx becomes `ApiError`
  and is surfaced via `ErrorBanner` + an error toast.
- Mutations end with `notify.*` and a reload of the affected list.
- Destructive actions go through `await confirmAction({...})` first.
- Loading states use `<Loading/>` spinners; submits set `disabled` + busy text.

### Theming (light/dark)

- Single token palette in `:root`; dark overrides in `html[data-theme='dark']`
  (backgrounds, ink, status colors with AA-ish contrast, shadows).
- `initTheme()` (main.tsx) resolves: localStorage → OS `prefers-color-scheme`;
  the toggle in the topbar persists the choice via `setTheme()`.
- Component colors must use tokens (`--surface`, `--ink`, `--track`,
  `--field-bg`, `--row-hover`, `--danger-line`…) — no raw hex in component
  rules, or dark mode breaks.
- `@media print` re-overrides dark tokens back to light so reports always
  print black-on-white (A4 landscape).
- **Modal blur & focus:** while a dialog is open the background is blurred via
  `body:has([data-scope='dialog'][data-part='backdrop']) .app-shell { filter:
  blur(3px) }` and Ark's modal behavior traps focus inside the dialog (the
  rest of the page becomes inert). The smoke test asserts both (blur computed
  style + 12 Tabs staying inside the content).
- **Caution — GPU compositing:** never put `backdrop-filter` on the dialog
  backdrop or topbar. On GPU-accelerated browsers it can paint above later
  siblings despite `z-index`, hiding the modal behind the blur (fixed
  2026-10-16; headless tests use software rendering and cannot catch this).
  Blur the `.app-shell` (below the portal) instead.

## Testing

| Layer | Command | Notes |
| --- | --- | --- |
| Backend | `cd backend && pytest -q && ruff check .` | 155 tests |
| Frontend build | `cd frontend && npm run build` | `tsc -b` + vite |
| Frontend lint | `cd frontend && npm run lint` | oxlint, 0 warnings expected |
| UI smoke | `cd frontend && npm run test:ui` | Headless Edge (puppeteer-core) against live dev stack; 16 checks: every page, theme toggle + persistence, dialog stacking (`elementFromPoint` guard), CRUD round trip via Dialog/Toast/Menu/AlertDialog |

The smoke test needs backend (`:8000`) and `npm run dev` (`:5173`) running;
screenshots land in the OS temp dir (`netspace-smoke/`). One benign
`requestfailed` for `DELETE /departments/:id` may appear: the delete succeeds
(row disappears, re-list confirms) — it is a dev-proxy connection artifact.

## Known constraints

- Vite warns the single JS chunk exceeds 500 kB (React + Ark's broad module
  graph). Candidate follow-up: route-level code splitting.
- SQLite by default; the backend is storage-agnostic via SQLAlchemy.
