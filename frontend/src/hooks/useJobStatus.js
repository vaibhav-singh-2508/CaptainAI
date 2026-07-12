/**
 * useJobStatus — SSE hook for CaptainAI pipeline progress.
 *
 * Opens an EventSource to GET /status/{jobId} and emits:
 *   { stage, pct, result, error }
 *
 * `result` is populated once stage === "ready" and contains
 * the full ProcessedResult payload (subtitles + granite_result).
 *
 * The hook closes the EventSource when:
 *   - stage reaches "ready" or "error"
 *   - the component unmounts
 *   - jobId is cleared (null / undefined)
 */

import { useState, useEffect, useRef } from 'react'

const API_BASE = 'http://localhost:8000'

export function useJobStatus(jobId) {
  const [stage, setStage]   = useState(null)
  const [pct, setPct]       = useState(0)
  const [result, setResult] = useState(null)
  const [error, setError]   = useState(null)

  const esRef = useRef(null)

  useEffect(() => {
    // Clean up previous connection whenever jobId changes
    if (esRef.current) {
      esRef.current.close()
      esRef.current = null
    }

    if (!jobId) return

    // Reset state for the new job
    setStage(null)
    setPct(0)
    setResult(null)
    setError(null)

    const es = new EventSource(`${API_BASE}/status/${jobId}`)
    esRef.current = es

    es.onmessage = (evt) => {
      let data
      try {
        data = JSON.parse(evt.data)
      } catch {
        return
      }

      const { stage: s, pct: p, error: e, subtitles, granite_result } = data

      setStage(s)
      setPct(p ?? 0)

      if (e) {
        setError(e)
      }

      if (s === 'ready' && subtitles && granite_result) {
        setResult({ subtitles, granite_result })
        es.close()
        esRef.current = null
      }

      if (s === 'error') {
        es.close()
        esRef.current = null
      }
    }

    es.onerror = () => {
      setError('Connection to server lost. Please refresh and try again.')
      es.close()
      esRef.current = null
    }

    return () => {
      es.close()
      esRef.current = null
    }
  }, [jobId])

  return { stage, pct, result, error }
}
