# ARTEMIS Next frontend

The sole ARTEMIS frontend: a static-export Next.js App Router application. It never fetches backend data during build; API calls are client-initiated only.

## Commands

- `npm run lint`
- `npm run typecheck`
- `npm test`
- `npm run build` (exports `out/`)
- `npm run test:acceptance` (Chromium smoke through a controlled FastAPI host)

The acceptance suite requires `@playwright/test` plus a Chromium browser. Install them explicitly when browser smoke is enabled: `npm install --no-save @playwright/test@1.51.1` and `npx playwright install chromium`. The production-artifact fallback does not need a browser: from the repository root run `pytest tests/integration/static_hosting/test_next_production_artifact.py -m integration`. Both paths require a fresh `out/` from `npm run build`; neither uses real backend data. Set `ARTEMIS_ACCEPTANCE_BASE_URL` only to exercise an already-running compatible FastAPI host instead of the controlled fixture.

## Fixed contracts

Routes: `/`, `/workspace/`, `/task-schedule/`, `/settings/`, `/check/`. Settings preserves `?tab=...`. Preferences use schema v1 at `artemis.ui.preferences.v1`. API URLs remain same-origin under `/api`.

FastAPI, launch scripts and packaging use Next.js by default. Angular has been removed; no frontend selector is required.
