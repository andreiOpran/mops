import { useEffect, useState } from 'react'
import { search, VEHICLE_LABELS, type SearchResponse } from './api.ts'

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
      <label>
        Caută o linie sau o stație:{' '}
        <input
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="ex. 41 sau piata unirii"
          autoFocus
        />
      </label>

      {error && <p>Eroare la căutare: {error}</p>}

      {shown && shown.lines.length === 0 && shown.stops.length === 0 && (
        <p>Niciun rezultat pentru „{shown.query}”.</p>
      )}

      {shown && shown.lines.length > 0 && (
        <>
          <h2>Linii</h2>
          <ul>
            {shown.lines.map((line) => (
              <li key={line.route_id}>
                <a href={`#/lines/${encodeURIComponent(line.route_id)}`}>
                  {VEHICLE_LABELS[line.vehicle_type]} {line.short_name}
                </a>
                {line.termini.length > 0 && <> : {line.termini.join(' – ')}</>}
              </li>
            ))}
          </ul>
        </>
      )}

      {shown && shown.stops.length > 0 && (
        <>
          <h2>Stații</h2>
          <ul>
            {shown.stops.map((stop) => (
              <li key={stop.stop_id}>
                {stop.name}
                {stop.description && <> ({stop.description})</>}
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  )
}

export default Search
