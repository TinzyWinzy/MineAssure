// Versioned API wire values; monetary business calculations remain on the server.
export type Row = Record<string, any>
export const base = import.meta.env.VITE_API_URL || '/api/v1'
export async function api(
  path: string,
  token: string,
  body?: unknown,
  method?: 'PUT' | 'DELETE' | 'POST'
): Promise<any> {
  const response = await fetch(`${base}${path}`, {
    method: method || (body !== undefined ? 'POST' : 'GET'),
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
    },
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
  })
  const data = await response.json().catch(() => null)
  if (!response.ok) {
    const detail = data?.detail || data?.error?.message || data?.message
    throw new Error(
      Array.isArray(detail)
        ? detail.map((v: Row) => `${v.loc?.slice(1).join('.')}: ${v.msg}`).join('; ')
        : typeof detail === 'string'
          ? detail
          : `Request failed (${response.status}). Please retry.`
    )
  }
  return data
}
export async function download(path: string, token: string, filename: string) {
  const response = await fetch(`${base}${path}`, { headers: { Authorization: `Bearer ${token}` } })
  if (!response.ok) {
    const data = await response.json().catch(() => null)
    throw new Error(data?.detail || data?.error?.message || 'Download failed.')
  }
  const url = URL.createObjectURL(await response.blob())
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
export function money(value: string | number | null | undefined) {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
  }).format(Number(value || 0))
}
