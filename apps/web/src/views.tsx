import type { ReactNode } from 'react'
import { api } from './api'
import type { Row } from './api'
import type { Props } from './hooks'
import {
  canonicalMessage,
  generateSigningKey,
  getSigningKey,
  getStoredSpki,
  signPayload,
} from './crypto'

export function Badge({ children }: { children: ReactNode }) {
  return (
    <span className={`badge ${String(children)}`}>{String(children).replaceAll('_', ' ')}</span>
  )
}
export function Empty({
  children = 'No matching records in this site.',
}: {
  children?: ReactNode
}) {
  return (
    <div className="empty">
      <span>◇</span>
      <p>{children}</p>
    </div>
  )
}
export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
    </label>
  )
}
export function Load({
  error,
  data,
  children,
}: {
  error: string
  data: unknown
  children: ReactNode
}) {
  return error ? (
    <div role="alert" className="error">
      {error}
    </div>
  ) : data === null ? (
    <div className="loading" role="status">
      Loading workspace records…
    </div>
  ) : (
    children
  )
}

export function ApprovalForm(p: Props & { run: Row; result: Row }) {
  return (
    <form
      className="approval-form"
      onSubmit={async (e) => {
        e.preventDefault()
        const f = new FormData(e.currentTarget)
        const fields = {
          run_id: p.run.id,
          invoice_line_id: p.result.invoice_line_id,
          decision: 'approved',
          amount: String(f.get('amount')),
          reason: String(f.get('reason')),
          run_version: p.run.version || 1,
        }
        await p.act(async () => {
          let signature: string | undefined
          let spki: string | undefined
          try {
            if (p.userId && typeof crypto !== 'undefined' && crypto.subtle) {
              let key = await getSigningKey(p.userId)
              if (!key) {
                const kp = await generateSigningKey(p.userId)
                key = kp.privateKey
                spki = kp.spkiB64
              } else {
                spki = getStoredSpki(p.userId) || undefined
              }
              if (key && spki)
                signature = await signPayload(
                  key,
                  canonicalMessage(fields as Record<string, string | number>)
                )
            }
          } catch {
            signature = undefined
            spki = undefined
          }
          await api('/approvals', p.token, {
            ...fields,
            client_signature: signature,
            client_public_key_spki: spki,
          })
        }, 'Finance approval recorded with an immutable decision snapshot.')
      }}
    >
      <Field label="Approve amount (USD)">
        <input
          name="amount"
          type="number"
          min="0.01"
          step="0.01"
          max={p.result.supported_amount}
          defaultValue={Number(p.result.supported_amount).toFixed(2)}
          required
        />
      </Field>
      <Field label="Decision reason">
        <input name="reason" required placeholder="Record your review rationale" maxLength={2000} />
      </Field>
      <button
        className="primary"
        disabled={p.busy || Number(p.result.supported_amount) <= 0 || Boolean(p.result.decision)}
      >
        Approve eligible costs
      </button>
    </form>
  )
}
export function Settings({ user, sites }: { user: Row | null; sites: Row[] }) {
  return (
    <section className="panel settings">
      <h2>Identity & access</h2>
      <dl>
        <dt>Signed-in account</dt>
        <dd>{user?.email}</dd>
        <dt>Accessible sites</dt>
        <dd>{sites.map((s) => s.name).join(', ')}</dd>
        <dt>Session</dt>
        <dd>Token held in memory; sign-in required after refresh.</dd>
        <dt>Pilot scope</dt>
        <dd>Hourly equipment hire · USD · Synthetic data</dd>
        <dt>Administration</dt>
        <dd>Tenant administrators manage local users, site grants and new sites below.</dd>
      </dl>
      <p className="muted">
        Production identity, retention, approval thresholds, and deployment jurisdiction require
        customer-specific configuration and review.
      </p>
    </section>
  )
}
