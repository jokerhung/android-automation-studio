# Angular appearance on Next.js

The Next frontend now uses shadcn/ui's new-york Radix components (source owned
in `src/components/ui`, upstream MIT notice in `public/licenses/shadcn-ui.txt`).
`components.json` configures the registry; Tailwind utilities are compiled by
PostCSS. The existing `data-theme` preference controls shadcn's dark variant.

`angular-tokens.css` preserves the Angular semantic palette.
`angular-parity.css` defines the application-specific visual contract: floating
navigation, 960px Home, 220px Settings sidebar, right-hand Workspace task rail,
compact controls, and light/dark surfaces. Do not replace these with default
shadcn black/white tokens. Local Inter/Outfit font packages avoid runtime CDN
requests. Home recommendations and bilingual tuning copy are ported from the
Angular reference; migrated task IDs and English goals stay compatible.

Validation commands:

```text
npm run lint
npm run typecheck
npm test
npm run build
npm run budget:check
npm run test:acceptance
node scripts/capture-design.mjs
```

The capture script hosts compiled assets in an ephemeral local server and mocks
API requests. Set `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` when Chrome is not installed
at the Windows default path. Screenshots go to ignored `test-results/design/`.
Angular source/builds have been retired; captures now use only the Next export.
Browser regression tests verify sizes, rail placement, mobile overflow and dirty
draft retention. They do not establish pixel-for-pixel equivalence for every
runtime session state. The migrated Workspace still has its own details renderer;
it is not the original Angular agent-stream component.

No backend, real schedule, SMTP setting, Windows startup entry or active task was
changed by the styling work. Switching Settings tabs retains mounted forms and
their unsaved values. Native form/select controls remain where replacing their
semantics would unnecessarily change the migrated behavior.
