import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { api, money } from './api'
import type { Row } from './api'

type Props = {
  contract: Row
  token: string
  revision: number
  busy: boolean
  can: (...roles: string[]) => boolean
  act: (fn: () => Promise<unknown>, message?: string) => Promise<void>
}

export function ContractVersions(p: Props) {
  const [versions, setVersions] = useState<Row[]>([])
  const [error, setError] = useState('')
  const [open, setOpen] = useState(false)
  useEffect(() => {
    if (!open) return
    let active = true
    api(`/contracts/${p.contract.id}/versions`, p.token)
      .then((data) => {
        if (active) {
          setVersions(data)
          setError('')
        }
      })
      .catch((e) => {
        if (active) setError(e.message)
      })
    return () => {
      active = false
    }
  }, [open, p.contract.id, p.token, p.revision])

  function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const form = e.currentTarget
    const values = Object.fromEntries(new FormData(form))
    p.act(async () => {
      await api(`/contracts/${p.contract.id}/versions`, p.token, values)
      form.reset()
    }, 'Contract revision drafted for independent approval.')
  }

  return (
    <details onToggle={(e) => setOpen(e.currentTarget.open)}>
      <summary>Versions &amp; revisions</summary>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {versions.map((v) => (
        <div key={v.id} className="version-record">
          <strong>
            Version {v.version_no} · {v.status}
          </strong>
          <p>
            {String(v.effective_from).slice(0, 10)} —{' '}
            {v.effective_to ? String(v.effective_to).slice(0, 10) : 'Open ended'}
          </p>
          {v.rates.map((r: Row) => (
            <p key={r.work_code}>
              {r.work_code} · {money(r.rate)} / {r.unit}
              {r.cap_hours ? ` · Cap ${r.cap_hours} hours per line` : ''}
            </p>
          ))}
          <small className="mono">
            {v.content_hash ? `SHA-256: ${v.content_hash}` : 'Draft terms'}
            {v.approved_by ? ` · Approver ${v.approved_by}` : ''}
          </small>
        </div>
      ))}
      {p.can('contract_preparer', 'tenant_admin') && p.contract.status !== 'draft' && (
        <form onSubmit={submit} className="revision-form">
          <label className="field">
            <span>Revision effective from</span>
            <input name="effective_from" type="date" required />
          </label>
          <label className="field">
            <span>Revised hourly rate (USD)</span>
            <input name="rate" type="number" min="0" step="0.01" required />
          </label>
          <label className="field">
            <span>Revision work code</span>
            <input name="work_code" defaultValue={p.contract.work_code || 'EQ-HIRE'} required />
          </label>
          <button disabled={p.busy}>Draft revision</button>
          <p className="muted small">
            Existing approved versions and historical assessments remain recorded. The latest
            approved effective date determines the applicable terms.
          </p>
        </form>
      )}
    </details>
  )
}
