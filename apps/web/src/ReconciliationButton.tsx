import { useEffect, useState } from 'react'
import { api } from './api'
import type { Row } from './api'

type Props = {
  id: string
  token: string
  scope: { org_id: string; site_id: string }
  busy: boolean
  disabledReason?: string
  act: (fn: () => Promise<unknown>, message?: string) => Promise<void>
}

export function ReconciliationButton(p: Props) {
  const { token, act } = p
  const [job, setJob] = useState<Row | null>(null)
  const [message, setMessage] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const jobId = job?.id
  const pending = job?.status === 'queued' || job?.status === 'running'
  useEffect(() => {
    if (!jobId || !pending) return
    let active = true
    let polling = false
    const timer = setInterval(async () => {
      if (polling) return
      polling = true
      try {
        const current = await api(`/jobs/${jobId}`, token)
        if (!active) return
        setJob(current)
        if (current.status === 'completed') {
          setMessage('Assessment completed.')
          await act(
            () => Promise.resolve(),
            'Assessment completed using approved terms and attested evidence.'
          )
        } else if (current.status === 'failed') {
          setMessage(current.result?.message || 'Assessment failed. Submit a new request to retry.')
        }
      } catch (e) {
        if (active) {
          setMessage((e as Error).message)
          setJob(null)
        }
      } finally {
        polling = false
      }
    }, 1000)
    return () => {
      active = false
      clearInterval(timer)
    }
  }, [jobId, pending, token, act])

  return (
    <div>
      <button
        className="primary"
        title={p.disabledReason}
        disabled={p.busy || submitting || pending || Boolean(p.disabledReason)}
        onClick={async () => {
          setSubmitting(true)
          setMessage('')
          try {
            setJob(
              await api('/jobs/reconciliation', p.token, {
                ...p.scope,
                invoice_id: p.id,
                idempotency_key: crypto.randomUUID(),
              })
            )
          } catch (e) {
            setMessage((e as Error).message)
          } finally {
            setSubmitting(false)
          }
        }}
      >
        {submitting
          ? 'Submitting assessment…'
          : pending
            ? job?.status === 'queued'
              ? 'Queued for assessment…'
              : 'Assessing invoice…'
            : 'Run reconciliation'}
      </button>
      {pending && (
        <small role="status">Job {String(job?.id).slice(0, 8)} · A worker must be running.</small>
      )}
      {message && <small role="status">{message}</small>}
      {p.disabledReason && <small>{p.disabledReason}</small>}
    </div>
  )
}
