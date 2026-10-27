import { useEffect, useState } from 'react'
import { api } from './api'

export function useRemote(path: string, token: string, revision = 0) {
  const key = `${token}:${path}:${revision}`
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
  }, [key, path, token, revision])
  return state.key === key ? state : { data: null, error: '' }
}
