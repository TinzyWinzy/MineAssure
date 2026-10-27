# Threat model and pilot release gates

Assets: contract versions/rates, operational evidence, invoice snapshots, allocation balances, user/site authority, decisions, export artifacts and audit provenance. Actors: scoped preparer, contract approver, verifier, AP analyst, finance approver, auditor, partner viewer and tenant administrator; untrusted browser/client; database/platform operator.

| Threat | Required control / verification |
| --- | --- |
| Cross-tenant/site object access | Scope parent and child objects, derive authority server-side, exercise IDOR tests across roles and sites; add database RLS before customer deployment. |
| Forged evidence or reviewer | Ignore caller-supplied verified balances and reviewer names; read attested stored records and authenticated actor. Distinct preparer/approver checks. |
| Concurrent reuse of work | Lock evidence rows inside transactions; enforce allocation conservation under real PostgreSQL contention. |
| Stale or repeated approval/export | Lock current run/results, verify version/authority, persist immutable decisions and export rows, reject stale mutation and repeated postings. |
| Contract/evidence tampering | Approved immutable inputs, version/hash provenance and append-only audit; restrict database write credentials and protect backups. |
| Malicious spreadsheet/document | Bounded accepted formats, strict schema and size, precise row errors, quarantine and malware scan before binary document retrieval. No arbitrary formulas or executable content. |
| Credential theft/privilege escalation | Production verified identity, MFA, short sessions, secrets rotation, no demo login outside explicit development. |
| Export disclosure/CSV injection | Scope exports and downloads; emit server-selected fields; guard spreadsheet formula prefixes in user text. |
| Loss or false audit confidence | Backup/restore rehearsal; access-restricted append-only logs; report unimplemented provider/storage guarantees. |

Local demonstration uses loopback HTTP and synthetic data. It has not established a production TLS boundary, managed OIDC/MFA, database RLS, malware scanning, jurisdictional compliance or an independently reviewed hosting configuration. These are concrete release gates, not implied certifications.

Never connect production customer, payment, ERP, mine telemetry or partner planning systems without explicit authorization. Do not add real documents to the demo fixture set.
