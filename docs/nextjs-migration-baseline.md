# Next.js migration baseline and contracts

Captured from commit `ecc306130e05dca03d6e212e5461de00f15ec9c3`.

## Toolchain baseline

- Node: 24.18.1 (development machine; application engine is pinned by the Next app).
- npm: 11.16.0.
- Python: 3.10.10.
- Existing frontend: Angular 22.1.x, TypeScript 6.0.3, RxJS 7.8, Angular CDK, Jasmine/Karma; exact baseline inventory contains 26 spec files and 213 `it()` calls. Angular CLI defaults provide the Karma configuration; there is no separate `karma.conf` or established frontend coverage threshold.
- Catalog baseline: exactly 675 entries in each EN/VI catalog using the executable entry parser. Key and placeholder snapshots must use parser/import results rather than file line counts.
- Angular production budgets retained for comparison: initial bundle warning/error 2/4 MiB and component stylesheet warning/error 200/400 KiB.
- Existing storage contracts: `artemis.sessions.v1`, `artemis.ui.preferences.v1` and `artemis_selected_profile`.
- Angular lockfile toolchain requires Node `^22.22.3 || ^24.15.0 || >=26.0.0`; the Next app independently pins a compatible Node/Next/React/TypeScript set rather than inheriting Angular's TypeScript runtime assumptions.
- Public asset contract is exactly `favicon.ico`, `logo.png`, `logo.svg` and `ui-preferences-bootstrap.js`. Existing Google Fonts/Material Symbols are loaded remotely and redundantly from Angular HTML/styles; local/offline replacement remains a cutover gate.

## Route contract

| URL | Existing owner | Migration requirement |
| --- | --- | --- |
| `/` | Angular Home launcher | Next static `index.html`; preserve Flash/Pro submission and readiness states. |
| `/workspace` | Angular Workspace | Next export at `workspace/index.html`; preserve query/session selection and stream state. |
| `/task-schedule` | Angular Task Schedule | Next export at `task-schedule/index.html`; preserve CRUD, preview and history. |
| `/settings?tab=...` | Angular Home diagnostics view | Next export at `settings/index.html`; preserve tab query. |
| `/check` | Angular Legacy Workspace | Keep a distinct exported route until parity is proven. |
| `/admin`, `/debug` | FastAPI admin console | Must remain backend-owned. |
| `/api/*`, media and replay | FastAPI | Must never fall through to UI HTML. |

## API inventory

### Tasks, sessions and stream

- `POST /api/run`, `GET /api/run/defaults`.
- `POST /api/stop`, `POST /api/resume`, `GET /api/status`.
- `GET /api/stream` and session stream variants; one EventSource per browser tab.
- `GET /api/sessions`, delete/cleanup, usage, steps, startup progress, checks, notes, video and replay endpoints.
- `GET /api/stream/device-live` and `GET /api/stream/device-state`.

### Settings and system

- Model: `GET|PUT /api/settings/model`; server reconnect uses `GET /api/system/server-status`.
- Email: `GET|PUT /api/settings/email`, password delete, connection test and test email.
- Readiness/devices: `GET /api/system/readiness`, `POST /api/system/devices/select`, `GET /api/devices`.
- ADB/emulator: status, launch, stop, dismiss, restart, remote server probe/connect/local.
- Credentials/config environment and Windows startup endpoints remain backend-owned.

### Schedules

- `GET|POST /api/schedules`, `GET|PATCH|DELETE /api/schedules/{id}`.
- `POST /api/schedules/preview` must return five occurrences in the UI contract.
- Optimistic updates pass `expected_version`; IDs are URL encoded.
- Manual run creates an idempotency key.
- Runs/history and email retry/report endpoints do not rerun the task.

## Preference and security contract

`artemis.ui.preferences.v1` has schema `{ version: 1, language: 'en'|'vi', theme: 'light'|'dark' }`. Invalid or unavailable storage falls back to English/light while keeping in-memory changes. Theme and language are applied to the root document. Secrets stay in backend storage and password/API key drafts stay in component memory only.

## Existing baseline defects

