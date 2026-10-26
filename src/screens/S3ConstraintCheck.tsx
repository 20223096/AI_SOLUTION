import { useEffect, useMemo, useRef, useState } from 'react'
import { ApiError } from '../api/client'
import type { ConstructionNotice } from '../api/notices'
import type { ConfirmedPlan } from '../api/planning'
import {
  ANALYSIS_DATE,
  validateSchedule,
  type ScheduleValidationResponse,
  type TaskAssignment,
} from '../api/schedules'
import { Missing } from '../components/Missing'
import { ScheduleTimeline } from '../components/ScheduleTimeline'
import { hhmm, toMinutes } from '../utils/time'
import {
  buildOriginalSchedule,
  scheduleIssues,
  toAssignments,
  violationDetails,
  violationMessage,
  type ScheduleRow,
} from './s3Schedule'
import './S3ConstraintCheck.css'

type ValidateState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'success'; data: ScheduleValidationResponse; rowsKey: string }

export interface S3Result {
  assignments: TaskAssignment[]
  validation: ScheduleValidationResponse
}

interface Props {
  notice: ConstructionNotice
  plan: ConfirmedPlan
  onBack: () => void
  onNext: (result: S3Result) => void
}

const rowsKeyOf = (rows: ScheduleRow[]) => rows.map((r) => `${r.task_id}@${r.start}-${r.end}`).join('|')

