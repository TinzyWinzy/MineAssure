import { useCallback, useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { api, download, money } from './api'
import type { Row } from './api'
import { ContractVersions } from './ContractVersions'
import { Administration } from './Administration'
import { ReconciliationButton } from './ReconciliationButton'
import { RecordPanel } from './RecordPanel'
import { FileCenter } from './FileCenter'
import { OutcomePanel } from './OutcomePanel'
import { Badge, Empty, Field, Load, ApprovalForm, Settings } from './views'
import { useData } from './hooks'
import type { Props, Scope } from './hooks'

const sections = [
  'Overview',
  'Contractors',
  'Contracts',
  'Evidence',
  'Files',
  'Invoices',
  'Exceptions',
  'Approvals',
  'Exports',
  'Audit',
  'Settings',
]
const glyphs = ['O', 'S', 'C', 'E', 'F', 'I', 'X', 'A', 'X', 'A', 'S']
const personas = [
  'ap',
  'finance',
  'verifier',
  'verifier2',
  'preparer',
  'approver',
  'auditor',
  'admin',
  'partner',
]
const descriptions: Record<string, string> = {
  Overview: 'Follow the evidence. Resolve the exceptions. Approve with confidence.',
  Contractors: 'Supplier identities behind every contract and invoice.',
  Contracts: 'Approved terms are the foundation of every calculation.',
  Evidence: 'Independent work records, verified by operations.',
  Files: 'Process input files, validate associations, and download ingestion outputs.',
  Invoices: 'From submitted costs to explainable, reviewed actuals.',
  Exceptions: 'A focused queue for findings that need human judgment.',
  Approvals: 'Authorize eligible amounts with a distinct finance reviewer.',
  Exports: 'Immutable approved-cost snapshots for your finance workflow.',
  Audit: 'The actor, action, and source behind every decision.',
  Settings: 'Your identity, site access, and pilot boundaries.',
}
export default function App() {
  const [token, setToken] = useState('')
  const [user, setUser] = useState<Row | null>(null)
  const [scope, setScope] = useState<Scope>({ org_id: 'org-demo', site_id: 'site-1' })
  const [sites, setSites] = useState<Row[]>([])
  const [page, setPage] = useState(location.hash.slice(1) || 'Overview')
  const [selected, setSelected] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const [revision, setRevision] = useState(0)
  const [menu, setMenu] = useState(false)
  const query = new URLSearchParams(scope).toString()
  const roles = (user?.memberships || [])
    .filter((m: Row) => m.org_id === scope.org_id && (!m.site_id || m.site_id === scope.site_id))
    .map((m: Row) => m.role)
  const can = (...allowed: string[]) => roles.some((r: string) => allowed.includes(r))
  useEffect(() => {
    const fn = () => {
      setPage(location.hash.slice(1) || 'Overview')
      setSelected(null)
      setError('')
      setMenu(false)
    }
    window.addEventListener('hashchange', fn)
    return () => window.removeEventListener('hashchange', fn)
  }, [])
  const act = useCallback(async (fn: () => Promise<unknown>, message = 'Changes saved.') => {
    setError('')
    setNotice('')
    setBusy(true)
    try {
      await fn()
      setNotice(message)
      setRevision((r) => r + 1)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }, [])
  async function login(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const f = new FormData(e.currentTarget)
    await act(async () => {
      const d = await api('/auth/dev-login', '', {
        email: f.get('email'),
        password: f.get('password'),
      })
      const [me, s] = await Promise.all([
        api('/auth/me', d.access_token),
        api('/sites', d.access_token),
      ])
      setUser(me)
      setSites(s)
      if (s.length) setScope({ org_id: s[0].org_id, site_id: s[0].id })
      setToken(d.access_token)
    }, 'Signed in to the synthetic pilot.')
  }
  useEffect(() => {
    if (!token) return
    let active = true
    api('/sites', token)
      .then((s) => {
        if (active) setSites(s)
      })
      .catch(() => {})
    return () => {
      active = false
    }
  }, [token, revision])
  if (!token)
    return (
      <div className="login">
        <div className="login-story">
          <a className="brand" href="#Overview">
            <span className="brand-mark">M</span>MineAssure<span className="brand-dot">.</span>
          </a>
          <div>
            <span className="eyebrow">Nexus Agronomics / Proof-to-Pay</span>
            <h1>
              Every invoice.
              <br />
              Backed by evidence.
            </h1>
            <p>A clear line from approved contract terms to verified work and reviewed costs.</p>
            <div className="proof-strip">
              <span>Contract</span>
              <i>→</i>
              <span>Evidence</span>
              <i>→</i>
              <span>Assurance</span>
            </div>
          </div>
          <small>Built for accountable mine operations.</small>
        </div>
        <main className="login-form">
          <div className="demo-note">Synthetic pilot · Demo data only</div>
          <h2>Welcome to MineAssure</h2>
          <p>Sign in with a scoped pilot account.</p>
          <form onSubmit={login}>
            <Field label="Pilot account">
              <input
                name="email"
                type="email"
                list="pilot-accounts"
                defaultValue="ap@demo.local"
                autoComplete="username"
                required
              />
              <datalist id="pilot-accounts">
                {personas.map((p) => (
                  <option key={p} value={`${p}@demo.local`} />
                ))}
              </datalist>
            </Field>
            <Field label="Password">
              <input
                name="password"
                type="password"
                autoComplete="current-password"
                required
                defaultValue="demo"
              />
            </Field>
            {error && (
              <div role="alert" className="error">
                {error}
              </div>
            )}
            <button className="primary wide" disabled={busy}>
              {busy ? 'Signing in…' : 'Sign in →'}
            </button>
          </form>
          <p className="muted small">
            Local development access only. Separate accounts enforce preparation, verification, and
            finance approval duties.
          </p>
        </main>
      </div>
    )
  const props = { token, userId: user?.id || '', scope, query, revision, busy, act, can }
  return (
    <div className="app">
      <a className="skip" href="#main-content">
        Skip to content
      </a>
      <aside className={menu ? 'sidebar open' : 'sidebar'}>
        <a className="brand" href="#Overview">
          <span className="brand-mark">M</span>MineAssure<span className="brand-dot">.</span>
        </a>
        <div className="workspace-label">Assurance workspace</div>
        <nav aria-label="Main navigation">
          {sections.map((s, i) => (
            <a
              key={s}
              href={`#${s}`}
              aria-current={page === s ? 'page' : undefined}
              className={page === s ? 'active' : ''}
            >
              <span aria-hidden="true">{glyphs[i]}</span>
              {s}
            </a>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <span className="status-dot" />
          Synthetic pilot<div>Nexus Agronomics</div>
          <small>Proof before approval.</small>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <button
            className="mobile-toggle"
            onClick={() => setMenu(!menu)}
            aria-label="Toggle navigation"
          >
            ☰
          </button>
          <div className="breadcrumb">
            Workspace <span>/</span> <strong>{page}</strong>
          </div>
          <div className="top-actions">
            <select
              aria-label="Mine site"
              value={scope.site_id}
              onChange={(e) => {
                const s = sites.find((s) => s.id === e.target.value)
                if (s) {
                  setScope({ org_id: s.org_id, site_id: s.id })
                  setSelected(null)
                }
              }}
            >
              {sites.map((s) => (
                <option value={s.id} key={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
            <button
              className="avatar"
              aria-label={`Sign out ${user?.email}`}
              onClick={() => {
                setToken('')
                setUser(null)
                setError('')
                setSelected(null)
              }}
            >
              ↪
            </button>
          </div>
        </header>
        <div className="demo-banner">
          <span className="status-dot" />
          Demo data{' '}
          <span>
            All records are synthetic. Exports contain reviewed costs; no payments are initiated.
          </span>
        </div>
        <main id="main-content" className="content">
          <div className="page-heading">
            <div>
              <div className="eyebrow">
                {sites.find((s) => s.id === scope.site_id)?.name || 'Pilot site'} / USD
              </div>
              <h1>
                {selected
                  ? 'Invoice review'
                  : page === 'Overview'
                    ? 'Clarity before commitment.'
                    : page}
              </h1>
              <p>{descriptions[page]}</p>
            </div>
            <div className="identity">
              <span className="avatar initials">
                {String(user?.email).slice(0, 2).toUpperCase()}
              </span>
              <div>
                {user?.email}
                <small>{roles.join(', ').replaceAll('_', ' ')}</small>
              </div>
            </div>
          </div>
          {error && (
            <div role="alert" className="error">
              {error}
              <button onClick={() => setError('')} aria-label="Dismiss error">
                ×
              </button>
            </div>
          )}
          {notice && (
            <div role="status" className="notice">
              {notice}
              <button onClick={() => setNotice('')} aria-label="Dismiss notice">
                ×
              </button>
            </div>
          )}
          {busy && (
            <div className="pending" role="status">
              Saving and refreshing records…
            </div>
          )}
          {selected ? (
            <InvoiceDetail {...props} id={selected} back={() => setSelected(null)} />
          ) : page === 'Overview' ? (
            <Overview {...props} open={setSelected} />
          ) : page === 'Files' ? (
            <FileCenter key={scope.site_id} {...props} openInvoice={setSelected} />
          ) : page === 'Settings' ? (
            <>
              <Settings user={user} sites={sites} />
              {can('tenant_admin') && <Administration {...props} userId={String(user?.id)} />}
            </>
          ) : sections.includes(page) ? (
            <Resource key={page + scope.site_id} {...props} page={page} open={setSelected} />
          ) : (
            <Empty>Page not found. Select a page from the workspace navigation.</Empty>
          )}
        </main>
        <footer className="workspace-footer">
          <span>MineAssure · Nexus Agronomics</span>
          <span>Evidence → Review → Approved actuals</span>
        </footer>
      </div>
    </div>
  )
}

function Overview(p: Props & { open: (id: string) => void }) {
  const { data, error } = useData(`/dashboard?${p.query}`, p.token, p.revision)
  const totals = data?.totals || data || {}
  return (
    <Load error={error} data={data}>
      <div className="metric-grid">
        {[
          ['Invoiced', 'invoiced_amount', 'Submitted contractor costs'],
          ['Provisionally supported', 'supported_amount', 'Calculated from eligible evidence'],
          ['Unverified', 'unverified_amount', 'Evidence or approved terms required'],
          ['Quantified variance', 'quantified_variance', 'Calculated difference, not savings'],
        ].map(([label, key, description]) => (
          <div className={`metric ${key}`} key={key}>
            <span>{label}</span>
            <strong>{money(totals[key])}</strong>
            <small>{description}</small>
          </div>
        ))}
      </div>
      <div className="overview-grid">
        <section className="panel">
          <div className="panel-heading">
            <div>
              <h2>Invoice workbench</h2>
              <p>One current assessment per invoice.</p>
            </div>
            <a className="text-link" href="#Invoices">
              All invoices ↗
            </a>
          </div>
          <InvoiceTable rows={data?.invoices || []} open={p.open} />
        </section>
        <section className="assurance-panel">
          <span className="eyebrow">The assurance chain</span>
          <h2>
            Proof before
            <br />
            approved actuals.
          </h2>
          <ol>
            <li>
              <span>01</span>
              <div>
                Approved contract<small>Effective terms and hourly rates</small>
              </div>
            </li>
            <li>
              <span>02</span>
              <div>
                Verified work<small>Independent evidence and quantities</small>
              </div>
            </li>
            <li>
              <span>03</span>
              <div>
                Human review<small>Scoped finance authorization</small>
              </div>
            </li>
          </ol>
          <div className="approved-total">
            <span>Approved actuals</span>
            <strong>{money(totals.approved_amount)}</strong>
          </div>
          <a href="#Approvals">Review eligible amounts →</a>
        </section>
      </div>
      <section className="panel">
        <div className="panel-heading">
          <div>
            <h2>Recent activity</h2>
            <p>Decisions with a traceable source.</p>
          </div>
          <a className="text-link" href="#Audit">
            Audit history ↗
          </a>
        </div>
        <AuditTable rows={data?.recent_audit || []} />
      </section>
    </Load>
  )
}
function InvoiceTable({
  rows,
  open,
  manage,
}: {
  rows: Row[]
  open: (id: string) => void
  manage?: (id: string) => void
}) {
  return !rows.length ? (
    <Empty>No invoices in this site. Import a synthetic invoice to begin.</Empty>
  ) : (
    <div className="table-wrap cards" tabIndex={0} role="region" aria-label="Invoice records">
      <table>
        <thead>
          <tr>
            <th>Invoice / Contractor</th>
            <th>Status</th>
            <th className="numeric">Invoiced</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id}>
              <td data-label="Invoice / Contractor">
                <button className="link-button" onClick={() => open(r.id)}>
                  {r.supplier_invoice_no}
                </button>
                <small>{r.contractor_name || 'Equipment hire'}</small>
              </td>
              <td data-label="Status">
                <Badge>{r.status}</Badge>
              </td>
              <td data-label="Invoiced" className="numeric">
                {money(r.total ?? r.invoiced_amount)}
              </td>
              <td className="actions">
                <button
                  className="row-action"
                  onClick={() => open(r.id)}
                  aria-label={`Review ${r.supplier_invoice_no}`}
                >
                  ↗
                </button>
                {manage && <button onClick={() => manage(r.id)}>Details &amp; edit</button>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
function AuditTable({ rows }: { rows: Row[] }) {
  return !rows.length ? (
    <Empty>No audit events in this site yet.</Empty>
  ) : (
    <div className="table-wrap cards" tabIndex={0} role="region" aria-label="Audit records">
      <table>
        <thead>
          <tr>
            <th>Action</th>
            <th>Actor</th>
            <th>Entity / Reference</th>
            <th>Time</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id}>
              <td data-label="Action">{r.action}</td>
              <td data-label="Actor">{r.actor_email || r.actor_id || 'System'}</td>
              <td data-label="Entity / Reference">
                {r.entity_type}
                <small className="mono">{r.entity_id}</small>
              </td>
              <td data-label="Time">
                {r.created_at ? new Date(r.created_at).toLocaleString('en-ZA') : '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Resource(p: Props & { page: string; open: (id: string) => void }) {
  const paths: Record<string, string> = {
    Contractors: 'contractors',
    Contracts: 'contracts',
    Evidence: 'evidence',
    Invoices: 'invoices',
    Exceptions: 'cases',
    Approvals: 'approvals',
    Exports: 'exports',
    Audit: 'audit',
  }
  const { data, error } = useData(`/${paths[p.page]}?${p.query}`, p.token, p.revision)
  const [search, setSearch] = useState('')
  const [offset, setOffset] = useState(0)
  const [form, setForm] = useState(false)
  const [record, setRecord] = useState<string | null>(null)
  const rows: Row[] = Array.isArray(data) ? data : data?.items || []
  const filtered = rows.filter((r) =>
    JSON.stringify(r).toLowerCase().includes(search.toLowerCase())
  )
  const shown = filtered.slice(offset, offset + 12)
  const createAllowed =
    (p.page === 'Contracts' && p.can('contract_preparer', 'tenant_admin')) ||
    (p.page === 'Evidence' && p.can('operations_verifier', 'tenant_admin')) ||
    (p.page === 'Invoices' && p.can('ap_analyst', 'tenant_admin')) ||
    (p.page === 'Contractors' && p.can('tenant_admin'))
  const headers =
    p.page === 'Contractors'
      ? ['Contractor', 'Reference']
      : p.page === 'Contracts'
        ? ['Contract / Version', 'Effective from', 'Hourly rate', 'Status', 'Action']
        : p.page === 'Evidence'
          ? ['Work reference', 'Service date', 'Hours', 'Status', 'Action']
          : p.page === 'Exceptions'
            ? ['Finding / Case', 'Status', 'Investigation']
            : p.page === 'Approvals'
              ? ['Invoice line', 'Decision', 'Amount', 'Reviewer']
              : ['Batch', 'Status', 'Approved total', 'Artifact']
  return (
    <>
      <div className="toolbar">
        <label className="search">
          <span aria-hidden="true">⌕</span>
          <input
            aria-label={`Search ${p.page.toLowerCase()}`}
            placeholder={`Search ${p.page.toLowerCase()}…`}
            value={search}
            onChange={(e) => {
              setSearch(e.target.value)
              setOffset(0)
            }}
          />
        </label>
        {createAllowed && (
          <button className="primary" onClick={() => setForm(!form)}>
            {form
              ? 'Close form'
              : `+ ${p.page === 'Evidence' ? 'Register work' : 'Add ' + p.page.toLowerCase().replace(/s$/, '')}`}
          </button>
        )}
      </div>
      {record && (
        <RecordPanel
          key={record}
          {...p}
          kind={paths[p.page]}
          id={record}
          close={() => setRecord(null)}
          openInvoice={p.open}
        />
      )}
      {form && <CreateForm {...p} close={() => setForm(false)} />}
      {['Evidence', 'Invoices'].includes(p.page) && createAllowed && (
        <details className="panel import-panel">
          <summary>Import CSV / XLSX with validation and outputs</summary>
          <FileCenter
            {...p}
            kind={p.page === 'Evidence' ? 'evidence' : 'invoice'}
            openInvoice={p.open}
          />
        </details>
      )}
      <Load error={error} data={data}>
        <section className="panel">
          <div className="panel-heading">
            <h2>
              {p.page === 'Approvals'
                ? 'Decision history'
                : p.page === 'Exceptions'
                  ? 'Investigation queue'
                  : p.page}
            </h2>
            <span className="count">{filtered.length} records</span>
          </div>
          {p.page === 'Invoices' ? (
            <InvoiceTable rows={shown} open={p.open} manage={setRecord} />
          ) : p.page === 'Audit' ? (
            <AuditTable rows={shown} />
          ) : !shown.length ? (
            <Empty>
              {p.page === 'Approvals'
                ? 'Open an assessed invoice to record a finance decision.'
                : p.page === 'Exports'
                  ? 'Create an approved-cost export from an invoice after finance approval.'
                  : 'No matching records in this site.'}
            </Empty>
          ) : (
            <div className="table-wrap" tabIndex={0} role="region" aria-label="Scrollable records">
              <table>
                <thead>
                  <tr>
                    {headers.map((h) => (
                      <th key={h}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {shown.map((r) => (
                    <tr key={r.id}>
                      {p.page === 'Contractors' ? (
                        <>
                          <td>
                            {r.name}
                            <button className="record-action" onClick={() => setRecord(r.id)}>
                              Details &amp; edit
                            </button>
                          </td>
                          <td className="mono">{r.id}</td>
                        </>
                      ) : p.page === 'Contracts' ? (
                        <>
                          <td>
                            {r.title}
                            <small>
                              {r.work_code || 'EQ-HIRE'} · Version {r.version_no || 1}
                            </small>
                            <ContractVersions {...p} contract={r} />
                            <button className="record-action" onClick={() => setRecord(r.id)}>
                              Details &amp; edit
                            </button>
                          </td>
                          <td>{String(r.effective_from || '').slice(0, 10)}</td>
                          <td>{money(r.rate)} / hr</td>
                          <td>
                            <Badge>{r.status}</Badge>
                          </td>
                          <td>
                            {r.status === 'draft' && p.can('contract_approver') ? (
                              <button
                                disabled={p.busy}
                                onClick={() =>
                                  p.act(
                                    () =>
                                      api(
                                        `/contracts/${r.id}/approve?version_id=${encodeURIComponent(r.version_id)}`,
                                        p.token,
                                        {}
                                      ),
                                    'Contract approved.'
                                  )
                                }
                              >
                                Approve terms
                              </button>
                            ) : (
                              <span className="muted">
                                {r.status === 'approved'
                                  ? 'Immutable terms'
                                  : 'Distinct approver required'}
                              </span>
                            )}
                          </td>
                        </>
                      ) : p.page === 'Evidence' ? (
                        <>
                          <td>
                            {r.work_reference || r.id}
                            <small>{r.work_code}</small>
                            <button className="record-action" onClick={() => setRecord(r.id)}>
                              Details &amp; edit
                            </button>
                          </td>
                          <td>{String(r.service_date).slice(0, 10)}</td>
                          <td>{r.quantity}</td>
                          <td>
                            <Badge>{r.status}</Badge>
                          </td>
                          <td>
                            {r.status === 'imported' && p.can('operations_verifier') ? (
                              <button
                                disabled={p.busy}
                                onClick={() =>
                                  p.act(
                                    () => api(`/evidence/${r.id}/attest`, p.token, {}),
                                    'Work evidence attested.'
                                  )
                                }
                              >
                                Attest record
                              </button>
                            ) : (
                              <span className="muted">
                                {r.status === 'attested'
                                  ? 'Verified by operations'
                                  : 'Independent verifier required'}
                              </span>
                            )}
                          </td>
                        </>
                      ) : p.page === 'Exceptions' ? (
                        <>
                          <td>
                            <strong>{r.rule_code || 'Investigation'}</strong>
                            <small>{r.message || r.finding_id}</small>
                          </td>
                          <td>
                            <Badge>{r.status}</Badge>
                          </td>
                          <td>
                            <CommentForm {...p} id={r.id} />
                          </td>
                        </>
                      ) : p.page === 'Approvals' ? (
                        <>
                          <td className="mono">{r.invoice_line_id}</td>
                          <td>
                            <Badge>{r.decision}</Badge>
                            <small>{r.reason}</small>
                          </td>
                          <td>{money(r.amount)}</td>
                          <td>{r.approver_email || r.approver_id}</td>
                        </>
                      ) : (
                        <>
                          <td className="mono">
                            {r.id}
                            <small>SHA-256: {String(r.artifact_hash || '').slice(0, 18)}…</small>
                          </td>
                          <td>
                            <Badge>{r.status}</Badge>
                          </td>
                          <td>{money(Number(r.total_minor || 0) / 100)}</td>
                          <td>
                            <button
                              onClick={() =>
                                p.act(
                                  () =>
                                    download(
                                      `/exports/${r.id}/download`,
                                      p.token,
                                      `mineassure-${r.id}.csv`
                                    ),
                                  'Approved-cost snapshot downloaded.'
                                )
                              }
                            >
                              Download CSV ↗
                            </button>
                          </td>
                        </>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <div className="pagination">
            <span>
              {filtered.length ? `${offset + 1}–${Math.min(offset + 12, filtered.length)}` : '0'} of{' '}
              {filtered.length}
            </span>
            <div>
              <button disabled={!offset} onClick={() => setOffset(Math.max(0, offset - 12))}>
                Previous
              </button>
              <button
                disabled={offset + 12 >= filtered.length}
                onClick={() => setOffset(offset + 12)}
              >
                Next
              </button>
            </div>
          </div>
        </section>
      </Load>
    </>
  )
}
function CommentForm(p: Props & { id: string }) {
  return (
    <form
      className="inline-form"
      onSubmit={(e) => {
        e.preventDefault()
        const f = e.currentTarget
        const text = new FormData(f).get('body')
        p.act(
          () => api(`/cases/${p.id}/comments`, p.token, { body: text }),
          'Investigation comment saved.'
        ).then(() => f.reset())
      }}
    >
      <input
        aria-label="Investigation comment"
        name="body"
        required
        placeholder="Record investigation note…"
        maxLength={4000}
      />
      <button disabled={p.busy || !p.can('ap_analyst', 'finance_approver')}>Add note</button>
    </form>
  )
}

function CreateForm(p: Props & { page: string; close: () => void }) {
  const { data: contracts } = useData(`/contracts?${p.query}`, p.token, p.revision)
  const { data: contractors } = useData(`/contractors?${p.query}`, p.token, p.revision)
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const f = Object.fromEntries(new FormData(e.currentTarget))
    const path = p.page === 'Evidence' ? 'evidence' : p.page.toLowerCase()
    const body: Row = { ...p.scope, ...f }
    if (p.page === 'Invoices') {
      body.lines = [
        {
          work_code: f.work_code,
          service_date: f.service_date,
          quantity: f.quantity,
          unit_price: f.unit_price,
          work_reference: f.work_reference,
        },
      ]
      for (const k of ['work_code', 'service_date', 'quantity', 'unit_price', 'work_reference'])
        delete body[k]
    }
    await p.act(async () => {
      await api(`/${path}`, p.token, body)
      p.close()
    }, 'Record registered. Independent approval or attestation may be required.')
  }
  return (
    <section className="panel form-panel">
      <h2>
        {p.page === 'Evidence'
          ? 'Register independent work'
          : `New ${p.page.toLowerCase().replace(/s$/, '')}`}
      </h2>
      <form onSubmit={submit}>
        <div className="form-grid">
          {p.page === 'Contractors' ? (
            <Field label="Contractor name">
              <input name="name" required maxLength={150} />
            </Field>
          ) : (
            <>
              {p.page === 'Contracts' ? (
                <>
                  <Field label="Contract title">
                    <input name="title" required />
                  </Field>
                  <Field label="Contractor">
                    <select name="contractor_id" required>
                      {(contractors || []).map((c: Row) => (
                        <option key={c.id} value={c.id}>
                          {c.name}
                        </option>
                      ))}
                    </select>
                  </Field>
                  <Field label="Effective from">
                    <input name="effective_from" type="date" defaultValue="2026-10-01" required />
                  </Field>
                  <Field label="Hourly rate (USD)">
                    <input
                      name="rate"
                      type="number"
                      min="0.01"
                      step="0.01"
                      defaultValue="240"
                      required
                    />
                  </Field>
                </>
              ) : (
                <>
                  <Field label="Contract">
                    <select name="contract_id" required>
                      {(contracts || []).map((c: Row) => (
                        <option key={c.id} value={c.id}>
                          {c.title}
                        </option>
                      ))}
                    </select>
                  </Field>
                  {p.page === 'Invoices' && (
                    <Field label="Supplier invoice number">
                      <input name="supplier_invoice_no" required placeholder="INV-2026-004" />
                    </Field>
                  )}
                  <Field label="Service date">
                    <input name="service_date" type="date" defaultValue="2026-10-10" required />
                  </Field>
                  <Field label="Work reference">
                    <input name="work_reference" required placeholder="SHIFT-004" />
                  </Field>
                  <Field label="Hours">
                    <input name="quantity" type="number" min="0.01" step="0.01" required />
                  </Field>
                  {p.page === 'Invoices' && (
                    <Field label="Billed hourly rate (USD)">
                      <input
                        name="unit_price"
                        type="number"
                        min="0.01"
                        step="0.01"
                        defaultValue="240"
                        required
                      />
                    </Field>
                  )}
                </>
              )}
              <Field label="Work code">
                <input name="work_code" defaultValue="EQ-HIRE" required />
              </Field>
            </>
          )}
        </div>
        <div className="form-actions">
          <p className="muted small">
            {p.page === 'Evidence'
              ? 'A different operations verifier must attest this independent source before reconciliation.'
              : 'Records are scoped to the selected mine site.'}
          </p>
          <button type="submit" className="primary" disabled={p.busy}>
            Save record
          </button>
        </div>
      </form>
    </section>
  )
}
function InvoiceDetail(p: Props & { id: string; back: () => void }) {
  const { data, error } = useData(`/invoices/${p.id}`, p.token, p.revision)
  const run = data?.current_run
  const [manage, setManage] = useState(false)
  return (
    <>
      <button className="text-link back" onClick={p.back}>
        ← Back to workspace
      </button>
      <Load error={error} data={data}>
        <section className="panel">
          <div className="panel-heading">
            <div>
              <h2>{data?.supplier_invoice_no}</h2>
              <p>
                {data?.contractor_name || 'Equipment hire'} · {data?.currency || 'USD'}
              </p>
            </div>
            <div className="button-group">
              <Badge>{data?.status}</Badge>
              <button onClick={() => setManage(!manage)}>
                {manage ? 'Close record details' : 'Edit / associations'}
              </button>
              {p.can('ap_analyst') && (
                <ReconciliationButton
                  {...p}
                  disabledReason={
                    run?.results?.some((r: Row) => r.decision)
                      ? 'A finance decision is recorded; the assessed invoice is retained.'
                      : undefined
                  }
                />
              )}
            </div>
          </div>
          <div className="table-wrap" tabIndex={0} role="region" aria-label="Scrollable records">
            <table>
              <thead>
                <tr>
                  <th>Line / Work reference</th>
                  <th>Service date</th>
                  <th className="numeric">Hours</th>
                  <th className="numeric">Billed rate</th>
                  <th className="numeric">Invoiced</th>
                </tr>
              </thead>
              <tbody>
                {(data?.lines || []).map((l: Row) => (
                  <tr key={l.id}>
                    <td>
                      {l.work_code}
                      <small>{l.work_reference || 'No work reference'}</small>
                    </td>
                    <td>{String(l.service_date).slice(0, 10)}</td>
                    <td className="numeric">{l.quantity}</td>
                    <td className="numeric">{money(l.unit_price)}</td>
                    <td className="numeric">{money(l.amount)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
        {manage && <RecordPanel {...p} kind="invoices" id={p.id} close={() => setManage(false)} />}
        {!run ? (
          <Empty>
            This invoice has no current assessment. An AP analyst can reconcile it against approved
            terms and attested work.
          </Empty>
        ) : (
          <>
            <OutcomePanel {...p} invoiceId={p.id} run={run} />
            <div className="section-heading">
              <h2>Reconciliation evidence</h2>
              <span className="muted small">
                Rule set {run.rule_set_version || '1.0'} · Current run · Version {run.version || 1}
              </span>
            </div>
            {run.results.map((r: Row) => (
              <section className="panel result-panel" key={r.id + ':' + run.version}>
                <div className="comparison">
                  {[
                    ['Invoiced', 'invoiced_amount', 'Submitted invoice line'],
                    ['Provisionally supported', 'supported_amount', 'Terms × eligible work'],
                    ['Unverified', 'unverified_amount', 'Requires further evidence'],
                    ['Quantified variance', 'quantified_variance', 'Calculated once per line'],
                  ].map(([label, key, sub]) => (
                    <div key={key}>
                      <span>{label}</span>
                      <strong>{money(r[key])}</strong>
                      <small>{sub}</small>
                    </div>
                  ))}
                </div>
                <details>
                  <summary>View calculation and source references</summary>
                  <p className="calculation">{r.explanation}</p>
                  <p className="mono small">
                    Run: {run.id} · Invoice line: {r.invoice_line_id}
                  </p>
                </details>
                <div className="findings">
                  {r.findings.length ? (
                    r.findings.map((f: Row) => (
                      <div className="finding" key={f.id}>
                        <span className="rule">{f.rule_code}</span>
                        <div>
                          <strong>{f.message}</strong>
                          <small>{f.severity} priority · Human determination required</small>
                        </div>
                        {p.can('ap_analyst', 'finance_approver') && (
                          <button
                            disabled={p.busy}
                            onClick={() =>
                              p.act(
                                () => api('/cases', p.token, { ...p.scope, finding_id: f.id }),
                                'Investigation opened in Exceptions.'
                              )
                            }
                          >
                            Investigate
                          </button>
                        )}
                      </div>
                    ))
                  ) : (
                    <p className="muted">
                      No rule exceptions detected. Finance approval is still required.
                    </p>
                  )}
                </div>
                <div className="decision">
                  <div>
                    <span className="muted small">Approved amount</span>
                    <strong>{money(r.approved_amount)}</strong>
                  </div>
                  {p.can('finance_approver') ? (
                    <ApprovalForm {...p} run={run} result={r} />
                  ) : (
                    <p className="muted small">
                      A distinct finance approver authorizes eligible amounts.
                    </p>
                  )}
                </div>
              </section>
            ))}
            {p.can('finance_approver', 'auditor') && (
              <div className="export-callout">
                <div>
                  <h2>Approved costs, ready for finance.</h2>
                  <p>Only approved amounts enter the immutable CSV snapshot.</p>
                </div>
                <button
                  className="primary"
                  disabled={p.busy || !run.results.some((r: Row) => Number(r.approved_amount) > 0)}
                  onClick={() =>
                    p.act(async () => {
                      const batch = await api('/exports', p.token, {
                        ...p.scope,
                        run_id: run.id,
                        idempotency_key: `export-${run.id}`,
                      })
                      await download(
                        `/exports/${batch.id}/download`,
                        p.token,
                        `mineassure-${batch.id}.csv`
                      )
                    }, 'Approved-cost export created and downloaded.')
                  }
                >
                  Export approved costs ↗
                </button>
              </div>
            )}
          </>
        )}
      </Load>
    </>
  )
}
