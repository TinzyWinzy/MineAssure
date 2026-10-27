import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { api } from './api'
import type { Row } from './api'

const roles = [
  'contract_preparer',
  'contract_approver',
  'operations_verifier',
  'ap_analyst',
  'finance_approver',
  'auditor',
  'partner_readonly',
  'tenant_admin',
]
type Props = {
  token: string
  query: string
  scope: { org_id: string; site_id: string }
  revision: number
  busy: boolean
  act: (fn: () => Promise<unknown>, message?: string) => Promise<void>
  userId: string
}

export function Administration(p: Props) {
  const [users, setUsers] = useState<Row[] | null>(null)
  const [error, setError] = useState('')
  useEffect(() => {
    let active = true
    api(`/admin/users?${p.query}`, p.token)
      .then((data) => {
        if (active) {
          setUsers(data)
          setError('')
        }
      })
      .catch((e) => {
        if (active) setError(e.message)
      })
    return () => {
      active = false
    }
  }, [p.query, p.token, p.revision])

  function submit(e: FormEvent<HTMLFormElement>, path: string) {
    e.preventDefault()
    const form = e.currentTarget
    const values = Object.fromEntries(new FormData(form))
    const scope = path === 'sites' ? { org_id: p.scope.org_id } : p.scope
    p.act(async () => {
      await api(`/admin/${path}`, p.token, { ...scope, ...values })
      form.reset()
    }, 'Administration change saved with an audit record.')
  }

  return (
    <section className="panel form-panel">
      <h2>Site &amp; user administration</h2>
      <p className="muted">
        Tenant administrators can provision sites and scoped users. New local accounts need a
        password of at least 12 characters. Privileged roles remain subject to independent approval
        checks.
      </p>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      <details>
        <summary>Create mine site</summary>
        <form className="inline-form" onSubmit={(e) => submit(e, 'sites')}>
          <input
            name="name"
            aria-label="New site name"
            required
            maxLength={200}
            placeholder="Site name"
          />
          <button disabled={p.busy}>Create site</button>
        </form>
      </details>
      <details>
        <summary>Create local user</summary>
        <form className="form-grid" onSubmit={(e) => submit(e, 'users')}>
          <label className="field">
            <span>New user email</span>
            <input type="email" name="email" autoComplete="off" required />
          </label>
          <label className="field">
            <span>Initial password</span>
            <input
              type="password"
              name="password"
              minLength={12}
              maxLength={72}
              autoComplete="new-password"
              required
            />
          </label>
          <label className="field">
            <span>Initial site role</span>
            <select name="role">
              {roles.map((r) => (
                <option key={r} value={r}>
                  {r.replaceAll('_', ' ')}
                </option>
              ))}
            </select>
          </label>
          <button disabled={p.busy}>Create user in selected site</button>
        </form>
      </details>
      {users && (
        <>
          <div className="table-wrap" tabIndex={0} role="region" aria-label="Scrollable records">
            <table>
              <thead>
                <tr>
                  <th>Account</th>
                  <th>Role</th>
                  <th>Scope</th>
                  <th>Access</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.membership_id}>
                    <td>{u.email}</td>
                    <td>{u.role.replaceAll('_', ' ')}</td>
                    <td>
                      {u.site_id === p.scope.site_id
                        ? 'Selected site'
                        : u.site_id || 'Organisation'}
                    </td>
                    <td>
                      <button
                        disabled={p.busy || u.id === p.userId}
                        title={
                          u.id === p.userId
                            ? 'Administrators cannot revoke their own access'
                            : 'Revoke this grant immediately'
                        }
                        onClick={() =>
                          p.act(
                            () => api(`/admin/memberships/${u.membership_id}/revoke`, p.token, {}),
                            'Membership revoked; future requests use the updated grants.'
                          )
                        }
                      >
                        Revoke grant
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <details>
            <summary>Grant another site role</summary>
            <form className="form-grid" onSubmit={(e) => submit(e, 'memberships')}>
              <label className="field">
                <span>Existing tenant user</span>
                <select name="user_id" required>
                  {Array.from(new Map(users.map((u) => [u.id, u])).values()).map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.email}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span>Additional role</span>
                <select name="role">
                  {roles.map((r) => (
                    <option key={r} value={r}>
                      {r.replaceAll('_', ' ')}
                    </option>
                  ))}
                </select>
              </label>
              <button disabled={p.busy}>Grant role in selected site</button>
            </form>
          </details>
        </>
      )}
    </section>
  )
}
