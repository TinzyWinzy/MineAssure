import { useRemote } from './useRemote'
import { useState } from 'react'
import { download } from './api'
import type { Row } from './api'
import { RecordsTable } from './workflow'
import type { WorkflowProps } from './workflow'
import { RecordPanel } from './RecordPanel'

export function OutcomePanel(p: WorkflowProps & { run: Row; invoiceId: string }) {
  const { data, error } = useRemote(
    `/reconciliation/runs/${p.run.id}/outcomes`,
    p.token,
    p.revision
  )
  const [source, setSource] = useState<{ kind: string; id: string } | null>(null)
  return (
    <section className="panel outcome-panel" aria-label="Mathematical outcomes">
      <div className="panel-heading">
        <div>
          <h2>Mathematical outcomes &amp; linked sources</h2>
          <p>Every amount has a formula, source and review state.</p>
        </div>
        <div className="button-group">
          <button
            onClick={() =>
              p.act(
                () =>
                  download(
                    `/reconciliation/runs/${p.run.id}/report?format=csv`,
                    p.token,
                    'reconciliation-outcomes.csv'
                  ),
                'Mathematical outcomes CSV downloaded.'
              )
            }
          >
            Download outcomes CSV
          </button>
          <button
            onClick={() =>
              p.act(
                () =>
                  download(
                    `/reconciliation/runs/${p.run.id}/report?format=json`,
                    p.token,
                    'reconciliation-report.json'
                  ),
                'Full calculation and provenance report downloaded.'
              )
            }
          >
            Download full report
          </button>
        </div>
      </div>
      {error ? (
        <p role="alert" className="error">
          {error}
        </p>
      ) : !data ? (
        <p role="status">Loading formulas and source associations…</p>
      ) : (
        <div className="record-body">
          <div className="association-grid">
            <article>
              <small>Invoice</small>
              <button
                className="link-button"
                onClick={() => setSource({ kind: 'invoices', id: p.invoiceId })}
              >
                {data.invoice_reference} ↗
              </button>
            </article>
            {data.contract && (
              <article>
                <small>Approved contract</small>
                <button
                  className="link-button"
                  onClick={() => setSource({ kind: 'contracts', id: data.contract.id })}
                >
                  {data.contract.title} ↗
                </button>
              </article>
            )}
            {data.contractor && (
              <article>
                <small>Associated supplier</small>
                <button
                  className="link-button"
                  onClick={() => setSource({ kind: 'contractors', id: data.contractor.id })}
                >
                  {data.contractor.name} ↗
                </button>
              </article>
            )}
          </div>
          {data.source_file && (
            <p>
              Invoice source:{' '}
              <button
                className="link-button"
                onClick={() =>
                  p.act(
                    () =>
                      download(
                        `/ingestion/${data.source_file.id}/download/source`,
                        p.token,
                        data.source_file.filename
                      ),
                    'Invoice source downloaded.'
                  )
                }
              >
                {data.source_file.filename}
              </button>
            </p>
          )}
          <p className="calculation">{data.conservation_formula}</p>
          {data.lines.map((line: Row, index: number) => (
            <article className="outcome-line" key={line.id}>
              <h3>
                Line {index + 1} · {line.invoice_source.work_reference || 'No evidence reference'}{' '}
                <span className="badge">
                  {line.conservation_valid ? 'Amounts reconcile' : 'Check amount balance'}
                </span>
              </h3>
              <RecordsTable label={`Calculation steps for line ${index + 1}`}>
                <table>
                  <thead>
                    <tr>
                      <th>Outcome</th>
                      <th>Formula / policy</th>
                      <th>Result</th>
                    </tr>
                  </thead>
                  <tbody>
                    {line.calculation_steps.map((step: Row) => (
                      <tr key={step.label}>
                        <td>{step.label}</td>
                        <td className="formula">{step.formula}</td>
                        <td className="numeric">
                          {step.unit === 'USD' ? `USD ${step.value}` : `${step.value} ${step.unit}`}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </RecordsTable>
              {!line.variance_determined && (
                <p className="policy-note">
                  The variance is undetermined. Zero in the variance column is not a finding of zero
                  liability or proof of an overcharge.
                </p>
              )}
              <div className="source-comparison">
                <article>
                  <h4>Frozen invoice input</h4>
                  <p>
                    {line.invoice_source.quantity} hours at USD {line.invoice_source.unit_price}
                    /hour
                  </p>
                  <small>
                    {line.invoice_source.service_date.slice(0, 10)} ·{' '}
                    {line.invoice_source.work_code}
                  </small>
                </article>
                <article>
                  <h4>Approved pricing source</h4>
                  {line.contract_source ? (
                    <>
                      <p>Version {line.contract_source.id}</p>
                      {line.contract_source.rates.map((r: Row) => (
                        <small key={r.work_code}>
                          {r.work_code}: USD {r.rate}/{r.unit}
                          {r.cap_hours ? ` · Per-line cap ${r.cap_hours} hours` : ''}
                        </small>
                      ))}
                    </>
                  ) : (
                    <p>No eligible approved terms for this service date.</p>
                  )}
                </article>
                <article>
                  <h4>Operational evidence</h4>
                  {line.evidence_sources.length ? (
                    line.evidence_sources.map((w: Row) => (
                      <div key={w.id}>
                        <button
                          className="link-button"
                          onClick={() => setSource({ kind: 'evidence', id: w.id })}
                        >
                          {w.work_reference} · {w.quantity} hours ↗
                        </button>
                        <small>
                          {w.status} · Verifier {w.attested_by}
                        </small>
                        {w.import_file && (
                          <button
                            onClick={() =>
                              p.act(
                                () =>
                                  download(
                                    `/ingestion/${w.import_file.id}/download/source`,
                                    p.token,
                                    w.import_file.filename
                                  ),
                                'Evidence source downloaded.'
                              )
                            }
                          >
                            Source: {w.import_file.filename}
                          </button>
                        )}
                      </div>
                    ))
                  ) : (
                    <p>No unique attested evidence allocated.</p>
                  )}
                </article>
              </div>
              <p className="muted">
                Eligible but not approved: USD {line.eligible_unapproved}.{' '}
                {line.decision_source
                  ? `Decision: ${line.decision_source.decision} · ${line.decision_source.reason}`
                  : 'A separate finance decision is required.'}
              </p>
            </article>
          ))}
          <small className="mono">
            Rule set {data.rule_set_version} · Frozen input SHA-256 {data.input_hash}
          </small>
        </div>
      )}
      {source && (
        <RecordPanel
          key={source.kind + source.id}
          {...p}
          {...source}
          close={() => setSource(null)}
        />
      )}
    </section>
  )
}
