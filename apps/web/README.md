# MineAssure web interface

React, TypeScript and Vite frontend for the native synthetic pilot. Start all services using [local development](../../docs/local-development.md).

From this folder:

```sh
npm ci
npm run dev -- --host 127.0.0.1
npm run lint
npm run build
npx playwright install chromium
npm run test:e2e
```

Browser tests expect API, worker and web to be running. E2E_WEB_URL and E2E_API_URL override localhost defaults. Tests create uniquely named synthetic contracts, invoices, sites and local users in the development database; they do not call external systems. Failure traces/screenshots are ignored under test-results/.

The sign-in token stays in memory. API values for money remain decimal strings; the UI formats them for display. Server authorization and monetary policy govern every mutation. New local users can enter their email directly in the sign-in field. The seeded verifier2 account supports independent attestation.
