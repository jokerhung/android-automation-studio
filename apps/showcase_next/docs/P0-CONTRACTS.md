# P0 baseline and contracts

## Baseline surveyed

- Angular routes are defined in `apps/showcase_ui/src/app/app.routes.ts`: Home, Workspace, Task Schedule, Settings, and legacy Check.
- Navigation order is Home → Workspace → Task Schedule → Settings. Check remains directly addressable but is not a primary tab.
- Settings reuses the Angular Home component in diagnostics mode; Next separates it as a route shell.
- Preferences are `{ version: 1, language: 'en'|'vi', theme: 'light'|'dark' }` under `artemis.ui.preferences.v1`; invalid or blocked storage falls back to English/light.
- Representative same-origin APIs: `/api/system/readiness`, `/api/run`, `/api/run/defaults`, `/api/sessions`, `/api/stream`, `/api/schedules`, `/api/devices`, and `/api/settings/email`.

## P1 decisions

- Next 15.5.25, React 19.1.1, TypeScript 5.8.3, Node >=20.9; exact dependency versions and npm lock.
- App Router static export with trailing slashes and unoptimized/local assets. No Server Actions, middleware, route handlers, remote fonts, or build-time fetch.
- Root client provider owns theme/language and cross-tab storage synchronization. An inline head bootstrap applies persisted attributes before paint.
- Typed `fetch` wrapper supports JSON/text/empty responses, structured errors, AbortSignal, and encoded path segments. Mutations are never automatically retried.
- Typed EN catalog is authoritative; VI is a partial catalog and falls back to EN by key.

## P0 parity checklist / deferred work

P1 supplies route shells, responsive navigation, primitives, preferences, API foundation, i18n, errors, and tests. Full Home/Settings behavior is P2; schedule CRUD is P3; Workspace SSE/player and legacy Check parity are P4. FastAPI hosting selection/manifest is outside the allowed edit scope and remains a P1 integration gap.

No fixture contains credentials. Tests use local in-memory values and mocked fetch only.
