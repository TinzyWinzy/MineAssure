import { useRemote } from './useRemote'
import { useState } from 'react'
import type { FormEvent } from 'react'
import { api, download, money } from './api'
import type { Row } from './api'
import { FormField, RecordsTable } from './workflow'
import type { WorkflowProps } from './workflow'

type Props = WorkflowProps & {
  kind: string
  id: string
  close: () => void
  openInvoice?: (id: string) => void
}

export function RecordPanel(p: Props) {
  const [selected, setSelected] = useState({ kind: p.kind, id: p.id })
  const [editing, setEditing] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const { data, error } = useRemote(
    `/records/${selected.kind}/${selected.id}?${p.query}`,
    p.token,
    p.revision
  )
  const { data: contracts } = useRemote(`/contracts?${p.query}&limit=200`, p.token, p.revision)
  const { data: contractors } = useRemote(`/contractors?${p.query}`, p.token, p.revision)
  const [lines, setLines] = useState<Row[] | null>(null)
  const item = data?.item
  const associations = data?.associations || {}
  function navigate(kind: string, id: string) {
    setSelected({ kind, id })
    setEditing(false)
    setDeleting(false)
    setLines(null)
  }
  function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const values: Row = Object.fromEntries(new FormData(e.currentTarget))
    if (selected.kind === 'contracts') {
      if (!values.effective_to) values.effective_to = null
      if (!values.cap_hours) values.cap_hours = null
    }
    if (selected.kind === 'invoices')
      values.lines = (lines || item.lines).map(({ id: _id, amount: _amount, ...line }: Row) => ({
        ...line,
        work_reference: line.work_reference || null,
        description: line.description || 'Equipment hire',
      }))
    p.act(async () => {
      await api(
        `/${selected.kind}/${selected.id}?expected_revision=${item.revision}`,
        p.token,
        { ...p.scope, ...values },
        'PUT'
      )
      setEditing(false)
      setLines(null)
    }, 'Record updated. Its associations and totals have been refreshed.')
  }
  const liveLines = lines || item?.lines || []
  const changeLine = (index: number, name: string, value: string) =>
    setLines(
      liveLines.map((line: Row, i: number) => (i === index ? { ...line, [name]: value } : line))
    )
  return (
    <section className="panel record-panel" aria-label="Record details">
      <div className="panel-heading">
        <div>
          <span className="eyebrow">{selected.kind} / Associations</span>
          <h2>
            {item?.name ||
              item?.title ||
              item?.supplier_invoice_no ||
              item?.work_reference ||
              'Record details'}
          </h2>
        </div>
        <button onClick={p.close}>Close details</button>
      </div>
      {error ? (
        <p className="error" role="alert">
          {error}
        </p>
      ) : !data ? (
        <p role="status">Loading linked records…</p>
      ) : (
        <div className="record-body">
          <div className="button-group">
            <span className="badge">
              {item.status || 'Registered'} · Revision {item.revision}
            </span>
            {data.can_edit && (
              <button
                onClick={() => {
                  setEditing(!editing)
                  setDeleting(false)
                }}
              >
                {editing ? 'Cancel editing' : 'Edit record'}
              </button>
            )}
            {data.can_delete && (
              <button
                className="danger-text"
                onClick={() => {
                  setDeleting(true)
                  setEditing(false)
                }}
              >
                Delete record
              </button>
            )}
            {selected.kind === 'invoices' && p.openInvoice && (
              <button onClick={() => p.openInvoice?.(item.id)}>Open invoice review</button>
            )}
          </div>
          {data.locked_reason && <p className="muted policy-note">{data.locked_reason}</p>}
          {deleting && (
            <div className="delete-confirm" role="alert">
              <p>Delete this unused record? Associated financial history cannot be deleted.</p>
              <button
                className="danger"
                disabled={p.busy}
                onClick={() =>
                  p.act(async () => {
                    await api(
                      `/records/${selected.kind}/${selected.id}?${p.query}&expected_revision=${item.revision}`,
                      p.token,
                      undefined,
                      'DELETE'
                    )
                    p.close()
                  }, 'Unused record deleted; an audit event is retained.')
                }
              >
                Confirm deletion
              </button>
              <button onClick={() => setDeleting(false)}>Keep record</button>
            </div>
          )}
          {editing && (
            <form onSubmit={submit} className="record-edit">
              <div className="form-grid">
                {selected.kind === 'contractors' ? (
                  <FormField label="Contractor name">
                    <input name="name" required defaultValue={item.name} />
                  </FormField>
                ) : selected.kind === 'contracts' ? (
                  <>
                    <FormField label="Contract title">
                      <input name="title" required defaultValue={item.title} />
                    </FormField>
                    <FormField label="Contractor association">
                      <select name="contractor_id" defaultValue={item.contractor_id} required>
                        {(contractors || []).map((c: Row) => (
                          <option key={c.id} value={c.id}>
                            {c.name}
                          </option>
                        ))}
                      </select>
                    </FormField>
                    <FormField label="Effective from">
                      <input
                        type="date"
                        name="effective_from"
                        defaultValue={item.effective_from?.slice(0, 10)}
                        required
                      />
                    </FormField>
                    <FormField label="Effective to">
                      <input
                        type="date"
                        name="effective_to"
                        defaultValue={item.effective_to?.slice(0, 10)}
                      />
                    </FormField>
                    <FormField label="Hourly rate (USD)">
                      <input
                        type="number"
                        step="0.01"
                        min="0"
                        name="rate"
                        defaultValue={item.rate}
                        required
                      />
                    </FormField>
                    <FormField label="Work code">
                      <input name="work_code" defaultValue={item.work_code} required />
                    </FormField>
                    <FormField label="Cap hours per line">
                      <input
                        type="number"
                        step="0.01"
                        min="0.01"
                        name="cap_hours"
                        defaultValue={item.cap_hours || ''}
                      />
                    </FormField>
                  </>
                ) : (
                  <>
                    <FormField label="Contract association">
                      <select name="contract_id" defaultValue={item.contract_id} required>
                        {(contracts || []).map((c: Row) => (
                          <option key={c.id} value={c.id}>
                            {c.title} · {c.status}
                          </option>
                        ))}
                      </select>
                    </FormField>
                    {selected.kind === 'invoices' ? (
                      <FormField label="Supplier invoice number">
                        <input
                          name="supplier_invoice_no"
                          defaultValue={item.supplier_invoice_no}
                          required
                        />
                      </FormField>
                    ) : (
                      <>
                        <FormField label="Work reference">
                          <input
                            name="work_reference"
                            defaultValue={item.work_reference}
                            required
                          />
                        </FormField>
                        <FormField label="Work code">
                          <input name="work_code" defaultValue={item.work_code} required />
                        </FormField>
                        <FormField label="Service date">
                          <input
                            type="date"
                            name="service_date"
                            defaultValue={item.service_date.slice(0, 10)}
                            required
                          />
                        </FormField>
                        <FormField label="Hours">
                          <input
                            type="number"
                            step="0.01"
                            min="0.01"
                            name="quantity"
                            defaultValue={item.quantity}
                            required
                          />
                        </FormField>
                      </>
                    )}
                  </>
                )}
              </div>
              {selected.kind === 'invoices' && (
                <fieldset className="line-editor">
                  <legend>Invoice lines</legend>
                  {liveLines.map((line: Row, index: number) => (
                    <div className="line-edit-row" key={index}>
                      {(
                        [
                          ['work_reference', 'Work reference', 'text'],
                          ['work_code', 'Work code', 'text'],
                          ['service_date', 'Service date', 'date'],
                          ['quantity', 'Hours', 'number'],
                          ['unit_price', 'Hourly price', 'number'],
                        ] as const
                      ).map(([name, label, type]) => (
                        <FormField key={name} label={`${label} · line ${index + 1}`}>
                          <input
                            type={type}
                            step={type === 'number' ? '0.01' : undefined}
                            min={
                              type === 'number' ? (name === 'quantity' ? '0.01' : '0') : undefined
                            }
                            value={
                              type === 'date' ? line[name]?.slice(0, 10) || '' : line[name] || ''
                            }
                            onChange={(e) => changeLine(index, name, e.target.value)}
                            required={name !== 'work_reference'}
                          />
                        </FormField>
                      ))}
                      <button
                        type="button"
                        disabled={liveLines.length === 1}
                        onClick={() =>
                          setLines(liveLines.filter((_: Row, i: number) => i !== index))
                        }
                      >
                        Remove line {index + 1}
                      </button>
                    </div>
                  ))}
                  <button
                    type="button"
                    disabled={liveLines.length >= 500}
                    onClick={() =>
                      setLines([
                        ...liveLines,
                        {
                          work_code: 'EQ-HIRE',
                          work_reference: '',
                          service_date: '',
                          quantity: '1',
                          unit_price: '240',
                          unit: 'hour',
                          description: 'Equipment hire',
                        },
                      ])
                    }
                  >
                    Add invoice line
                  </button>
                </fieldset>
              )}
              <button className="primary" disabled={p.busy}>
                Save changes
              </button>
            </form>
          )}
          <div className="association-grid">
            {associations.contractor && (
              <article>
                <small>Contractor</small>
                <button
                  className="link-button"
                  onClick={() => navigate('contractors', associations.contractor.id)}
                >
                  {associations.contractor.name}
                </button>
              </article>
            )}
            {associations.contract && (
              <article>
                <small>Contract</small>
                <button
                  className="link-button"
                  onClick={() => navigate('contracts', associations.contract.id)}
                >
                  {associations.contract.title}
                </button>
              </article>
            )}
            {associations.import && (
              <article>
                <small>Original input file</small>
                <strong>{associations.import.filename}</strong>
                <button
                  onClick={() =>
                    p.act(
                      () =>
                        download(
                          `/ingestion/${associations.import.id}/download/source`,
                          p.token,
                          associations.import.filename
                        ),
                      'Original source downloaded.'
                    )
                  }
                >
                  Download source file
                </button>
                <small className="mono">SHA-256 {associations.import.sha256}</small>
              </article>
            )}
          </div>
          {selected.kind === 'invoices' && !editing && (
            <RecordsTable>
              <table>
                <thead>
                  <tr>
                    <th>Line reference</th>
                    <th>Contract work code</th>
                    <th>Hours</th>
                    <th>Hourly price</th>
                    <th>Invoiced</th>
                  </tr>
                </thead>
                <tbody>
                  {item.lines.map((line: Row) => (
                    <tr key={line.id}>
                      <td>{line.work_reference || 'Unlinked'}</td>
                      <td>{line.work_code}</td>
                      <td>{line.quantity}</td>
                      <td>{money(line.unit_price)}</td>
                      <td>{money(line.amount)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </RecordsTable>
          )}
          {associations.contracts?.length > 0 && (
            <div className="association-list">
              <h3>Associated contracts</h3>
              {associations.contracts.map((c: Row) => (
                <button key={c.id} onClick={() => navigate('contracts', c.id)}>
                  {c.title} ↗
                </button>
              ))}
            </div>
          )}
          {associations.invoices?.length > 0 && (
            <div className="association-list">
              <h3>Associated invoices</h3>
              {associations.invoices.map((i: Row) => (
                <button key={i.id} onClick={() => navigate('invoices', i.id)}>
                  {i.supplier_invoice_no} · {money(i.total)} ↗
                </button>
              ))}
            </div>
          )}
          {associations.evidence?.length > 0 && (
            <div className="association-list">
              <h3>Associated evidence</h3>
              {associations.evidence.map((w: Row) => (
                <button key={w.id} onClick={() => navigate('evidence', w.id)}>
                  {w.work_reference} · {w.quantity} hours · {w.status} ↗
                </button>
              ))}
            </div>
          )}
          {associations.runs?.length > 0 && (
            <div className="association-list">
              <h3>Assessment history &amp; outputs</h3>
              {associations.runs.map((r: Row) => (
                <article key={r.id}>
                  <span>
                    {r.is_current ? 'Current assessment' : 'Historical assessment'} · {r.status}
                  </span>
                  <button
                    onClick={() =>
                      p.act(
                        () =>
                          download(
                            `/reconciliation/runs/${r.id}/report?format=json`,
                            p.token,
                            `assessment-${r.id}.json`
                          ),
                        'Calculation report downloaded.'
                      )
                    }
                  >
                    Download report JSON
                  </button>
                  <small className="mono">{r.input_hash}</small>
                </article>
              ))}
            </div>
          )}
          {associations.allocations?.length > 0 && (
            <RecordsTable>
              <table>
                <thead>
                  <tr>
                    <th>Invoice line</th>
                    <th>Allocated hours</th>
                    <th>Ledger state</th>
                    <th>Assessment</th>
                  </tr>
                </thead>
                <tbody>
                  {associations.allocations.map((a: Row) => (
                    <tr key={a.id}>
                      <td className="mono">{a.invoice_line_id}</td>
                      <td>{a.quantity}</td>
                      <td>{a.status}</td>
                      <td className="mono">{a.reconciliation_run_id}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </RecordsTable>
          )}
          {!editing && selected.kind === 'evidence' && (
            <p>
              {item.quantity} {item.unit} · {item.service_date.slice(0, 10)} · {item.work_code} ·{' '}
              {item.status}
              {item.attested_by ? ` · Verifier ${item.attested_by}` : ''}
            </p>
          )}
        </div>
      )}
    </section>
  )
}
