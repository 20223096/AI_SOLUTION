import { useEffect, useState } from 'react'
import { getPublicDataCatalog, type PublicDataCatalog } from '../api/publicData'
import { errorMessage, isAbort, type Async } from '../utils/async'
import { buildSensitivityMap } from './sensitivityMapModel'
import './SensitivityMap.css'

const TYPE_LABEL: Record<string, string> = { school: '학교', hospital: '병원', university: '대학', residential: '주거', construction: '공사 대표점' }

export function SensitivityMap() {
  const [state, setState] = useState<Async<PublicDataCatalog>>({ status: 'loading' })
  useEffect(() => {
    const controller = new AbortController()
    getPublicDataCatalog(controller.signal).then((data) => setState({ status: 'success', data }))
      .catch((e) => !isAbort(e) && setState({ status: 'error', message: errorMessage(e) }))
    return () => controller.abort()
  }, [])
  if (state.status === 'loading') return <p className="muted" role="status">민감시설 좌표를 불러오는 중…</p>
  if (state.status === 'error') return <div className="hint error">민감도 지도를 불러오지 못했습니다. {state.message}</div>
  const { points, unavailable } = buildSensitivityMap(state.data)
  const minLat = Math.min(...points.map((p) => p.lat)), maxLat = Math.max(...points.map((p) => p.lat))
  const minLon = Math.min(...points.map((p) => p.lon)), maxLon = Math.max(...points.map((p) => p.lon))
  const x = (lon: number) => 35 + ((lon - minLon) / (maxLon - minLon || 1)) * 530
  const y = (lat: number) => 265 - ((lat - minLat) / (maxLat - minLat || 1)) * 220
  return <div className="sensitivity-map">
    <svg viewBox="0 0 600 300" role="img" aria-label="공식 좌표가 확인된 신촌 민감시설과 공사 대표점 지도">
      <rect x="1" y="1" width="598" height="298" rx="12" className="map-bg" />
      <path d="M40 245 C150 190 205 220 300 145 S470 70 565 45" className="map-guide" />
      {points.map((p) => <g key={p.id} transform={`translate(${x(p.lon)} ${y(p.lat)})`} className={`map-point ${p.type}`}>
        <circle r={p.type === 'construction' ? 9 : 7} /><text x="11" y="4">{p.name}</text>
        <title>{`${TYPE_LABEL[p.type] ?? p.type} · ${p.role} · ${p.source}`}</title>
      </g>)}
    </svg>
    <div className="map-legend">{Object.entries(TYPE_LABEL).map(([key, label]) => <span key={key}><i className={key} />{label}</span>)}</div>
    <p className="map-note"><b>좌표 해석:</b> 시설 점과 공사 대표점은 공식 공개 좌표입니다. 배경 선은 위치 읽기용 도식이며 법정 경계·도로·공사 선형이 아닙니다.</p>
    <details><summary>좌표가 없어 지도에 표시하지 않은 수음점·시설 ({unavailable.length})</summary>
      <ul>{unavailable.map((r, i) => <li key={`${r.name}-${i}`}>{r.name} ({TYPE_LABEL[r.type] ?? r.type}) — {r.status}</li>)}</ul>
    </details>
    <p className="map-note"><b>계산 연결:</b> 현재 계산은 시나리오 수음점과 거리 가정을 사용합니다. 위 공식 시설점은 맥락 표시용이며, 공식 공사 대표점과의 직선거리를 음향 전파거리로 대체하지 않습니다.</p>
  </div>
}
