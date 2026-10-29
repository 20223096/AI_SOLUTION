import { useEffect, useState } from 'react'
import type { ConstructionNotice } from '../api/notices'
import type { ConfirmedPlan } from '../api/planning'
import {
  compareSchedules,
  type CandidateResult,
  type CompareResponse,
  type RecommendationResponse,
} from '../api/recommendations'
import { ScheduleTimeline } from '../components/ScheduleTimeline'
import { errorMessage, isAbort, type Async } from '../utils/async'
import {
  ALL_METRICS,
  HEADLINE_METRICS,
  assignmentTime,
  candidateLabel,
  deltaTone,
  formatDelta,
  formatNumber,
  taskNameMap,
  toTimelineItems,
} from './s4Display'
import './S6Comparison.css'

interface Props {
  res: RecommendationResponse
  candidate: CandidateResult
  notice: ConstructionNotice
  plan: ConfirmedPlan
  onBack: () => void
  onNext: (compare: CompareResponse) => void
}

/** 선택 후보가 바뀌면 부모가 key로 다시 마운트한다. */
export function S6Comparison({ res, candidate, notice, plan, onBack, onNext }: Props) {
  const [state, setState] = useState<Async<CompareResponse>>({ status: 'loading' })
  const [reloadKey, setReloadKey] = useState(0)
  const original = res.original_schedule

  useEffect(() => {
    if (!original) return
    const controller = new AbortController()
    // 가이드 6절: before = original_schedule.assignments, after = 선택 후보 assignments
    compareSchedules(res.scenario_id, original.assignments, candidate.assignments, controller.signal)
      .then((data) => setState({ status: 'success', data }))
      .catch((err) => !isAbort(err) && setState({ status: 'error', message: errorMessage(err) }))
    return () => controller.abort()
  }, [res.scenario_id, original, candidate, reloadKey])

  const taskNames = taskNameMap(notice.tasks)
  const originalBad = new Set(original?.violations.map((v) => v.task_id).filter((id): id is string => !!id))

  return (
    <div className="grid s6">
      <section className="panel span2" aria-live="polite">
        <div className="ph">
          <span className="step">S6</span>
          <h2>조정 전후 비교</h2>
          <span className="tag">원 일정 → {candidateLabel(candidate.candidate_id)}</span>
        </div>
        <p className="sub">같은 수음점과 계산 규칙으로 원 일정과 선택한 조정안을 비교한 시뮬레이션 결과입니다.</p>

        {original ? (
          <ScheduleTimeline
            window={plan.planning.total_work_window}
            lanes={[
              { key: 'before', label: '조정 전', items: toTimelineItems(original.assignments, taskNames, originalBad) },
              { key: 'after', label: '조정 후', tone: 'new', items: toTimelineItems(candidate.assignments, taskNames) },
            ]}
          />
        ) : (
          <div className="hint error">서버 응답에 원 일정이 없어 비교할 수 없습니다.</div>
        )}

        {original &&
          (state.status === 'loading' ? (
            <p className="muted" role="status">
              전후 소음 지표를 비교하는 중…
            </p>
          ) : state.status === 'error' ? (
            <>
              <div className="hint error" role="alert">
                {state.message}
              </div>
              <div className="row">
                <button
                  type="button"
                  className="ghost"
                  onClick={() => {
                    setState({ status: 'loading' })
                    setReloadKey((k) => k + 1)
                  }}
                >
                  다시 비교
                </button>
              </div>
            </>
          ) : (
            <CompareResult data={state.data} taskNames={taskNames} />
          ))}
      </section>

      <section className="panel span2">
        <div className="row">
          <button type="button" className="ghost" onClick={onBack}>
            ← S5로 돌아가기
          </button>
          <button
            type="button"
            disabled={state.status !== 'success'}
            onClick={() => state.status === 'success' && onNext(state.data)}
          >
            다음: 일정 확정·주민 안내 (S7)
          </button>
        </div>
      </section>
    </div>
  )
}

function CompareResult({ data, taskNames }: { data: CompareResponse; taskNames: Map<string, string> }) {
  const details = data.schedule_change_details
  const shifts = details.task_start_shift_minutes as Record<string, number> | undefined
  const beforeEnd = details.before_project_end as string | undefined
  const afterEnd = details.after_project_end as string | undefined
  const basis = data.comparison_basis as { slot_minutes?: number; threshold_db?: number; same_receptors_and_rules?: boolean }
  const deltaOf = (key: (typeof ALL_METRICS)[number]['key']) => data.delta[key] ?? data.after[key] - data.before[key]

  return (
    <>
      <div className="metrics">
        {HEADLINE_METRICS.map((m) => {
          const delta = deltaOf(m.key)
          const changed = data.before[m.key] !== data.after[m.key]
          return (
            <div key={m.key} className="m">
              <div className="l">
                {m.label}
                {m.unit && <span className="muted"> ({m.unit})</span>}
              </div>
              <div className="v">
                {changed && (
                  <>
                    <s>{formatNumber(data.before[m.key])}</s> →{' '}
                  </>
                )}
                {formatNumber(data.after[m.key])}
              </div>
              <div className={`d ${deltaTone(m, delta)}`}>{delta === 0 ? '변화 없음' : formatDelta(delta)}</div>
            </div>
          )
        })}
      </div>

      {shifts && Object.keys(shifts).length > 0 && (
        <>
          <h3>작업별 시작 이동</h3>
          <div className="scroll">
            <table>
              <thead>
                <tr>
                  <th>작업</th>
                  <th>시작 이동</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(shifts).map(([id, min]) => (
                  <tr key={id}>
                    <td>{taskNames.get(id) ?? id}</td>
                    <td>{formatDelta(min)}분</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {beforeEnd && afterEnd && (
            <p className="muted s6-note">
              공사 종료: {assignmentTime(beforeEnd)} → {assignmentTime(afterEnd)}
            </p>
          )}
        </>
      )}

      <details className="s6-details">
        <summary>전체 지표 보기 ({ALL_METRICS.length}개)</summary>
        <div className="scroll">
          <table>
            <thead>
              <tr>
                <th>지표</th>
                <th>조정 전</th>
                <th>조정 후</th>
                <th>변화</th>
              </tr>
            </thead>
            <tbody>
              {ALL_METRICS.map((m) => {
                const delta = deltaOf(m.key)
                return (
                  <tr key={m.key}>
                    <td>
                      {m.label}
                      {m.unit && <span className="muted"> ({m.unit})</span>}
                    </td>
                    <td>{formatNumber(data.before[m.key])}</td>
                    <td>{formatNumber(data.after[m.key])}</td>
                    <td className={deltaTone(m, delta)}>{delta === 0 ? '–' : formatDelta(delta)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </details>

      <p className="muted s6-note">
        비교 기준: {basis.slot_minutes ?? '?'}분 단위, {basis.threshold_db ?? '?'}dB 이상을 고소음으로 계산
        {basis.same_receptors_and_rules ? ', 전후 같은 수음점·규칙 적용' : ''}. 시뮬레이션 결과이며 실측값이 아닙니다.
      </p>
    </>
  )
}