/** plan이 바뀌면 부모가 key로 다시 마운트한다. */
export function S3ConstraintCheck({ notice, plan, onBack, onNext }: Props) {
  const original = useMemo(() => buildOriginalSchedule(notice, plan), [notice, plan])
  const [rows, setRows] = useState<ScheduleRow[]>(original)
  const [state, setState] = useState<ValidateState>({ status: 'idle' })
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => () => abortRef.current?.abort(), [])

  const issues = scheduleIssues(rows)
  const rowsKey = rowsKeyOf(rows)
  const loading = state.status === 'loading'
  const result = state.status === 'success' ? state : null
  const stale = result != null && result.rowsKey !== rowsKey
  const fresh = result != null && !stale ? result.data : null
  const taskNames = new Map(rows.map((r) => [r.task_id, r.name]))
  const badTasks = new Set(fresh?.violations.map((v) => v.task_id).filter((id): id is string => !!id))

  const p = plan.planning
  const periodStart = p.construction_period.start
  const periodEnd = p.construction_period.end
  const dateOutsidePeriod =
    periodStart != null && periodEnd != null && (ANALYSIS_DATE < periodStart || ANALYSIS_DATE > periodEnd)

  const setRow = (i: number, patch: Partial<ScheduleRow>) =>
    setRows((rs) => rs.map((r, j) => (j === i ? { ...r, ...patch } : r)))

  async function validate() {
    if (issues.length > 0 || loading) return
    const controller = new AbortController()
    abortRef.current = controller
    const key = rowsKey
    setState({ status: 'loading' })
    try {
      const data = await validateSchedule(plan, toAssignments(rows), controller.signal)
      setState({ status: 'success', data, rowsKey: key })
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        setState({ status: 'idle' })
        return
      }
      setState({ status: 'error', message: err instanceof ApiError ? err.message : '알 수 없는 오류가 발생했습니다.' })
    } finally {
      if (abortRef.current === controller) abortRef.current = null
    }
  }

  return (
    <div className="grid s3">
      <section className="panel span2">
        <div className="ph">
          <span className="step">S3</span>
          <h2>제약 확인</h2>
          <span className="tag">분석일 {ANALYSIS_DATE} (고정)</span>
        </div>
        <p className="sub">
          확정한 계획의 제약으로 신고서 원 일정을 검증합니다. 결과는 법적 판정이 아니라 입력 계획과 명시 제약의 불일치 안내입니다.
        </p>

        <h3>확정한 제약</h3>
        <div className="scroll">
          <table>
            <tbody>
              <tr>
                <th>공사 기간</th>
                <td>
                  {periodStart ?? '?'} ~ {periodEnd ?? '?'}
                </td>
              </tr>
              <tr>
                <th>전체 작업 허용시간</th>
                <td>
                  {hhmm(p.total_work_window.start)} – {hhmm(p.total_work_window.end)}
                </td>
              </tr>
              <tr>
                <th>도로점용 허가시간</th>
                <td>
                  {p.road_occupancy_permit_window ? (
                    `${hhmm(p.road_occupancy_permit_window.start)} – ${hhmm(p.road_occupancy_permit_window.end)}`
                  ) : (
                    <span className="muted">제한 없음</span>
                  )}
                </td>
              </tr>
              {p.equipment_constraints?.map((e) => (
                <tr key={e.equipment_id}>
                  <th>
                    장비 {e.equipment_id} <span className="muted">· {e.category}</span>
                  </th>
                  <td>
                    필요 {e.required_usage_minutes}분
                    {e.max_daily_count != null && ` · 일 최대 ${e.max_daily_count}대`}
                    {e.permitted_time_windows?.length
                      ? ` · 허용 ${e.permitted_time_windows.map((w) => `${hhmm(w.start)}–${hhmm(w.end)}`).join(', ')}`
                      : ''}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {dateOutsidePeriod && (
          <div className="hint warn">
            분석일 {ANALYSIS_DATE}이 확정한 공사 기간 밖입니다. 검증 시 공사기간 위반으로 표시됩니다.
          </div>
        )}
      </section>

      <section className="panel span2">
        <div className="ph">
          <h2>검증할 일정</h2>
          <span className="tag">원 일정 기준 · 수정 가능</span>
        </div>
        <p className="sub">공고문 작업 시작시각부터 선행 순서대로 이어 붙인 원 일정입니다. 시각을 바꿔 다시 검증할 수 있습니다.</p>

        <ScheduleTimeline
          window={p.total_work_window}
          lanes={rows.map((r) => ({
            key: r.task_id,
            label: r.name,
            items: [{ id: r.task_id, name: r.name, start: r.start, end: r.end, bad: badTasks.has(r.task_id) }],
          }))}
        />

        <div className="scroll">
          <table className="s3-table">
            <thead>
              <tr>
                <th>작업</th>
                <th>장비</th>
                <th>시작</th>
                <th>종료</th>
                <th>소요</th>
                {fresh && <th>검증</th>}
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => {
                const minutes = r.start && r.end && r.start < r.end ? toMinutes(r.end) - toMinutes(r.start) : null
                return (
                  <tr key={r.task_id} className={badTasks.has(r.task_id) ? 'bad-row' : undefined}>
                    <td>
                      {r.name} <span className="muted">({r.task_id})</span>
                    </td>
                    <td>{plan.equipment_by_task[r.task_id] ?? <span className="muted">–</span>}</td>
                    <td>
                      <input
                        type="time"
                        aria-label={`${r.name} 시작`}
                        value={r.start}
                        onChange={(e) => setRow(i, { start: e.target.value })}
                        disabled={loading}
                      />
                    </td>
                    <td>
                      <input
                        type="time"
                        aria-label={`${r.name} 종료`}
                        value={r.end}
                        onChange={(e) => setRow(i, { end: e.target.value })}
                        disabled={loading}
                      />
                    </td>
                    <td>{minutes != null ? `${minutes}분` : <Missing label="–" />}</td>
                    {fresh && <td>{badTasks.has(r.task_id) ? <b className="bad">위반</b> : <span className="good">통과</span>}</td>}
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>

        {issues.length > 0 && (
          <div className="hint warn">
            {issues.map((m) => (
              <div key={m}>{m}</div>
            ))}
          </div>
        )}

        <div className="row">
          <button type="button" onClick={validate} disabled={issues.length > 0 || loading}>
            {loading ? '검증하는 중…' : result ? '다시 검증하기' : '일정 검증하기'}
          </button>
          {loading && (
            <button type="button" className="ghost" onClick={() => abortRef.current?.abort()}>
              취소
            </button>
          )}
          {!loading && rowsKey !== rowsKeyOf(original) && (
            <button type="button" className="ghost" onClick={() => setRows(original)}>
              원 일정으로 되돌리기
            </button>
          )}
        </div>
      </section>

      {state.status === 'error' && (
        <section className="panel span2">
          <div className="hint error" role="alert">
            {state.message}
          </div>
          <div className="row">
            <button type="button" className="ghost" onClick={validate} disabled={issues.length > 0}>
              다시 시도
            </button>
          </div>
        </section>
      )}

      {result && (
        <section className={`panel span2${stale ? ' stale' : ''}`} aria-live="polite">
          <div className="ph">
            <h2>검증 결과</h2>
            <span className="tag">{result.data.policy_version}</span>
          </div>

          {stale && <div className="hint warn">일정이 바뀌었습니다. 다시 검증해야 다음 단계로 넘어갈 수 있습니다.</div>}

          {result.data.feasible ? (
            <div className="s3-verdict ok">
              <b>모든 제약을 통과했습니다.</b>
              <span>이 일정은 확정한 계획의 제약과 충돌하지 않습니다.</span>
            </div>
          ) : (
            <>
              <div className="s3-verdict fail">
                <b>제약 위반 {result.data.violations.length}건</b>
                <span>아래 사유를 확인하세요. 원 일정이 맞지 않으면 S4에서 제약을 지키는 대안 일정을 찾을 수 있습니다.</span>
              </div>
              <ul className="s3-violations">
                {result.data.violations.map((v, i) => (
                  <li key={`${v.code}-${v.task_id}-${v.equipment_id}-${i}`}>
                    <b>{violationMessage(v)}</b>
                    <span className="muted">{violationDetails(v, taskNames).join(' · ')}</span>
                    <code>{v.code}</code>
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>
      )}

      <section className="panel span2">
        <div className="row">
          <button type="button" className="ghost" onClick={onBack}>
            ← S2로 돌아가기
          </button>
          <button
            type="button"
            className={fresh && !fresh.feasible ? 'ghost' : undefined}
            disabled={!fresh}
            onClick={() => fresh && onNext({ assignments: toAssignments(rows), validation: fresh })}
          >
            {fresh && !fresh.feasible ? '대안 일정 찾기 (S4)' : '다음: 후보 추천 (S4)'}
          </button>
          {!fresh && <span className="muted">일정을 검증해야 S4로 넘어갈 수 있습니다.</span>}
        </div>
      </section>
    </div>
  )
}
