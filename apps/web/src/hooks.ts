import { useEffect, useState } from 'react'
import { api } from './api'

export type Scope = { org_id: string; site_id: string }
export type Props = {
  token: string
  userId: string
  scope: Scope
  query: string
  revision: number
  busy: boolean
  act: (fn: () => Promise<unknown>, message?: string) => Promise<void>
  can: (...roles: string[]) => boolean
}

export function useData(path: string, token: string, revision: number) {
  const key = token + ':' + path + ':' + revision
  const [state, setState] = useState<{ key: string; data: any; error: string }>({
    key: '',
    data: null,
    error: '',
  })
  useEffect(() => {
    let active = true
    api(path, token)
      .then((data) => {
        if (active) setState({ key, data, error: '' })
      })
      .catch((e) => {
        if (active) setState({ key, data: null, error: e.message })
      })
    return () => {
      active = false
    }
  }, [path, token, revision, key])
  return state.key === key ? state : { data: null, error: '' }
}
