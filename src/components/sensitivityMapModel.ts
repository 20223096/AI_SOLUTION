import type { PublicDataCatalog } from '../api/publicData'

type Row = Record<string, unknown>
export type MapPoint = { id: string; name: string; type: string; lat: number; lon: number; source: string; role: string }

export function buildSensitivityMap(catalog: PublicDataCatalog) {
  const points: MapPoint[] = []
  for (const row of catalog.official_facilities as Row[]) {
    const lat = Number(row.latitude), lon = Number(row.longitude)
    if (Number.isFinite(lat) && Number.isFinite(lon)) points.push({
      id: String(row.facility_id), name: String(row.name), type: String(row.type), lat, lon,
      source: '공식 공공데이터', role: '표시용 위치 · 현재 계산 수음점과 동일하다고 간주하지 않음',
    })
  }
  const distance = (catalog.receptor_distances as Row[])[0]
  if (distance) points.push({
    id: `project-${String(distance.project_id)}`, name: String(distance.project_name), type: 'construction',
    lat: Number(distance.project_latitude), lon: Number(distance.project_longitude), source: '공식 공공데이터',
    role: '공사 대표점 · 공사 선형/경계 아님',
  })
  const unavailable = (catalog.receptors as Row[])
    .filter((row) => !row.latitude || !row.longitude)
    .map((row) => ({ name: String(row.name), type: String(row.type), status: String(row.coordinate_accuracy || row.status) }))
  return { points, unavailable }
}
