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
