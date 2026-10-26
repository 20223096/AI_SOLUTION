import { hhmm, toMinutes } from '../utils/time'
import './ScheduleTimeline.css'

export interface TimelineItem {
  id: string
  name: string
  start: string // "HH:MM"
  end: string
  bad?: boolean
}

export interface TimelineLane {
  key: string
  label: string
  items: TimelineItem[]
  /** 'new' = 조정 후 일정처럼 강조할 레인 */
  tone?: 'build' | 'new'
}

/** 목업 3번 '시간대별 소음 일정' 스타일의 가로 타임라인. 허용시간은 배경 띠로 표시한다. */
export function ScheduleTimeline({ lanes, window }: { lanes: TimelineLane[]; window: { start: string; end: string } }) {
  const winStart = toMinutes(hhmm(window.start))
  const winEnd = toMinutes(hhmm(window.end))
  const valid = lanes.flatMap((l) => l.items).filter((it) => it.start && it.end && it.start < it.end)
  const times = valid.flatMap((it) => [toMinutes(it.start), toMinutes(it.end)])
  const from = Math.floor(Math.min(winStart, ...times) / 60) * 60
  const to = Math.ceil(Math.max(winEnd, ...times) / 60) * 60
  const span = Math.max(to - from, 60)
  const left = (m: number) => `${((m - from) / span) * 100}%`
  const width = (a: number, b: number) => `${((b - a) / span) * 100}%`
  const hours = Array.from({ length: span / 60 + 1 }, (_, i) => from / 60 + i)
  const hasBad = valid.some((it) => it.bad)
  const hasNew = lanes.some((l) => l.tone === 'new')

  return (
    <div className="scroll">
      <div className="stl" role="img" aria-label="작업 일정 타임라인">
        <div />
        <div className="stl-axis">
          {hours.map((h) => (
            <span key={h} style={{ left: left(h * 60) }}>
              {h}시
            </span>
          ))}
        </div>
        {lanes.map((lane) => (
          <div key={lane.key} className="stl-lane-wrap">
            <div className="stl-label">{lane.label}</div>
            <div className="stl-lane">
              <div className="stl-window" style={{ left: left(winStart), width: width(winStart, winEnd) }} />
              {lane.items
                .filter((it) => it.start && it.end && it.start < it.end)
                .map((it) => (
                  <div
                    key={it.id}
                    className={`stl-ev ${lane.tone ?? 'build'}${it.bad ? ' bad' : ''}`}
                    style={{ left: left(toMinutes(it.start)), width: width(toMinutes(it.start), toMinutes(it.end)) }}
                    title={`${it.name} ${it.start}–${it.end}`}
                  >
                    {it.name}
                  </div>
                ))}
            </div>
          </div>
        ))}
      </div>
      <div className="stl-legend">
        <span>
          <i style={{ background: 'var(--quiet-soft)', border: '1px solid var(--quiet)' }} />
          전체 작업 허용시간
        </span>
        <span>
          <i style={{ background: 'var(--build)' }} />
          작업
        </span>
        {hasNew && (
          <span>
            <i style={{ background: 'var(--new)' }} />
            조정 후 작업
          </span>
        )}
        {hasBad && (
          <span>
            <i style={{ background: 'var(--s4)' }} />
            위반 작업
          </span>
        )}
      </div>
    </div>
  )
}
