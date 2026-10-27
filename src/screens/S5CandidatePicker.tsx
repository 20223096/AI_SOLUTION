import { useState, type KeyboardEvent } from 'react'
import { isSelectable, type CandidateResult, type RecommendationResponse } from '../api/recommendations'
import { assignmentTime, candidateLabel, formatDelta, formatNumber } from './s4Display'
import './S5CandidatePicker.css'

interface Props {
  res: RecommendationResponse
  selectedId: string | null
  onSelect: (id: string) => void
  onBack: () => void
  onNext: () => void
}

type Status = 'rec' | 'ok' | 'bad'
const STATUS_LABEL: Record<Status, string> = { rec: '추천', ok: '제약 충족 · 비추천', bad: '제약 위반' }

const statusOf = (c: CandidateResult, res: RecommendationResponse): Status =>
  isSelectable(c, res) ? 'rec' : c.prd_feasible ? 'ok' : 'bad'

/** 작업 전체 시간 범위 "08:00–17:00" */
function spanOf(c: CandidateResult): string {
  if (c.assignments.length === 0) return '–'
  const starts = c.assignments.map((a) => a.start).sort()
  const ends = c.assignments.map((a) => a.end).sort()
  return `${assignmentTime(starts[0])}–${assignmentTime(ends[ends.length - 1])}`
}

export function S5CandidatePicker({ res, selectedId, onSelect, onBack, onNext }: Props) {
  const selectable = res.candidates.filter((c) => isSelectable(c, res))
  const original = res.original_schedule
  const selected = selectable.find((c) => c.candidate_id === selectedId) ?? null

  return (
    <div className="grid s5">
      <section className="panel span2">
        <div className="ph">
          <span className="step">S5</span>
          <h2>조정안 고르기</h2>
          <span className="tag">추천 후보만 선택 가능</span>
        </div>
        <p className="sub">
          일정을 얼마나 옮기는지(변경량)와 주민에게 더해지는 소음 영향을 함께 봅니다. 추천 후보만 고를 수 있고, 고른 뒤에도 자동으로
          확정되지 않습니다.
        </p>

        <CandidateChart res={res} selectedId={selectedId} onSelect={onSelect} />

        {selectable.length === 1 && (
          <div className="hint">
            추천 후보가 <b>{candidateLabel(selectable[0].candidate_id)}</b> 하나입니다. 내용을 확인한 뒤 직접 선택해 주세요.
          </div>
        )}

        <div className="opts" role="radiogroup" aria-label="조정안">
          {selectable.map((c) => {
            const on = c.candidate_id === selectedId
            const di = original ? c.noise_impact.incremental_impact_cost - original.noise_impact.incremental_impact_cost : null
            const dov = original
              ? c.noise_impact.existing_noise_overlap_receptor_minutes - original.noise_impact.existing_noise_overlap_receptor_minutes
              : null
            return (
              <button
                key={c.candidate_id}
                type="button"
                role="radio"
                aria-checked={on}
                className={`opt${on ? ' on' : ''}`}
                onClick={() => onSelect(c.candidate_id)}
              >
                <b>{candidateLabel(c.candidate_id)}</b>
                <span className="opt-time">{spanOf(c)}</span>
                <span>일정 변경 {formatNumber(c.schedule_change_minutes)}분</span>
                <span>
                  추가 소음 영향 {formatNumber(c.noise_impact.incremental_impact_cost)}
                  {di != null && <span className="muted"> (원 일정 대비 {formatDelta(Number(di.toFixed(2)))})</span>}
                </span>
                <span>
                  기존 소음과 겹침 {formatNumber(c.noise_impact.existing_noise_overlap_receptor_minutes)}
                  {dov != null && <span className="muted"> ({formatDelta(dov)})</span>}
                </span>
              </button>
            )
          })}
        </div>
      </section>

      <section className="panel span2">
        <div className="row">
          <button type="button" className="ghost" onClick={onBack}>
            ← S4로 돌아가기
          </button>
          <button type="button" onClick={onNext} disabled={!selected}>
            다음: 조정 전후 비교 (S6)
          </button>
          {!selected && <span className="muted">조정안을 하나 골라 주세요.</span>}
        </div>
      </section>
    </div>
  )
}

/* ---------- 산점도: x = 일정 변경량, y = 추가 소음 영향 ---------- */

const W = 560
const H = 280
const PAD = { l: 52, r: 20, t: 16, b: 44 }

function niceTicks(min: number, max: number, count = 4): number[] {
  const range = max - min || 1
  const raw = range / count
  const pow = 10 ** Math.floor(Math.log10(raw))
  const step = [1, 2, 2.5, 5, 10].map((m) => m * pow).find((s) => s >= raw) ?? raw
  const start = Math.floor(min / step) * step
  const ticks: number[] = []
  for (let v = start; v <= max + step * 0.001; v += step) ticks.push(Number(v.toFixed(6)))
  if (ticks[ticks.length - 1] < max) ticks.push(Number((start + ticks.length * step).toFixed(6)))
  return ticks
}

