// Types and calls for the backend API (see http://localhost:8000/docs).

export type VehicleType = 'tram' | 'bus' | 'trolleybus' | 'other'

export type LineResult = {
  route_id: string
  short_name: string
  route_type: number
  vehicle_type: VehicleType
  color: string | null
  termini: string[]
}

export type StopResult = {
  stop_id: string
  name: string
  description: string | null
  lat: number
  lon: number
}

export type SearchResponse = {
  query: string
  lines: LineResult[]
  stops: StopResult[]
}

export const VEHICLE_LABELS: Record<VehicleType, string> = {
  tram: 'Tramvai',
  bus: 'Autobuz',
  trolleybus: 'Troleibuz',
  other: 'Altul',
}

export async function getJson<T>(url: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(url, { signal })
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`)
  }
  return (await response.json()) as T
}

export function search(q: string, signal?: AbortSignal): Promise<SearchResponse> {
  return getJson<SearchResponse>(`/api/search?q=${encodeURIComponent(q)}`, signal)
}

export type DirectionStats = {
  direction_id: number | null
  headsign: string | null
  observation_count: number
  mean_delay_seconds: number
  median_delay_seconds: number
  p90_delay_seconds: number
  on_time_pct: number
}

export type LineStats = {
  route_id: string
  short_name: string
  vehicle_type: VehicleType
  color: string | null
  date_from: string
  date_to: string
  directions: DirectionStats[]
  message: string | null
}

export function lineStats(
  routeId: string,
  range: { dateFrom?: string; dateTo?: string },
  signal?: AbortSignal,
): Promise<LineStats> {
  const params = new URLSearchParams()
  if (range.dateFrom) params.set('date_from', range.dateFrom)
  if (range.dateTo) params.set('date_to', range.dateTo)
  return getJson<LineStats>(`/api/lines/${encodeURIComponent(routeId)}/stats?${params}`, signal)
}