- Angular `npm run i18n:check` fails before migration changes because the Vietnamese catalog contains the extra key `model.urlHint`. This is tracked as a pre-existing regression and is not evidence of a Next.js failure.

## Realtime timing and ordering baseline

- Agent status polling: every 2 seconds; session polling: every 6 seconds. Both pause while the document is hidden and refresh immediately when visible again.
- Readiness polling: every 3 seconds with one shared in-flight request, stale timestamp rejection and duplicate-payload suppression. Emulator status polling: every 1 second.
- Foreground LLM stream chunks are coalesced for 80 ms; hidden-tab chunks for 500 ms. Chunk identity is `(execution_id, stream_type)`. Pending chunks must flush before every non-stream event; `llm_stream_reset` first discards buffered text for the matching identity, then applies the reset notice through the reducer.
- `trace_recorded` events are deduplicated by `trace_id`. Malformed SSE JSON currently has a raw-data compatibility branch that fixtures must define explicitly.
- Step snapshots merge with live data and use load-generation/request guards. Responses for a session that is no longer selected must not overwrite current state.
- Video finalization retries between 500 and 3000 ms, has a 120-second deadline and rejects responses from an older session/video generation.
- Model restart polling begins after about 2.5 seconds, repeats about every 1.5 seconds, has an approximately 90-second deadline and applies a 1.2-second timeout to each status request. The original PUT must never be replayed.
- The Angular EventSource currently relies mostly on browser auto-reconnect; explicit connection state, bounded backoff and snapshot-after-reconnect are migration improvements and therefore require compatibility/race tests.

## Required realtime fixtures before cutover

1. Fake-timer tests for 2s/6s polling, hidden/visible transitions and Strict Mode cleanup.
2. SSE tests for 80/500 ms coalescing, flush ordering, duplicate trace IDs, malformed JSON and reconnect plus snapshot.
3. Race tests for stale snapshot after a live event, session switch during a request and overlapping polls.
4. Per-item validation for `artemis.sessions.v1`; reject malformed, secret-bearing or unreasonably large cached payloads.
5. Restart tests for the 1.2s request timeout, 1.5s cadence and 90s deadline, proving the model PUT is not resubmitted.
6. A documented multi-session policy deciding whether non-selected-session events are buffered in a per-session store or dropped.
7. Schedule preview cancellation/generation tests when any relevant draft field changes.
8. Redaction tests for model config/environment previews and all runtime error payloads.
9. Runtime parser fixtures normalizing epoch seconds, epoch milliseconds and ISO timestamp strings to one internal representation.
10. Schedule preview fingerprint/generation tests: changing any contract field invalidates preview; HTTP 409 `expected_version` becomes an inline conflict while preserving the draft.
11. One root poll-coordinator fixture for status, sessions, readiness and emulator requests, including visibility pause/resume and overlap prevention; page-local effects must not create duplicate polls.

## Workspace implementation sequence

Port realtime functionality in dependency order: pure aggregators → session reducer → snapshot reconciler → SSE controller → poll coordinator → session selection/pin/auto-follow → notes/checks → pause/retry → live/video/replay → legacy `/check`. The migration acceptance criterion is lifecycle and state consistency, not merely converting Angular templates to JSX.

## Component boundary and CSS constraints

- Angular coupling hotspots are not 1:1 port candidates: Home/Settings is about 1,170 TS, 2,089 HTML and more than 4,800 SCSS lines; AgentStream is about 2,235 TS plus 1,436 HTML lines; AgentService is about 2,039 TS lines.
- Most Angular components communicate through singleton services rather than inputs/outputs. React uses props/callbacks for local UI state and the root provider/store for task, SSE, session and player state that must survive route changes.
- Workspace and legacy `/check` share task/session transport. A page-local provider would reset streams, players and drafts, so the provider remains above the route layout.
- Model settings and Windows startup previously called HttpClient directly from components. Their endpoints belong in typed feature API modules before UI code calls them.
- CSS migration must map Angular form state such as `.ng-invalid.ng-touched` to explicit React classes or `data-state` attributes, in addition to replacing `:host`, `app-*` and `::ng-deep`/CDK overlay selectors.
- Canvas/image-overlay helpers are browser-only even when otherwise pure; import or execute them only from client components and test them with a DOM/browser environment.

