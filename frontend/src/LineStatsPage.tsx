import { useEffect, useState, type FormEvent } from 'react'
import { lineStats, VEHICLE_LABELS, type LineStats } from './api.ts'
import LineBadge from './LineBadge.tsx'

// "+1,5 min" / "-0,8 min"
function minutes(seconds: number): string {
  const value = (seconds / 60).toLocaleString('ro-RO', { maximumFractionDigits: 1, minimumFractionDigits: 1 })
  return `${seconds > 0 ? '+' : ''}${value} min`
}

const MAX_RANGE_DAYS = 366

// Number of days from `from` to `to`, both included (ISO dates).
function days(from: string, to: string): number {
  return (Date.parse(to) - Date.parse(from)) / 86_400_000 + 1
}

function percent(value: number): string {
  return `${value.toLocaleString('ro-RO', { maximumFractionDigits: 1 })}%`
}

function LineStatsPage({ routeId }: { routeId: string }) {
  const [range, setRange] = useState<{ dateFrom?: string; dateTo?: string }>({})
  const [stats, setStats] = useState<LineStats | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [rangeError, setRangeError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    lineStats(routeId, range, controller.signal)
      .then((data) => {
        setStats(data)
        setError(null)
      })
      .catch((err: Error) => {
        if (err.name !== 'AbortError') setError(err.message === 'HTTP 404' ? 'Linia nu există.' : err.message)
      })
    return () => controller.abort()
  }, [routeId, range])

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const dateFrom = String(form.get('date_from'))
    const dateTo = String(form.get('date_to'))
    // ISO dates compare correctly as strings.
    if (dateFrom > dateTo) {
      setRangeError('Data de început trebuie să fie înaintea datei de sfârșit.')
      return
    }
    if (days(dateFrom, dateTo) > MAX_RANGE_DAYS) {
      setRangeError(`Intervalul poate avea cel mult ${MAX_RANGE_DAYS} de zile.`)
      return
    }
    setRangeError(null)
    setRange({ dateFrom, dateTo })
  }

  const back = (
    <a className="back" href="#/">
      ← Înapoi
    </a>
  )

  if (error) {
    return (
      <section>
        {back}
        <p className="error">Eroare: {error}</p>
      </section>
    )
  }
  if (!stats) return <p className="muted">Se încarcă...</p>

  return (
    <section>
      {back}
      <h2 className="line-title">
        <LineBadge number={stats.short_name} color={stats.color} />
        {VEHICLE_LABELS[stats.vehicle_type]}
      </h2>

      {/* key: reset the inputs to the range the server actually used */}
      <form className="range" onSubmit={onSubmit} key={`${stats.date_from}/${stats.date_to}`}>
        <label>
          De la
          <input type="date" name="date_from" defaultValue={stats.date_from} required />
        </label>
        <label>
          Până la
          <input type="date" name="date_to" defaultValue={stats.date_to} required />
        </label>
        <button type="submit">Afișează</button>
      </form>
      {rangeError && <p className="error">{rangeError}</p>}

      {stats.message ? (
        <p className="notice">{stats.message}</p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Sens</th>
                <th className="num">Observații</th>
                <th className="num">Medie</th>
                <th className="num">Mediană</th>
                <th className="num">Percentila 90</th>
                <th className="num">La timp</th>
              </tr>
            </thead>
            <tbody>
              {stats.directions.map((d) => (
                <tr key={d.direction_id ?? 'unknown'}>
                  <td>{d.headsign ?? 'necunoscut'}</td>
                  <td className="num">{d.observation_count.toLocaleString('ro-RO')}</td>
                  <td className="num">{minutes(d.mean_delay_seconds)}</td>
                  <td className="num">{minutes(d.median_delay_seconds)}</td>
                  <td className="num">{minutes(d.p90_delay_seconds)}</td>
                  <td className="num">{percent(d.on_time_pct)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

export default LineStatsPage
