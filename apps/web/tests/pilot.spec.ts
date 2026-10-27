import { test, expect } from '@playwright/test'
import type { APIRequestContext, Page } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import { createHash, randomUUID } from 'node:crypto'
import { readFile } from 'node:fs/promises'

const apiUrl = process.env.E2E_API_URL || 'http://127.0.0.1:8000/api/v1'
const scope = { org_id: 'org-demo', site_id: 'site-1' }

async function token(request: APIRequestContext, persona: string) {
  const response = await request.post(`${apiUrl}/auth/dev-login`, { data: { email: `${persona}@demo.local`, password: 'demo' } })
  expect(response.ok()).toBeTruthy()
  return (await response.json()).access_token as string
}

async function post(request: APIRequestContext, path: string, auth: string, data: unknown) {
  const response = await request.post(`${apiUrl}${path}`, { headers: { Authorization: `Bearer ${auth}` }, data })
  expect(response.ok(), await response.text()).toBeTruthy()
  return response.json()
}

async function login(page: Page, persona: string) {
  await page.goto('/')
  await page.getByLabel('Pilot account').fill(`${persona}@demo.local`)
  await page.getByLabel('Password', { exact: true }).fill('demo')
  await page.getByRole('button', { name: 'Sign in →' }).click()
  await expect(page.getByRole('button', { name: `Sign out ${persona}@demo.local` })).toBeVisible()
}

async function openInvoice(page: Page, reference: string) {
  await page.getByRole('link', { name: 'Invoices', exact: true }).click()
  await page.getByRole('button', { name: reference, exact: true }).click()
  await expect(page.getByRole('heading', { name: reference, exact: true })).toBeVisible()
}

