import type { ConstructionNotice } from '../api/notices'
import type { ConfirmedPlan } from '../api/planning'
import type { CandidateResult } from '../api/recommendations'
import { ANALYSIS_DATE } from '../api/schedules'
import { hhmm } from '../utils/time'
import { formatKoreanDate } from './s7Notice'
import { summarizeDay } from './s8Quiet'
import './S8ResidentView.css'

interface Props {
  notice: ConstructionNotice
  plan: ConfirmedPlan
  candidate: CandidateResult
  onBack: () => void
}

const durationLabel = (min: number) => {
  const h = Math.floor(min / 60)
  const m = min % 60
  return [h && `${h}시간`, m && `${m}분`].filter(Boolean).join(' ')
}

export function S8ResidentView({ notice, plan, candidate, onBack }: Props) {
  const p = plan.planning
  const names = new Map(notice.tasks.map((t) => [t.id, t.name]))
  const { longest, items } = summarizeDay(candidate.assignments, names, p.total_work_window)

  return (
    <div className="grid s8">
      <section className="panel span2">
        <div className="ph">
          <span className="step">S8</span>
          <h2>주민 화면: 오늘의 조용한 시간</h2>
          <span className="tag">주민용 미리보기</span>
        </div>
        <p className="sub">
          주민이 휴대폰으로 우리 동네 오늘 공사 일정을 확인하는 화면입니다. 주민 공개 API는 아직 없어 확정 일정으로 만든 미리보기입니다.
        </p>

        <div className="phone">
          <div className="ph-top">
            {p.location} · {formatKoreanDate(ANALYSIS_DATE)}
          </div>

          <div className="qcard">
            <div className="ql">
              작업 시간({hhmm(p.total_work_window.start)}–{hhmm(p.total_work_window.end)}) 중 가장 긴 조용한 시간
            </div>
            {longest ? (
              <>
                <div className="qt">
                  {longest.start} – {longest.end}
                </div>
                <div className="qd">{durationLabel(longest.minutes)} 동안 이 공사의 작업이 없어요</div>
              </>
            ) : (
              <>
                <div className="qt">{hhmm(p.total_work_window.end)} 이후</div>
                <div className="qd">작업 시간 중에는 쉬는 시간 없이 공사가 이어져요</div>
              </>
            )}
          </div>

          <ul className="day">
            {items.map((it) =>
              it.kind === 'work' ? (
                <li key={`w-${it.start}-${it.name}`}>
                  <span className="dt">
                    {it.start}–{it.end}
                  </span>
                  <span className="dot build" aria-hidden="true" />
                  {it.name}
                </li>
              ) : (
                <li key={`q-${it.start}`} className="q">
                  <span className="dt">{it.end ? `${it.start}–${it.end}` : `${it.start}~`}</span>
                  <span className="dot qq" aria-hidden="true" />
                  {it.end ? '조용한 시간' : '공사 없음'}
                </li>
              ),
            )}
          </ul>

          <p className="ph-note">{p.project_name} 기준이며 교통 등 다른 소음은 포함하지 않아요.</p>
        </div>
      </section>

      <section className="panel span2">
        <div className="row">
          <button type="button" className="ghost" onClick={onBack}>
            ← S7로 돌아가기
          </button>
        </div>
      </section>
    </div>
  )
}