function CandidateChart({
  res,
  selectedId,
  onSelect,
}: {
  res: RecommendationResponse
  selectedId: string | null
  onSelect: (id: string) => void
}) {
  const [hoverId, setHoverId] = useState<string | null>(null)
  const pts = res.candidates.map((c) => ({
    c,
    x: c.schedule_change_minutes,
    y: c.noise_impact.incremental_impact_cost,
    status: statusOf(c, res),
  }))
  const xTicks = niceTicks(0, Math.max(...pts.map((p) => p.x), 60))
  const yVals = pts.map((p) => p.y)
  const yTicks = niceTicks(Math.min(...yVals), Math.max(...yVals))
  const [x0, x1] = [xTicks[0], xTicks[xTicks.length - 1]]
  const [y0, y1] = [yTicks[0], yTicks[yTicks.length - 1]]
  const sx = (v: number) => PAD.l + ((v - x0) / (x1 - x0 || 1)) * (W - PAD.l - PAD.r)
  const sy = (v: number) => H - PAD.b - ((v - y0) / (y1 - y0 || 1)) * (H - PAD.t - PAD.b)
  const hover = pts.find((p) => p.c.candidate_id === hoverId) ?? null

  const keySelect = (e: KeyboardEvent, id: string) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      onSelect(id)
    }
  }

  return (
    <figure className="s5-chart">
      <figcaption className="s5-cap">
        후보별 일정 변경량과 추가 소음 영향 <span className="muted">· 아래로 갈수록 주민 부담이 적고, 왼쪽일수록 일정을 덜 옮깁니다</span>
      </figcaption>
      <div className="s5-plot">
        <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="후보별 일정 변경량과 추가 소음 영향 산점도">
          {yTicks.map((t) => (
            <g key={`y${t}`}>
              <line x1={PAD.l} x2={W - PAD.r} y1={sy(t)} y2={sy(t)} className="grid" />
              <text x={PAD.l - 8} y={sy(t)} className="tick" textAnchor="end" dominantBaseline="middle">
                {formatNumber(t)}
              </text>
            </g>
          ))}
          {xTicks.map((t) => (
            <text key={`x${t}`} x={sx(t)} y={H - PAD.b + 16} className="tick" textAnchor="middle">
              {t}분
            </text>
          ))}
          <line x1={PAD.l} x2={W - PAD.r} y1={H - PAD.b} y2={H - PAD.b} className="axis" />
          <text x={(PAD.l + W - PAD.r) / 2} y={H - 6} className="axis-title" textAnchor="middle">
            일정 변경량 (작업 시작 이동 합계)
          </text>
          <text x={12} y={(PAD.t + H - PAD.b) / 2} className="axis-title" textAnchor="middle" transform={`rotate(-90 12 ${(PAD.t + H - PAD.b) / 2})`}>
            추가 소음 영향
          </text>

          {pts.map((p) => {
            const id = p.c.candidate_id
            const cx = sx(p.x)
            const cy = sy(p.y)
            const on = id === selectedId
            const can = p.status === 'rec'
            const isOriginal = id === res.original_schedule?.candidate_id
            return (
              <g
                key={id}
                className={`pt ${p.status}${on ? ' on' : ''}`}
                onPointerEnter={() => setHoverId(id)}
                onPointerLeave={() => setHoverId((h) => (h === id ? null : h))}
                onFocus={() => setHoverId(id)}
                onBlur={() => setHoverId((h) => (h === id ? null : h))}
                onClick={can ? () => onSelect(id) : undefined}
                onKeyDown={can ? (e) => keySelect(e, id) : undefined}
                tabIndex={can ? 0 : undefined}
                role={can ? 'button' : undefined}
                aria-pressed={can ? on : undefined}
                aria-label={can ? `${candidateLabel(id)} 선택` : undefined}
              >
                <circle cx={cx} cy={cy} r={12} className="hit" />
                {on && <circle cx={cx} cy={cy} r={10} className="sel-ring" />}
                <circle cx={cx} cy={cy} r={p.status === 'bad' ? 4 : can ? 6 : 5} className="dot" />
                {(can || isOriginal) && (
                  <text x={cx} y={cy - 14} className="pt-label" textAnchor="middle">
                    {isOriginal ? '원 일정' : candidateLabel(id)}
                  </text>
                )}
              </g>
            )
          })}
        </svg>
        {hover && (
          <div
            className="s5-tip"
            style={{ left: `${(sx(hover.x) / W) * 100}%`, top: `${(sy(hover.y) / H) * 100}%` }}
            role="status"
          >
            <b>{candidateLabel(hover.c.candidate_id)}</b>
            <span>{STATUS_LABEL[hover.status]}</span>
            <span>
              <b>{formatNumber(hover.x)}분</b> 일정 변경
            </span>
            <span>
              <b>{formatNumber(hover.y)}</b> 추가 소음 영향
            </span>
            <span>
              <b>{formatNumber(hover.c.noise_impact.existing_noise_overlap_receptor_minutes)}</b> 기존 소음과 겹침
            </span>
          </div>
        )}
      </div>
      <div className="s5-legend">
        {(['rec', 'ok', 'bad'] as const).map((s) => (
          <span key={s}>
            <svg width="14" height="14" aria-hidden="true">
              <circle cx="7" cy="7" r={s === 'bad' ? 4 : 5} className={`legend-dot ${s}`} />
            </svg>
            {STATUS_LABEL[s]}
          </span>
        ))}
      </div>
    </figure>
  )
}
