# README screenshots

Captured on 2026-09-16 from the real application at http://localhost:8009/.
English UI, dark theme, 1440×960 viewport; new-schedule.png is cropped to the dialog.
Solid slate rectangles redact task text, account/device identifiers and device media.
Screenshots are not mocked UI or AI-generated images.

The capture script uses an isolated browser profile, only allows read-only API
requests, selects an existing session, and opens (but does not save) a new schedule.
It does not start tasks, send email, change backend settings or modify the user's
browser preferences. Review every screenshot for sensitive content before publishing.

To refresh, start the app on port 8009, then from apps/showcase_next run:

```text
node scripts/capture-readme.mjs
```

Playwright requires a browser. Set PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH to a local
Chrome/Chromium executable if Playwright's Chromium is not installed.
