# README screenshots

Home, Workspace and Task Schedule were captured on 2026-11-11 from the real
application at http://localhost:8009/. These are the three images displayed in
the root README. English UI, dark theme, 1440×960 viewport.
Private task text, session history, device identifiers, email recipients and
device media are blurred in the disposable browser before capture.
The older settings.png and new-schedule.png are retained but not displayed.
Screenshots are not mocked UI or AI-generated images.

The capture script uses an isolated browser profile, only allows read-only API
requests and selects an existing session for the Workspace screenshot.
It does not start tasks, send email, change backend settings or modify the user's
browser preferences. Review every screenshot for sensitive content before publishing.

To refresh, start the app on port 8009, then from apps/showcase_next run:

```text
node scripts/capture-readme.mjs
```

Playwright requires a browser. Set PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH to a local
Chrome/Chromium executable if Playwright's Chromium is not installed.
