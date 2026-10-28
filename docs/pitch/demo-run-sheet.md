# Demo run-sheet — 163 Solutions call

Deck: `docs/pitch/163-solutions-partner-deck.html` (open in browser, F11, arrows to advance, `n` for notes).
System: http://127.0.0.1:5173 — all personas use password `demo`.

## Pre-flight (verified 28 Oct)

| Check | Result |
| --- | --- |
| API `/health`, `/ready` | ok / ready |
| Web on 5173 | HTTP 200 |
| Worker | Alive; processed a test job and correctly rejected a decided invoice |
| Demo data | 4 invoices, 3 reconciled; approval recorded on `ACME-2026-041` (34,800); export still open |
| Dashboard | invoiced 87,200 · supported 34,800 · unverified 47,200 · variance 5,200 · **approved 34,800** |

Note: the stack is on migration **0010** with the purge and signing-key changes. Approval for `ACME-2026-041` is already recorded at run version 2. **Do not click Approve again** — it returns "Line already has an immutable decision". The export is still available and is the only live finance action in step 6.

## Before you share

- Close Slack, mail, and anything with client names.
- Share the **browser tab**, not the whole screen.
- 100% zoom, bookmarks bar hidden.
- Have two tabs: deck, app. Do not hunt for windows live.

## The 8-minute show

| Step | Login | Do | Say |
| --- | --- | --- | --- |
| 1 | `ap@demo.local` | Dashboard | "These are amount categories, not savings." |
| 2 | same | Open invoice `ACME-2026-041` | "Invoice says 250 an hour. Approved contract says 240." |
| 3 | same | Reconcile → wait for completed → open outcomes | "160 hours invoiced, 145 attested, 5,200 variance counted once." |
| 4 | same | Point at formula steps and frozen sources | "This is the evidence a modeller or auditor can follow." |
| 5 | same | Open `ACME-2026-042` | "2,400 unverified. Not an overcharge — the evidence is missing." |
| 6 | `finance@demo.local` | Show the recorded 34,800 approval, then Export approved costs | "A different person decided. The export carries the run and approval hashes." |
| 7 | same | Audit trail | "Every action is attributable. Nothing here is reconstructed." |

Stop at seven. If he asks about admin, files, or integrations, answer verbally and move on.

## Fallbacks

- **Reconciliation stays queued:** "The worker is still processing; here is the same outcome from the completed run" — open the existing run on `ACME-2026-041`. Do not debug live.
- **Login fails:** check `/ready` once. If it is down, switch to the deck's control-model slide and say the local demo is unavailable; do not improvise claims.
- **He asks to see his own data:** say the pilot mapping is the next step, not a live improvisation.
- **He asks for SSO / ERP / Anaplan integration:** "Not in the pilot. Scoped after the workflow is proven."

## Lines to avoid

- "Saves you X" / "recovers X" — say variance, unverified, approved.
- "Production-ready", "enterprise-grade", "AI-powered".
- "We integrate with Anaplan" — no connector exists.
- "We have clients" — no paying customers yet.
