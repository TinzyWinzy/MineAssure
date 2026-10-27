import type { ReactNode } from 'react'

export type WorkflowProps = {
  token: string
  query: string
  scope: { org_id: string; site_id: string }
  revision: number
  busy: boolean
  can: (...roles: string[]) => boolean
  act: (fn: () => Promise<unknown>, message?: string) => Promise<void>
}

export function FormField({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
    </label>
  )
}

export function RecordsTable({
  children,
  label = 'Scrollable records',
}: {
  children: ReactNode
  label?: string
}) {
  return (
    <div className="table-wrap" tabIndex={0} role="region" aria-label={label}>
      {children}
    </div>
  )
}
