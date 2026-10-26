# NetSpace IPAM — Documentation

| File | Contents |
| --- | --- |
| [API.md](API.md) | REST endpoint reference (request/response contracts) |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Full-stack architecture: backend layers, frontend design system (Ark UI), theming, testing |
| [DATA.md](DATA.md) | Enterprise demo dataset: what the seed contains and how to reseed |

## Maintenance policy

These docs are **updated manually after every key architectural change** —
the AI agent maintaining this repo performs the update in the same change
that introduces the architectural edit (this is the "manual" mode chosen
instead of a regenerating cron job, which cannot detect architectural meaning
reliably).

### What counts as a key architectural change

- New/removed dependency (frontend or backend)
- New page/route, removed resource, or shell change
- API contract change: new/changed endpoint, request/response shape, error code
- New UI primitive in `src/ui.tsx`, design-token or theming change
- Database model, migration, or service-layer (VLSM engine) change
- Testing/verification workflow change

Small bug fixes and visual tweaks that change no structure do **not** require
a doc update.

### Update checklist (run inside the same change)

1. `ARCHITECTURE.md` — update the affected section(s) and bump the
   _Last updated_ line (mention what changed).
2. `API.md` — if endpoints/DTOs changed, mirror it there.
3. `../README.md` — feature list / verification commands, if affected.
4. Re-run the affected verification (at minimum `npm run build` + `npm run lint`
   for frontend changes; `pytest -q` for backend) so doc claims stay true.

### Optional staleness reminder (cron / scheduled task)

A plain cron job cannot rewrite the docs meaningfully, but it can nag when
sources moved ahead of the docs. Save and run periodically (exit 1 = stale):

```bash
#!/usr/bin/env bash
# docs-stale-check.sh — fails if app sources are newer than the docs
stale=$(find backend/app frontend/src -type f -newer docs/ARCHITECTURE.md 2>/dev/null | head -3)
if [ -n "$stale" ]; then
  echo "docs/ARCHITECTURE.md is stale — sources changed after it:"
  echo "$stale"
  exit 1
fi
echo "docs up to date"
```

- Linux/macOS cron: `0 9 * * 1 /path/to/docs-stale-check.sh`
- Windows: Task Scheduler running the same script via Git Bash weekly.