## Coverage and localization gaps

- Significant hard-coded English remains in Angular Android/System settings, tooltips and formatter/service runtime strings. Representative Vietnamese assertions do not prove full locale parity.
- Direct component/service coverage is missing for Home, Workspace, the primary AgentStream, ChatInterface, legacy `/check` and TaskRecommendationService. Pure reducer/utility coverage cannot substitute for browser behavior tests in these areas.
- Next cutover therefore requires a hard-coded-text inventory and production-browser coverage of these routes; no frontend coverage percentage is claimed from the current Angular suite.

## Home and Settings implementation validation gaps

- Home and all five Settings tabs are implemented with typed same-origin APIs, query/keyboard tab navigation, mounted hidden panels that preserve dirty drafts, write-only credential fields and single-mutation model restart handling.
- Home recommendations remain a representative subset rather than the complete Angular smart-task catalog. Readiness now refreshes every 3 seconds, pauses while hidden, refreshes immediately on visible/focus, prevents overlapping requests, aborts on cleanup and preserves dirty drafts; three lifecycle integration tests pass.
- Android/System settings implement the confirmed ADB/device/wireless/emulator contracts, including emulator logs, retry/stop/dismiss and visibility-aware non-overlapping 1-second startup polling. Clipboard/onboarding depth and physical-device execution across the OS matrix remain open; some readiness probe actions are informational because no safe mutation contract exists.
- Email and Android/System body copy now use the typed EN/VI catalog. The four-combination Settings matrix verifies translated headings/labels, root language/theme, focus preservation, dirty SMTP/password values and no settings/emulator GET replay across local/cross-tab preference changes.
- Workspace owns accepted-run startup/session tracking; the complete end-to-end transition from Home submission to route-stable Workspace state has not been browser-verified.
- P2 component tests cover invalid cross-tab payloads, storage listener cleanup, Preferences accessibility, and preservation of Home, Email, Model/secret and Schedule drafts across local/cross-tab preference changes. Managed Chromium now covers the complete locale/theme prepaint and hydration matrix; P2's integration gate is complete.

## Schedule implementation validation gaps

- Schedule API contract coverage exists for CRUD, `expected_version`, recurrence seconds/timezone/weekdays, preview aliases, idempotent run-now, paged history, device/status normalization and isolated email retry/report URLs. A TypeScript parser check passed the schedule TS/TSX source files.
- React interaction tests execute for preview generation/exact-five behavior, inline 409 conflict with preserved draft, direct-backdrop handling, initial focus, bidirectional focus trap, Escape close and logical opener focus restoration in editor/history dialogs. Schedule email configuration readiness is now derived conservatively from `GET /api/settings/email`, with ready/not-configured/request-error states and no connection-test or email send side effects. The backend exposes no stronger readiness contract.
- Session navigation uses a Workspace query URL instead of proving integration with the complete root session-selection policy.
- Schedule copy is bilingual but partly feature-local rather than fully represented in the central catalog. Hard-coded-text and placeholder parity gates therefore remain open.
- These gaps prevent declaring the P3 acceptance gate complete even though the feature and typed API modules have been implemented.

## Verified packaging and media evidence

- A Windows Next wheel was built through isolated `uv build`; it contains 43 `showcase_next` files, no Angular tree and no Node runtime files. Isolated import/resource lookup from the unpacked wheel succeeds.
- Workspace media contracts now have seven executing tests covering 500–3000 ms finalization retry, 120-second deadline, generation/session guards and multi-segment timeline mapping.
- The exported artifact contains 43 files and approximately 1.10 MB uncompressed; detailed measurements are in `docs/nextjs-migration-performance.md`.

## Workspace implementation validation gaps

