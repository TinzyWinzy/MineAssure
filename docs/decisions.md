# Implementation decisions and source conflicts

25 October 2026. Evidence source order: master build prompt, engineering review, PRD, SAD, existing implementation. Original PRD/SAD paragraph transcriptions are retained in this directory.

| Decision | Rationale and consequence |
| --- | --- |
| Modular monolith; PostgreSQL transactions | Preserve the supplied FastAPI/SQLAlchemy stack and keep invoice, allocation, approval and export transitions within a single transaction. See ADR-001. |
| USD hourly equipment hire only | Complex tax, standby, minimums, escalation, conversions and other pricing models require a signed financial policy. Unsupported inputs must fail or remain unverified. |
| No evidence means undetermined | Earlier prototype rules could present absent evidence as a proven overcharge. The master prompt overrides this: classify the invoiced amount as unverified and block approval. |
| Distinct preparation and approval | Tenant administration does not imply finance authority. Contract preparers and AP analysts do not approve their own financial inputs. |
| Application-scoped pilot | Database row-level security and externally verified identity remain separate release gates. Do not describe application policy checks as a complete production tenancy boundary. |
| Synthetic data only | Demonstration records do not establish precision, savings, production scale or regulatory compliance. No ERP, Anaplan or payment connection is authorized. |
| Local development startup | Compose binds services to loopback and uses explicit development settings. Default credentials are demonstration credentials, not deployment secrets. |
| Source API prefix | Use `/api/v1` rather than the SAD's illustrative `/v1` paths. Runtime OpenAPI is the endpoint authority. |

## Cabinet participation

The OpenCode cabinet was found at `C:/Users/USER/.config/opencode`, with runtime source at `C:/Users/USER/Documents/Altar/FORGE-Cabinet`. Its adaptive routing and implementation skills call for specialists, adversarial review and deterministic verification for financial/security work. Responsibilities were split between backend implementation, independent tests/security review, delivery documentation and the main frontend/integration agent. This records workflow participation; it does not assert that the OpenCode plugin executed or certified the application.

## Open customer decisions

Confirm actual site and work codes; legal contract wording; any tax, caps, minimums and standby; identity provider and MFA; monetary delegations and override policy; hosting jurisdiction and privacy requirements; source verification owner; partner dataset approval; retention; SLA; backup RPO/RTO; and customer data-use authorization before a live pilot.
