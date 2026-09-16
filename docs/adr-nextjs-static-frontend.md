# ADR: Next.js static frontend migration

## Status

Accepted for the parallel migration period.

## Decision

- Add `apps/showcase_next` beside `apps/showcase_ui`.
- Use Next.js App Router, React and strict TypeScript with `output: 'export'` and `trailingSlash: true`.
- FastAPI remains the only production runtime and serves the selected artifact at the existing origin and port.
- Select the frontend explicitly with `ARTEMIS_FRONTEND=angular|next`; default remains `angular` until the parity gates pass.
- Use same-origin typed fetch plus AbortController. Do not add Next API routes, Server Actions, SSR, ISR, middleware or production rewrites.
- Keep root providers for preferences and task/session transport so route changes do not recreate streams.
- Preserve storage schemas and API contracts; do not add secrets to public environment variables, bundles or browser storage.
- Package a complete immutable export tree and a manifest identifying framework, version/commit and lockfile inputs.

## Consequences

- Every route needed in production must be known at build time.
- Interactive data loads after mount; static export cannot depend on FastAPI availability.
- Next image optimization requiring a server is unavailable; backend media uses ordinary image/video elements.
- Unknown UI routes can return the exported 404, while missing assets/API remain proper 404 responses.
- Angular is retained as rollback material through P5 and removed only after acceptance.