- The root `WorkspaceProvider`, typed API/cache/reducer/selectors, modern Workspace route and distinct legacy `/check` route are implemented. Browser API/SSE setup is root-mounted, uses bounded reconnect, visibility-aware 2s/6s polling, request ordering and per-item validation for `artemis.sessions.v1`.
- SSE handling now implements session-scoped `(execution_id, stream_type)` 80/500 ms chunk coalescing, reset-buffer discard, trace dedupe, conservative foreign/sessionless event rejection and explicit checker parent/trace aggregation. Browser EventSource/reconnect validation remains open.
- Live media uses the confirmed MJPEG device endpoint with manual retry; video finalization and multi-segment timeline mapping are implemented and unit-tested. Browser runtime, Range playback and Angular auto-open/minimize behavior remain unverified.
- A headless Edge smoke successfully rendered and hydrated the exported Home through the controlled FastAPI fixture. The hermetic fixture now executes full and single-range video responses (200/206/416 with exact headers/body) plus a finite two-frame MJPEG stream without device access; its direct HTTP integration passes and Playwright request-context assertions are defined. Session switching, reconnect, duplicate/out-of-order EventSource behavior and route-stable media-element playback still need managed-browser assertions.
- Full lint, strict typecheck, Vitest and static export execute successfully. Vitest now reports 22 files and 119 passing tests, including preference/cross-tab dirty drafts, Workspace provider lifecycle, Home readiness lifecycle, Schedule SMTP configuration readiness and Android emulator lifecycle. Emulator polling runs every second only during startup states, is non-overlapping, pauses/aborts while hidden, resumes immediately when visible, aborts on cleanup, and covers logs/retry/stop/dismiss actions. React `act(...)` warnings remain test-harness cleanup; broader browser/backend-runtime validation remains open.
- The P4 integration gate is complete through reducer/realtime/media fixtures, route-child provider remount evidence and managed-browser static/media acceptance. Real physical-device and long-running live-task exercises remain P5 release gates rather than claims of broader environment parity.

## Known migration risks

1. The Angular agent service is a large combined session/SSE/polling/video store; React must split transport, reducer and selectors without multiplying connections under Strict Mode.
2. Home, stream and workspace templates/styles are very large; parity must be measured behavior-first rather than copied blindly.
3. Existing FastAPI hosting is SPA fallback based. Next export requires exact route HTML, a real 404, full `_next` tree and differentiated cache headers.
4. Model save intentionally restarts the backend. The client must not replay the mutation while reconnecting.
5. Schedule mutations are versioned and manual run is idempotent; generic automatic mutation retry is forbidden.
6. Live/replay media, Range responses and SSE are backend paths and must not be intercepted by static hosting.

## Rollback drill evidence

Deterministic selector/static-host/resource tests verify Angular remains the default, Next can be selected explicitly, and returning to Angular restores its independent SPA behavior. A dedicated same-client/same-origin drill switches Angular → Next → Angular while preserving `/api/*` and `/admin` responses; its static-host suite reports 12 passing tests, and the wider focused rollback suite reports 23 passing tests. A live long-running-task rollback exercise on packaged executables remains open.

## Baseline verification checklist

- Angular remains selectable and its existing tests continue to run until cutover.
- Next build succeeds with no backend, Android device or credentials.
- Direct refresh works for all five UI routes and preserves query strings.
- Missing static assets and API paths return 404 rather than Home HTML.
- EN/VI and light/dark combinations do not reset drafts, streams or media players.
- Managed Chromium acceptance now passes 28/28 tests against the controlled FastAPI fixture, covering EN/VI × light/dark prepaint/hydration, all exported routes and reloads, client navigation, cross-page storage events, query preservation without mutation, immutable assets, 404/reserved-path isolation, full/Range video, finite MJPEG, and `/admin` priority. Browser execution exposed and fixed an unbound native `setInterval` call in the Workspace poll coordinator. Playwright's webServer launcher now resolves the repository `.venv` Python portably (or `ARTEMIS_ACCEPTANCE_PYTHON`/`python` fallback), so the ordinary acceptance command starts its own fixture successfully instead of depending on whichever Python happens to be on PATH. CI never sends real email or changes host startup settings. Package CI is configured as an Ubuntu/Windows/macOS matrix with portable clean-venv interpreter and CLI paths for both Angular-default and Next-selected wheels; hosted-runner execution evidence is still pending.
