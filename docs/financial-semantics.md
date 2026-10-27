# Financial semantics for the synthetic hourly-hire pilot

Currency: USD. Unit: hour. Financial calculations use Python `Decimal`, PostgreSQL NUMERIC and integer cents in exports. Browser formatting does not determine payable amounts. Tax, retention, minimums, standby, escalation, foreign exchange and complex variations are outside the supported policy until explicitly implemented and tested.

| Category | Meaning |
| --- | --- |
| Invoiced | Invoice quantity multiplied by invoice rate under the supported pricing policy. |
| Provisionally supported | Amount linked to attested eligible evidence and an approved effective contract rate. It remains subject to human approval. |
| Unverified | Amount whose support cannot be determined because evidence, authorization or matching is missing or conflicting. It is not a proven overcharge. |
| Quantified variance | A single nonnegative comparison between billed and determined supported amounts. Rule warnings are never summed to produce exposure. |
| Approved | Explicit amount accepted by an authorized distinct finance actor, within eligible bounds and authority. |
| Confirmed adjustment | A separately recorded agreed correction. It must not be inferred from an alert. |
| Recovered cash | Separately evidenced receipt or recovery. The current pilot does not claim this metric. |

## Golden arithmetic

Scenario A: 160 × $250 = $40,000 invoiced. Independently attested 145 × approved $240 = $34,800 provisionally supported. The discrepancy is $5,200, once, even though both rate and quantity rules fire. A review can approve part of the $34,800; export contains only that decision amount.

Scenario B: 10 × $240 = $2,400, with no supporting evidence. All $2,400 is unverified. Quantified variance is undetermined (a numeric zero is only a storage representation with that interpretation). Approved amount is zero until adequate evidence and a new eligible run exist.

## Invariants

Approved amounts cannot be negative, exceed the invoiced/eligible amount or include an unresolved unverified portion. An evidence quantity cannot be reserved or consumed twice. A newer reconciliation cannot silently change an older snapshot; stale decisions fail. An export repeats the immutable approved decision snapshot, not a live recalculation. Repeated requests must not create additional postings.

Amounts must round using the documented server policy at the currency boundary; inspect `app/engine.py` and automated tests for the currently executed rounding mode. No customer tolerance, tax or rounding assumption should be inferred from the simple example.
