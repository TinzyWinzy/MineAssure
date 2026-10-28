import { useRemote } from './useRemote'
import { useState } from 'react'
import type { FormEvent } from 'react'
import { api, base, download } from './api'
import type { Row } from './api'
import { FormField, RecordsTable } from './workflow'
import type { WorkflowProps } from './workflow'
import { RecordPanel } from './RecordPanel'

export function FileCenter(
  p: WorkflowProps & { kind?: string; openInvoice?: (id: string) => void }
) {
  const [kind, setKind] = useState(
    p.kind || (p.can('ap_analyst', 'tenant_admin') ? 'invoice' : 'evidence')
  )
  const [batch, setBatch] = useState<Row | null>(null)
  const [mapping, setMapping] = useState<Record<string, string>>({})
  const [processing, setProcessing] = useState(false)
  const [contractId, setContractId] = useState('')
  const [error, setError] = useState('')
  const [source, setSource] = useState<{ kind: string; id: string } | null>(null)
  const [confirmPurge, setConfirmPurge] = useState(false)
  const [version, setVersion] = useState(0)
  const { data: contracts, error: contractError } = useRemote(
    `/contracts?${p.query}&limit=200`,
    p.token,
    p.revision
  )
  const { data: files, error: filesError } = useRemote(
    `/ingestion?${p.query}`,
    p.token,
    p.revision + version
  )
  const canUpload = p.can(kind === 'invoice' ? 'ap_analyst' : 'operations_verifier', 'tenant_admin')
  function show(data: Row) {
    setBatch(data)
    setConfirmPurge(false)
    setMapping(
      Object.fromEntries(
        data.required_columns.map((column: string) => [
          column,
          data.mapping[column] || (data.headers.includes(column) ? column : ''),
        ])
      )
    )
  }
  async function perform(fn: () => Promise<Row>) {
    setError('')
    setProcessing(true)
    try {
      show(await fn())
      setVersion((v) => v + 1)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setProcessing(false)
    }
  }
  function upload(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const form = new FormData(e.currentTarget)
    const contractId = String(form.get('contract_id'))
    form.delete('contract_id')
    perform(async () => {
      const response = await fetch(
        `${base}/ingestion/${kind}/stage?${p.query}&contract_id=${encodeURIComponent(contractId)}`,
        { method: 'POST', headers: { Authorization: `Bearer ${p.token}` }, body: form }
      )
      const data = await response.json()
      if (!response.ok)
        throw new Error(typeof data.detail === 'string' ? data.detail : 'File processing failed')
      return data
    })
  }
  const shownFiles = (files || []).filter((f: Row) => !p.kind || f.kind === p.kind)
  return (
    <section className="file-center" aria-label="File processing and ingestion">
      <section className="panel form-panel">
        <div className="section-heading">
          <div>
            <h2>File processing &amp; ingestion</h2>
            <p>Upload → map columns → validate → import linked records → download results.</p>
          </div>
        </div>
        {!p.kind && (
          <FormField label="File contains">
            <select
              value={kind}
              onChange={(e) => {
                setKind(e.target.value)
                setBatch(null)
              }}
            >
              <option value="invoice">Invoices</option>
              <option value="evidence">Operational evidence</option>
            </select>
          </FormField>
        )}
        {canUpload ? (
          <form className="import-form" onSubmit={upload}>
            <FormField label="Associate file with contract">
              <select
                name="contract_id"
                value={contractId || contracts?.[0]?.id || ''}
                onChange={(e) => setContractId(e.target.value)}
                required
              >
                {(contracts || []).map((c: Row) => (
                  <option key={c.id} value={c.id}>
                    {c.title} · {c.status}
                  </option>
                ))}
              </select>
            </FormField>
            <FormField label="CSV or XLSX file">
              <input name="file" type="file" accept=".csv,.xlsx" required />
            </FormField>
            <button className="primary" disabled={processing || !contracts?.length}>
              {processing ? 'Processing…' : 'Upload & preview'}
            </button>
          </form>
        ) : (
          <p className="policy-note">
            Your role can inspect files and outputs. An AP analyst uploads invoices; an operations
            verifier uploads evidence.
          </p>
        )}
        <p className="muted small">
          CSV: UTF-8. XLSX: first worksheet, reviewed values without formulas. Limit: 2 MiB, 500
          rows. Original files and checksums are retained. Evidence requires independent attestation
          after import.
        </p>
        <button
          onClick={() =>
            p.act(
              () => download(`/ingestion/templates/${kind}`, p.token, `${kind}-template.csv`),
              'Synthetic input template downloaded.'
            )
          }
        >
          Download {kind} CSV template
        </button>
        <details>
          <summary>How records, source files and calculations are associated</summary>
          <ol className="workflow-help">
            <li>Select the same contract for the operational evidence and its invoice.</li>
            <li>
              Match each line's work reference, work code, service date and unit to its evidence
              record.
            </li>
            <li>
              Import work as one operations verifier; a different verifier attests it under
              Evidence.
            </li>
            <li>
              Import the invoice, open its created record and run reconciliation. The report
              compares the invoice, approved rate and attested hours.
            </li>
            <li>
              Finance approves determined amounts. Download the calculation report or export
              approved costs.
            </li>
          </ol>
          <p className="muted small">
            The paired example templates use 160 hours at USD 250 versus 145 verified hours at USD
            240: USD 40,000 invoiced, USD 34,800 supported, USD 5,200 variance. Change example
            references before creating a different invoice.
          </p>
        </details>
        {(error || contractError || filesError) && (
          <p className="error" role="alert">
            {error || contractError || filesError}
          </p>
        )}
      </section>
      {batch && (
        <section className="panel" aria-label="File processing results">
          <div className="panel-heading">
            <div>
              <h2>{batch.filename}</h2>
              <small>
                {batch.row_count} source rows{batch.sheet ? ` · Worksheet ${batch.sheet}` : ''} ·
                Associated contract {batch.contract?.title}
              </small>
            </div>
            <span className={`badge ${batch.status}`}>{batch.status}</span>
          </div>
          <div className="record-body">
            <div className="workflow-steps">
              <span>1. Uploaded</span>
              <span>2. Map &amp; validate</span>
              <span>3. Import</span>
              <span>4. Outputs</span>
            </div>
            {batch.status !== 'imported' && batch.headers.length > 0 && canUpload && (
              <form
                onSubmit={(e) => {
                  e.preventDefault()
                  perform(() => api(`/ingestion/${batch.id}/validate`, p.token, { mapping }))
                }}
              >
                <h3>Column mapping</h3>
                <div className="mapping-grid">
                  {batch.required_columns.map((column: string) => (
                    <FormField key={column} label={`Map ${column}`}>
                      <select
                        value={mapping[column] || ''}
                        onChange={(e) => setMapping({ ...mapping, [column]: e.target.value })}
                        required
                      >
                        <option value="">Choose source column</option>
                        {batch.headers.map((header: string) => (
                          <option key={header} value={header}>
                            {header}
                          </option>
                        ))}
                      </select>
                    </FormField>
                  ))}
                </div>
                <button disabled={processing}>Validate mapped rows</button>
              </form>
            )}
            {batch.preview.length > 0 && (
              <details open>
                <summary>Source preview · first {batch.preview.length} rows</summary>
                <RecordsTable label="Source file preview">
                  <table>
                    <thead>
                      <tr>
                        {batch.headers.map((h: string) => (
                          <th key={h}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {batch.preview.map((row: string[], i: number) => (
                        <tr key={i}>
                          {row.map((v, j) => (
                            <td key={j}>{v}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </RecordsTable>
              </details>
            )}
            {batch.errors.length > 0 && (
              <div role="alert" className="validation-errors">
                <h3>{batch.errors.length} validation issues — no rows imported</h3>
                <RecordsTable label="Row validation errors">
                  <table>
                    <thead>
                      <tr>
                        <th>Source row</th>
                        <th>Field</th>
                        <th>Reason</th>
                      </tr>
                    </thead>
                    <tbody>
                      {batch.errors.map((e: Row, i: number) => (
                        <tr key={i}>
                          <td>{e.row || 'Whole file'}</td>
                          <td>{e.field || 'row'}</td>
                          <td>{e.message}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </RecordsTable>
              </div>
            )}
            {batch.status === 'ready' && canUpload && (
              <div className="import-ready">
                <p>
                  All {batch.row_count} rows validated. Import will create records under{' '}
                  {batch.contract?.title}; no financial approval is implied.
                </p>
                <button
                  className="primary"
                  disabled={processing}
                  onClick={() => perform(() => api(`/ingestion/${batch.id}/commit`, p.token, {}))}
                >
                  Import {batch.row_count} validated rows
                </button>
              </div>
            )}
            {batch.status === 'imported' && (
              <div className="notice" role="status">
                Imported {batch.accepted} rows. Linked records are available below.
              </div>
            )}
            <div className="button-group file-outputs">
              {batch.source_retained ? (
                <button
                  onClick={() =>
                    p.act(
                      () =>
                        download(`/ingestion/${batch.id}/download/source`, p.token, batch.filename),
                      'Original file downloaded.'
                    )
                  }
                >
                  Download original file
                </button>
              ) : (
                <span className="muted policy-note">Original file purged; checksum retained.</span>
              )}
              <button
                onClick={() =>
                  p.act(
                    () =>
                      download(
                        `/ingestion/${batch.id}/download/normalized`,
                        p.token,
                        'processed-rows.csv'
                      ),
                    'Processed rows downloaded.'
                  )
                }
              >
                Download processed rows
              </button>
              <button
                onClick={() =>
                  p.act(
                    () =>
                      download(
                        `/ingestion/${batch.id}/download/errors`,
                        p.token,
                        'validation-errors.csv'
                      ),
                    'Validation output downloaded.'
                  )
                }
              >
                Download validation output
              </button>
            </div>
            {batch.created_records?.length > 0 && (
              <div className="association-list">
                <h3>Created records &amp; associations</h3>
                {batch.created_records.map((r: Row) => (
                  <button
                    key={r.id}
                    onClick={() =>
                      r.kind === 'invoices' && p.openInvoice
                        ? p.openInvoice(r.id)
                        : setSource({ kind: r.kind, id: r.id })
                    }
                  >
                    {r.label} · {r.kind} ↗
                  </button>
                ))}
              </div>
            )}
            <small className="mono">Original SHA-256: {batch.sha256}</small>
            {batch.source_retained && batch.status === 'imported' && p.can('tenant_admin') && (
              <button className="danger-text" onClick={() => setConfirmPurge(true)}>
                Purge original file
              </button>
            )}
            {confirmPurge && (
              <div className="delete-confirm" role="alert">
                <p>
                  Purge the original file content? Checksum, processed rows, created records and the
                  audit event remain; the original cannot be downloaded again.
                </p>
                <button
                  className="danger"
                  disabled={processing}
                  onClick={() => perform(() => api(`/ingestion/${batch.id}/purge`, p.token, {}))}
                >
                  Purge original file
                </button>
                <button onClick={() => setConfirmPurge(false)}>Cancel</button>
              </div>
            )}
          </div>
        </section>
      )}
      <section className="panel">
        <div className="panel-heading">
          <h2>File history &amp; processing outputs</h2>
          <span>{shownFiles.length} files</span>
        </div>
        {!shownFiles.length ? (
          <p className="empty">No files have been ingested in this site.</p>
        ) : (
          <RecordsTable>
            <table>
              <thead>
                <tr>
                  <th>File / contract</th>
                  <th>Kind</th>
                  <th>State</th>
                  <th>Rows</th>
                  <th>Outputs</th>
                </tr>
              </thead>
              <tbody>
                {shownFiles.map((f: Row) => (
                  <tr key={f.id}>
                    <td>
                      <button
                        className="link-button"
                        onClick={() => {
                          setKind(f.kind)
                          show(f)
                        }}
                      >
                        {f.filename}
                      </button>
                      <small>{f.contract?.title}</small>
                    </td>
                    <td>{f.kind}</td>
                    <td>
                      <span className={`badge ${f.status}`}>{f.status}</span>
                    </td>
                    <td>
                      {f.accepted} / {f.row_count}
                    </td>
                    <td>
                      <button
                        onClick={() => {
                          setKind(f.kind)
                          show(f)
                        }}
                      >
                        View processing results
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </RecordsTable>
        )}
      </section>
      {source && (
        <RecordPanel
          key={source.kind + source.id}
          {...p}
          {...source}
          close={() => setSource(null)}
          openInvoice={p.openInvoice}
        />
      )}
    </section>
  )
}
