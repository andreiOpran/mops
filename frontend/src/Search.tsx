import { useEffect, useState } from 'react'
import { search, VEHICLE_LABELS, type SearchResponse } from './api.ts'
import LineBadge from './LineBadge.tsx'

function Search() {
  const [query, setQuery] = useState('')
  const [result, setResult] = useState<SearchResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const q = query.trim()
    if (!q) {
      return
    }
    const controller = new AbortController()
    const timer = setTimeout(() => {
      search(q, controller.signal)
        .then((data) => {
          setResult(data)
          setError(null)
        })
        .catch((err: Error) => {
          if (err.name !== 'AbortError') setError(err.message)
        })
    }, 250)
    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [query])

  const shown = query.trim() ? result : null

  return (
    <section>
      <input
        className="search-input"
        aria-label="Caută"
        type="search"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="Linie sau stație"
        autoFocus
      />

      {error && <p className="error">Eroare: {error}</p>}

      {shown && shown.lines.length === 0 && shown.stops.length === 0 && (
        <p className="muted">Niciun rezultat.</p>
      )}

      {shown && shown.lines.length > 0 && (
        <>
          <h2>Linii</h2>
          <ul className="results">
            {shown.lines.map((line) => (
              <li key={line.route_id}>
                <a href={`#/lines/${encodeURIComponent(line.route_id)}`}>
                  <LineBadge number={line.short_name} color={line.color} />
                  <span>
                    {VEHICLE_LABELS[line.vehicle_type]}
                    {line.termini.length > 0 && <span className="muted"> · {line.termini.join(' – ')}</span>}
                  </span>
                </a>
              </li>
            ))}
          </ul>
        </>
      )}

      {shown && shown.stops.length > 0 && (
        <>
          <h2>Stații</h2>
          <ul className="results">
            {shown.stops.map((stop) => (
              <li key={stop.stop_id}>
                <span>
                  {stop.name}
                  {stop.description && <span className="muted">{stop.description}</span>}
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  )
}

export default Search
