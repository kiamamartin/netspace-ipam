# frontend.md — Frontend Nested Rules

Applies when editing frontend code (components, hooks, state, styles).

- Match the existing component patterns, state management, and styling approach.
- Keep server state authoritative; do not duplicate backend calculations client-side.
- Preserve existing accessibility behavior: labels, focus order, keyboard navigation,
  and ARIA semantics.
- Do not hardcode values that should come from the API.
- Keep changes responsive; verify layouts at mobile and desktop widths when relevant.
- Add or update tests for user-visible behavior, error, and loading states.
- Do not add UI libraries or state managers without approval.
- Never expose secrets or internal API details in client bundles.
- Match existing formatting of numbers, dates, and addresses.