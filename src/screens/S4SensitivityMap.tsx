import { useEffect, useState } from 'react'
import { getScenario, type Receptor } from '../api/scenarios'
import { errorMessage, isAbort, type Async } from '../utils/async'
import { formatNumber } from './s4Display'

/* ---------- 민감도 지도: 공사장 중심, 100m·200m 반경과 수음점 거리 ---------- */

const W = 360
const H = 280
const CX = W / 2
const CY = H / 2
/** 지도 가장자리 반경(px)과 그에 해당하는 거리(m). 이보다 먼 수음점은 가장자리에 붙여 그린다. */
const EDGE_PX = 118
const EDGE_M = 250
const RINGS_M = [100, 200]

type Level = 'high' | 'mid' | 'low'
const TYPE_LABEL: Record<Receptor['type'], string> = {
  hospital: '병원',
  school: '학교',
  residential: '주거',
  university: '대학',
  commercial: '상업',
}
const TYPE_LEVEL: Record<Receptor['type'], Level> = {
  hospital: 'high',
  school: 'high',
  residential: 'mid',
  university: 'mid',
  commercial: 'low',
}
const LEVEL_LABEL: Record<Level, string> = { high: '높음 (병원·학교)', mid: '보통 (주거·대학)', low: '낮음 (상업)' }

const px = (m: number) => (Math.min(m, EDGE_M) / EDGE_M) * EDGE_PX

function zoneOf(m: number): string {
  if (m <= 100) return '100m 이내'
  if (m <= 200) return '200m 이내'
  return '200m 밖'
}

export function S4SensitivityMap({ scenarioId }: { scenarioId: string }) {
  const [state, setState] = useState<Async<Receptor[]>>({ status: 'loading' })

  useEffect(() => {
    const controller = new AbortController()
    getScenario(scenarioId, controller.signal)
      .then((data) => setState({ status: 'success', data: data.receptors }))
      .catch((err) => !isAbort(err) && setState({ status: 'error', message: errorMessage(err) }))
    return () => controller.abort()
  }, [scenarioId])

  if (state.status === 'loading') {
    return (
      <p className="muted" role="status">
        수음점 정보를 불러오는 중…
      </p>
    )
  }
  if (state.status === 'error') {
    return (
      <div className="hint error" role="alert">
        민감도 지도를 불러오지 못했습니다. {state.message}
      </div>
    )
  }

  // 공사장 좌표가 응답에 없어 방향은 알 수 없다. 거리만 실제 값이고 방향은 겹치지 않게 고르게 배치한다.
  const receptors = [...state.data].sort((a, b) => a.distance_to_source_m - b.distance_to_source_m)
  const placed = receptors.map((r, i) => {
    const angle = ((i * 360) / Math.max(receptors.length, 1) - 60) * (Math.PI / 180)
    const d = px(r.distance_to_source_m)
    return { r, x: CX + d * Math.cos(angle), y: CY + d * Math.sin(angle), outside: r.distance_to_source_m > EDGE_M }
  })

  return (
    <figure className="s4-map">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="공사장 기준 100m·200m 반경과 수음점 거리 지도">
        <rect x="0" y="0" width={W} height={H} rx="10" className="map-bg" />
        <circle cx={CX} cy={CY} r={EDGE_PX} className="edge" />
        {RINGS_M.map((m) => (
          <g key={m}>
            <circle cx={CX} cy={CY} r={px(m)} className={`ring r${m}`} />
            <text x={CX} y={CY - px(m) - 4} className="ring-label" textAnchor="middle">
              {m}m
            </text>
          </g>
        ))}
        {placed.map(({ r, x, y }) => (
          <line key={`l-${r.id}`} x1={CX} y1={CY} x2={x} y2={y} className="ray" />
        ))}
        <rect x={CX - 6} y={CY - 6} width="12" height="12" rx="2" className="site" />
        <text x={CX} y={CY + 20} className="site-label" textAnchor="middle">
          공사장
        </text>
        {placed.map(({ r, x, y, outside }) => {
          // 긴 이름이 지도 밖으로 나가지 않게 바깥쪽 수음점은 안쪽으로 정렬한다.
          const anchor = x > CX + 30 ? 'end' : x < CX - 30 ? 'start' : 'middle'
          return (
          <g key={r.id} className={`rcp ${TYPE_LEVEL[r.type]}${outside ? ' outside' : ''}`}>
            <circle cx={x} cy={y} r="6" />
            <text x={x} y={y - 10} textAnchor={anchor} className="rcp-name">
              {r.name}
            </text>
            <text x={x} y={y + 18} textAnchor={anchor} className="rcp-dist">
              {outside ? `→ ${formatNumber(r.distance_to_source_m)}m` : `${formatNumber(r.distance_to_source_m)}m`}
            </text>
          </g>
          )
        })}
      </svg>
      <figcaption className="s4-map-cap muted">
        거리는 공사장 대표점과 수음점 사이의 수평 직선거리입니다. 공사장 좌표가 없어 방향은 실제와 다르며, {EDGE_M}m보다 먼
        수음점은 가장자리에 표시하고 실제 거리를 적었습니다.
      </figcaption>
      <div className="s4-map-legend">
        {(['high', 'mid', 'low'] as const).map((l) => (
          <span key={l}>
            <i className={`legend-dot ${l}`} aria-hidden="true" />
            민감도 {LEVEL_LABEL[l]}
          </span>
        ))}
      </div>
      {receptors.length === 0 ? (
        <p className="muted">이 시나리오에는 등록된 수음점이 없습니다.</p>
      ) : (
        <div className="scroll">
          <table className="s4-table s4-rcp-table">
            <thead>
              <tr>
                <th>수음점</th>
                <th>유형</th>
                <th>공사장까지 거리</th>
                <th>반경</th>
              </tr>
            </thead>
            <tbody>
              {receptors.map((r) => (
                <tr key={r.id}>
                  <td>{r.name}</td>
                  <td>{TYPE_LABEL[r.type]}</td>
                  <td>{formatNumber(r.distance_to_source_m)}m</td>
                  <td>{zoneOf(r.distance_to_source_m)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </figure>
  )
}
