import { useCallback, useEffect, useRef, useState } from 'react'

// Runs `fn` now and every `ms`, pausing while the tab is hidden.
export function usePolling(fn, ms = 15000, deps = []) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [updatedAt, setUpdatedAt] = useState(null)
  const fnRef = useRef(fn)
  fnRef.current = fn

  const refresh = useCallback(async () => {
    try {
      const result = await fnRef.current()
      setData(result)
      setError(null)
      setUpdatedAt(new Date())
    } catch (e) {
      setError(e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    setLoading(true)
    refresh()
    const id = setInterval(() => {
      if (!document.hidden) refresh()
    }, ms)
    return () => clearInterval(id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ms, refresh, ...deps])

  return { data, error, loading, updatedAt, refresh }
}

// Re-renders every `ms` so relative timers ("waiting 12 min") stay live.
export function useNow(ms = 30000) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), ms)
    return () => clearInterval(id)
  }, [ms])
  return now
}