test('independent evidence → queued assessment → partial finance approval → immutable export', async ({ page, request }, testInfo) => {
  const suffix = randomUUID().slice(0, 8)
  const [ap, preparer, approver, verifier, verifier2, finance] = await Promise.all(
    ['ap', 'preparer', 'approver', 'verifier', 'verifier2', 'finance'].map(p => token(request, p)),
  )
  const contract = await post(request, '/contracts', preparer, { ...scope, contractor_id: 'ctr-1', title: `E2E equipment ${suffix}`, effective_from: '2026-01-01', rate: '240' })
  await post(request, `/contracts/${contract.id}/approve?version_id=${contract.version_id}`, approver, {})
  const work = await post(request, '/evidence', verifier, { ...scope, contract_id: contract.id, work_reference: `E2E-${suffix}`, quantity: '145', service_date: '2026-10-10' })
  await post(request, `/evidence/${work.id}/attest`, verifier2, {})
  const reference = `E2E-INV-${suffix}`
  const invoice = await post(request, '/invoices', ap, { ...scope, contract_id: contract.id, supplier_invoice_no: reference, lines: [{ work_reference: `E2E-${suffix}`, quantity: '160', unit_price: '250', service_date: '2026-10-10' }] })
  await login(page, 'ap')
  await openInvoice(page, reference)
  await page.getByRole('button', { name: 'Run reconciliation', exact: true }).click()
  await expect(page.getByRole('status').filter({ hasText: 'Assessment completed using approved terms and attested evidence.' })).toBeVisible()
  await expect(page.getByText('$34,800.00', { exact: true })).toBeVisible()
  await expect(page.getByText('$5,200.00', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Approve eligible costs' })).toHaveCount(0)
  await page.getByRole('button', { name: 'Sign out ap@demo.local' }).click()
  await login(page, 'finance')
  await openInvoice(page, reference)
  await page.getByLabel('Approve amount (USD)').fill('30000')
  await page.getByLabel('Decision reason').fill('Independent synthetic E2E review with partial approval')
  await page.getByRole('button', { name: 'Approve eligible costs' }).click()
  await expect(page.getByRole('status').filter({ hasText: 'Finance approval recorded with an immutable decision snapshot.' })).toBeVisible()
  const downloading = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Export approved costs ↗' }).click()
  const download = await downloading
  const bytes = await readFile((await download.path())!)
  expect(bytes.toString()).toContain('3000000')
  const detail = await request.get(`${apiUrl}/invoices/${invoice.id}`, { headers: { Authorization: `Bearer ${finance}` } })
  const run = (await detail.json()).current_run
  const batch = await post(request, '/exports', finance, { ...scope, run_id: run.id, idempotency_key: `export-${run.id}` })
  expect(batch.total_minor).toBe(3000000)
  expect(batch.artifact_hash).toBe(createHash('sha256').update(bytes).digest('hex'))
  await page.screenshot({ path: testInfo.outputPath('approved-desktop.png'), fullPage: true })
})

test('mobile sign-in and dashboard pass the axe WCAG A/AA smoke audit', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  expect((await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze()).violations).toEqual([])
  await login(page, 'auditor')
  await expect(page.getByRole('heading', { name: 'Invoice workbench' })).toBeVisible()
  expect((await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze()).violations).toEqual([])
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
  await page.screenshot({ path: testInfo.outputPath('overview-mobile.png'), fullPage: true })
})

test('administrator provisions a site and grants then revokes a local user', async ({ page }) => {
  const suffix = randomUUID().slice(0, 8)
  await login(page, 'admin')
  await page.getByRole('link', { name: 'Settings', exact: true }).click()
  await page.getByText('Create mine site', { exact: true }).click()
  await page.getByLabel('New site name').fill(`E2E site ${suffix}`)
  await page.getByRole('button', { name: 'Create site', exact: true }).click()
  await expect(page.getByRole('option', { name: `E2E site ${suffix}` })).toHaveCount(1)
  await page.getByText('Create local user', { exact: true }).click()
  const email = `e2e-${suffix}@demo.local`
  await page.getByLabel('New user email').fill(email)
  await page.getByLabel('Initial password').fill('Synthetic-e2e-only-2026')
  await page.getByLabel('Initial site role').selectOption('auditor')
  await page.getByRole('button', { name: 'Create user in selected site' }).click()
  const row = page.getByRole('row').filter({ hasText: email })
  await expect(row).toBeVisible()
  await row.getByRole('button', { name: 'Revoke grant' }).click()
  await expect(row).toHaveCount(0)
})

test('CSV mapping and ingestion → invoice editing → linked evidence and mathematical outputs', async ({ page, request }, testInfo) => {
  const suffix = randomUUID().slice(0, 8)
  const reference = `FILE-INV-${suffix}`
  const workReference = `FILE-SHIFT-${suffix}`
  const [verifier, verifier2] = await Promise.all(['verifier', 'verifier2'].map(p => token(request, p)))
  const work = await post(request, '/evidence', verifier, { ...scope, contract_id: 'contract-1', work_reference: workReference, quantity: '145', service_date: '2026-10-10' })
  await post(request, `/evidence/${work.id}/attest`, verifier2, {})
  await login(page, 'ap')
  await page.getByRole('link', { name: 'Files', exact: true }).click()
  await page.getByLabel('File contains').selectOption('invoice')
  await page.getByLabel('Associate file with contract').selectOption('contract-1')
  const raw = Buffer.from(`Invoice,Shift,Code,Hours,Day,Unit,Price\n${reference},${workReference},EQ-HIRE,160,2026-10-10,hour,250\n`)
  await page.getByLabel('CSV or XLSX file').setInputFiles({ name: `invoice-${suffix}.csv`, mimeType: 'text/csv', buffer: raw })
  await page.getByRole('button', { name: 'Upload & preview' }).click()
  await expect(page.getByRole('heading', { name: 'Column mapping', exact: true })).toBeVisible()
  for (const [target, source] of Object.entries({ supplier_invoice_no: 'Invoice', work_reference: 'Shift', work_code: 'Code', quantity: 'Hours', service_date: 'Day', unit: 'Unit', unit_price: 'Price' })) {
    await page.getByRole('combobox', { name: `Map ${target}`, exact: true }).selectOption(source)
  }
  await page.getByRole('button', { name: 'Validate mapped rows' }).click()
  await page.getByRole('button', { name: 'Import 1 validated rows' }).click()
  await expect(page.getByText('Imported 1 rows. Linked records are available below.', { exact: true })).toBeVisible()
  const sourceDownload = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Download original file', exact: true }).click()
  expect(await readFile((await (await sourceDownload).path())!)).toEqual(raw)
  await page.getByRole('button', { name: `${reference} · invoices ↗`, exact: true }).click()
  await page.getByRole('button', { name: 'Edit / associations', exact: true }).click()
  await page.getByRole('button', { name: 'Edit record', exact: true }).click()
  await page.getByLabel('Hours · line 1', { exact: true }).fill('150')
  await page.getByLabel('Hourly price · line 1', { exact: true }).fill('245')
  await page.getByRole('button', { name: 'Save changes', exact: true }).click()
  await expect(page.getByRole('status').filter({ hasText: 'Record updated.' })).toBeVisible()
  await page.getByRole('button', { name: 'Close details', exact: true }).click()
  await page.getByRole('button', { name: 'Run reconciliation', exact: true }).click()
  await expect(page.getByRole('status').filter({ hasText: 'Assessment completed using approved terms' })).toBeVisible()
  const outcomes = page.getByRole('region', { name: 'Mathematical outcomes', exact: true })
  await expect(outcomes.getByText('USD 1950.00', { exact: true })).toBeVisible()
  await expect(outcomes.getByText('USD 36750.00', { exact: true })).toBeVisible()
  await expect(outcomes.getByRole('button', { name: new RegExp(workReference + '.*145') })).toBeVisible()
  const downloading = page.waitForEvent('download')
  await outcomes.getByRole('button', { name: 'Download outcomes CSV', exact: true }).click()
  const output = await readFile((await (await downloading).path())!)
  expect(output.toString()).toContain('1950.000000')
  expect(output.toString()).toContain(workReference)
  await page.screenshot({ path: testInfo.outputPath('file-ingestion-outcomes.png'), fullPage: true })
})

test('unused supplier and invoice records can be edited and deleted in the UI', async ({ page, request }) => {
  const suffix = randomUUID().slice(0, 8)
  await login(page, 'admin')
  await page.getByRole('link', { name: 'Contractors', exact: true }).click()
  await page.getByRole('button', { name: '+ Add contractor', exact: true }).click()
  await page.getByLabel('Contractor name', { exact: true }).fill(`CRUD supplier ${suffix}`)
  await page.getByRole('button', { name: 'Save record', exact: true }).click()
  const supplierRow = page.getByRole('row').filter({ hasText: `CRUD supplier ${suffix}` })
  await supplierRow.getByRole('button', { name: 'Details & edit', exact: true }).click()
  await page.getByRole('button', { name: 'Edit record', exact: true }).click()
  await page.getByLabel('Contractor name', { exact: true }).fill(`Renamed supplier ${suffix}`)
  await page.getByRole('button', { name: 'Save changes', exact: true }).click()
  await expect(page.getByRole('heading', { name: `Renamed supplier ${suffix}`, exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Delete record', exact: true }).click()
  await page.getByRole('button', { name: 'Confirm deletion', exact: true }).click()
  await expect(page.getByRole('row').filter({ hasText: `Renamed supplier ${suffix}` })).toHaveCount(0)
  const ap = await token(request, 'ap')
  const invoice = await post(request, '/invoices', ap, { ...scope, contract_id: 'contract-1', supplier_invoice_no: `DELETE-INV-${suffix}`, lines: [{ quantity: '1', unit_price: '240', service_date: '2026-10-10' }] })
  await page.getByRole('button', { name: 'Sign out admin@demo.local' }).click()
  await login(page, 'ap')
  await page.getByRole('link', { name: 'Invoices', exact: true }).click()
  await page.getByRole('row').filter({ hasText: `DELETE-INV-${suffix}` }).getByRole('button', { name: 'Details & edit' }).click()
  await page.getByRole('button', { name: 'Delete record', exact: true }).click()
  await page.getByRole('button', { name: 'Confirm deletion', exact: true }).click()
  await expect(page.getByRole('row').filter({ hasText: `DELETE-INV-${suffix}` })).toHaveCount(0)
  expect((await request.get(`${apiUrl}/invoices/${invoice.id}`, { headers: { Authorization: `Bearer ${ap}` } })).status()).toBe(404)
})
