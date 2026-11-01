import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { ApiError } from '../api/client'
import { lookupAddressCoordinate, type AddressCoordinateResponse } from '../api/coordinates'
import type { ExtractResponse } from '../api/notices'
import { createPlanningDraft, type ConfirmedPlan, type PlanningDraftResponse } from '../api/planning'
import { Missing } from '../components/Missing'
import { ProvenanceBadge } from '../components/ProvenanceBadge'
import {
  formFromDraft,
  toConfirmedPlan,
  validateForm,
  type EquipmentForm,
  type PlanningForm,
  type TaskForm,
} from './s2Form'
import './S2ExtractionReview.css'

type DraftState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'success'; data: PlanningDraftResponse }

const FIELD_LABEL: Record<string, string> = {
  project_name: '공사명',
  location: '장소',
  construction_period: '공사 기간',
  total_work_window: '전체 작업 허용시간',
  road_excavation: '도로 굴착 여부',
  road_occupancy_permit_window: '도로점용 허가시간',
  equipment_constraints: '장비 제약',
  equipment_required_usage_minutes: '장비 필요 사용시간',
  max_daily_equipment_count: '장비 일 최대 대수',
  same_day_restoration_required: '당일 복구 여부',
}

const WARNING_KO: Record<string, string> = {
  'Extraction output is an unconfirmed draft and is not an official filing fact.':
    '추출 결과는 확인되지 않은 초안이며 공식 신고 사실이 아닙니다.',
  'Null and missing values must be confirmed by a user; no constraint was inferred.':
    '비어 있는 값은 사용자가 직접 확인해야 하며, 서버는 어떤 제약도 추정하지 않았습니다.',
}

interface Props {
  extraction: ExtractResponse
  onBack: () => void
  onConfirm: (plan: ConfirmedPlan) => void
}

/** extraction이 바뀌면 부모가 key로 다시 마운트한다. */
export function S2ExtractionReview({ extraction, onBack, onConfirm }: Props) {
  const [draftState, setDraftState] = useState<DraftState>({ status: 'loading' })
  const [form, setForm] = useState<PlanningForm | null>(null)
  const [showErrors, setShowErrors] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)
  const [coordinate, setCoordinate] = useState<AddressCoordinateResponse | null>(null)
  const [coordinateLoading, setCoordinateLoading] = useState(false)
  const [coordinateError, setCoordinateError] = useState('')
  const [coordinateConfirmed, setCoordinateConfirmed] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    createPlanningDraft(extraction, controller.signal)
      .then((data) => {
        setDraftState({ status: 'success', data })
        setForm(formFromDraft(data.planning_draft, extraction.notice.tasks))
      })
      .catch((err) => {
        if (err instanceof DOMException && err.name === 'AbortError') return
        const message = err instanceof ApiError ? err.message : '알 수 없는 오류가 발생했습니다.'
        setDraftState({ status: 'error', message })
      })
    return () => controller.abort()
  }, [extraction, reloadKey])

  const issues = useMemo(() => (form ? validateForm(form) : []), [form])

  if (draftState.status === 'loading') {
    return (
      <section className="panel">
        <S2Heading />
        <p className="muted" role="status">
          추출 결과를 계획 초안으로 변환하는 중…
        </p>
      </section>
    )
  }

  if (draftState.status === 'error') {
    return (
      <section className="panel">
        <S2Heading />
        <div className="hint error" role="alert">
          {draftState.message}
        </div>
        <div className="row">
          <button
            type="button"
            onClick={() => {
              setDraftState({ status: 'loading' })
              setReloadKey((k) => k + 1)
            }}
          >
            다시 시도
          </button>
          <button type="button" className="ghost" onClick={onBack}>
            ← S1로 돌아가기
          </button>
        </div>
      </section>
    )
  }

  if (!form) return null

  const { data } = draftState
  const draft = data.planning_draft
  const missing = new Set(data.missing_fields)
  const toConfirm = new Set(data.confirmation_required_fields)
  const invalid = new Set(showErrors ? issues.map((i) => i.key) : [])

  const set = <K extends keyof PlanningForm>(key: K, value: PlanningForm[K]) =>
    setForm((f) => {
      if (key === 'location') {
        setCoordinate(null)
        setCoordinateConfirmed(false)
        setCoordinateError('')
      }
      return f ? { ...f, [key]: value } : f
    })
  const setEquipment = (i: number, patch: Partial<EquipmentForm>) =>
    setForm((f) => (f ? { ...f, equipment: f.equipment.map((e, j) => (j === i ? { ...e, ...patch } : e)) } : f))
  const setTask = (i: number, patch: Partial<TaskForm>) =>
    setForm((f) => (f ? { ...f, tasks: f.tasks.map((t, j) => (j === i ? { ...t, ...patch } : t)) } : f))

  /** 필드 옆에 서버가 알려준 상태(미확인/확인 필요)를 표시한다. */
  const fieldTag = (apiField: string) =>
    missing.has(apiField) ? <Missing /> : toConfirm.has(apiField) ? <span className="confirm-tag">확인 필요</span> : null

  function confirm() {
    if (!form) return
    // 공식 주소 좌표 조회는 선택 사항이다. 확정된 계획에는 좌표가 들어가지 않는다.
    if (issues.length > 0) {
      setShowErrors(true)
      return
    }
    onConfirm(toConfirmedPlan(form, draft))
  }

  async function lookupCoordinate(selectedAddressId?: string) {
    if (!form) return
    const address = form.location
    setCoordinateLoading(true)
    setCoordinateError('')
    setCoordinateConfirmed(false)
    try {
      setCoordinate(await lookupAddressCoordinate(address, selectedAddressId))
    } catch (err) {
      setCoordinateError(err instanceof ApiError ? err.message : '주소 좌표를 조회하지 못했습니다.')
    } finally {
      setCoordinateLoading(false)
    }
  }

  return (
    <div className="grid s2">
      <section className="panel span2">
        <S2Heading
          tag={data.status === 'needs_confirmation' ? '확인 필요' : '확인 대기'}
          extractor={data.extractor_mode === 'llm' ? 'AI 추출' : data.extractor_mode === 'mock' ? '규칙 기반 추출' : '수동 입력'}
        />
        <p className="sub">
          추출된 값은 확정값이 아닙니다. 비어 있거나 확인이 필요한 항목을 채운 뒤 계획을 확정해 주세요.
        </p>
        {data.warnings.length > 0 && (
          <div className="hint warn">
            {data.warnings.map((w) => (
              <div key={w}>{WARNING_KO[w] ?? w}</div>
            ))}
          </div>
        )}
        {data.missing_fields.length > 0 && (
          <div className="s2-missing">
            <span className="muted">추출되지 않은 항목</span>
            {data.missing_fields.map((f) => (
              <span key={f} className="missing">
                {FIELD_LABEL[f] ?? f}
              </span>
            ))}
          </div>
        )}
      </section>

      {/* 공사 기본 정보 */}
      <section className="panel span2">
        <div className="ph">
          <h2>공사 기본 정보</h2>
        </div>
        <div className="s2-fields">
          <Field label="공사명" tag={fieldTag('project_name')} htmlFor="s2-name">
            <input
              id="s2-name"
              value={form.project_name}
              onChange={(e) => set('project_name', e.target.value)}
              aria-invalid={invalid.has('project_name')}
            />
          </Field>
          <Field label="장소" tag={fieldTag('location')} htmlFor="s2-location">
            <input
              id="s2-location"
              value={form.location}
              onChange={(e) => set('location', e.target.value)}
              aria-invalid={invalid.has('location')}
            />
            <div className="row">
              <button type="button" className="ghost" disabled={coordinateLoading || form.location.trim().length < 2} onClick={() => lookupCoordinate()}>
                {coordinateLoading ? '공식 주소 조회 중…' : '공식 주소·좌표 조회'}
              </button>
              <span className="muted">선택 사항 · 조회하지 않아도 다음 단계로 넘어갈 수 있습니다.</span>
            </div>
            {coordinateError && <div className="hint error" role="alert">{coordinateError}</div>}
            {coordinate?.status === 'selection_required' && (
              <div className="hint warn">
                <b>주소 후보를 선택해 주세요. 첫 후보는 자동 선택하지 않습니다.</b>
                {(coordinate.candidates ?? []).map((candidate) => (
                  <button key={candidate.address_id} type="button" className="ghost" onClick={() => lookupCoordinate(candidate.address_id)}>
                    {candidate.road_address}{candidate.building_name ? ` · ${candidate.building_name}` : ''}
                  </button>
                ))}
              </div>
            )}
            {coordinate && coordinate.status !== 'resolved' && coordinate.status !== 'selection_required' && (
              <div className="hint error" role="alert">좌표 조회 실패: {coordinate.failure_reason ?? coordinate.status}</div>
            )}
            {coordinate?.status === 'resolved' && coordinate.map_coordinate && (
              <div className="hint">
                <b>{coordinate.normalized_official_address}</b><br />
                주소 대표점: {coordinate.map_coordinate.latitude.toFixed(6)}, {coordinate.map_coordinate.longitude.toFixed(6)}
                <div className="muted">{coordinate.limitation}</div>
                <label className="s2-check">
                  <input type="checkbox" checked={coordinateConfirmed} onChange={(e) => setCoordinateConfirmed(e.target.checked)} />
                  공식 주소 대표점을 확인했습니다
                </label>
              </div>
            )}
          </Field>
          <Field
            label="공사 기간"
            tag={fieldTag('construction_period')}
            hint={form.period_raw ? `원문: “${form.period_raw}”` : undefined}
          >
            <div className="s2-range">
              <input
                type="date"
                aria-label="공사 시작일"
                value={form.period_start}
                onChange={(e) => set('period_start', e.target.value)}
                aria-invalid={invalid.has('construction_period')}
              />
              <span>~</span>
              <input
                type="date"
                aria-label="공사 종료일"
                value={form.period_end}
                onChange={(e) => set('period_end', e.target.value)}
                aria-invalid={invalid.has('construction_period')}
              />
            </div>
          </Field>
          <Field label="전체 작업 허용시간" tag={fieldTag('total_work_window')}>
            <TimeRange
              label="전체 작업 허용시간"
              start={form.work_start}
              end={form.work_end}
              onChange={(s, e) => setForm((f) => (f ? { ...f, work_start: s, work_end: e } : f))}
              invalid={invalid.has('total_work_window')}
            />
          </Field>
          <Field label="도로 굴착 여부" tag={fieldTag('road_excavation')}>
            <div className={`seg${invalid.has('road_excavation') ? ' invalid' : ''}`} role="group" aria-label="도로 굴착 여부">
              {(['yes', 'no'] as const).map((v) => (
                <button
                  key={v}
                  type="button"
                  aria-pressed={form.road_excavation === v}
                  onClick={() => set('road_excavation', v)}
                >
                  {v === 'yes' ? '굴착함' : '굴착 안 함'}
                </button>
              ))}
            </div>
          </Field>
          <Field label="도로점용 허가시간" tag={fieldTag('road_occupancy_permit_window')}>
            <label className="s2-check">
              <input
                type="checkbox"
                checked={form.has_permit_window}
                onChange={(e) => set('has_permit_window', e.target.checked)}
              />
              허가시간 제한 있음
            </label>
            {form.has_permit_window && (
              <TimeRange
                label="도로점용 허가시간"
                start={form.permit_start}
                end={form.permit_end}
                onChange={(s, e) => setForm((f) => (f ? { ...f, permit_start: s, permit_end: e } : f))}
                invalid={invalid.has('road_occupancy_permit_window')}
              />
            )}
          </Field>
          <Field label="계획 완료일" hint="선택 항목" htmlFor="s2-completion">
            <input
              id="s2-completion"
              type="date"
              value={form.completion_date}
              onChange={(e) => set('completion_date', e.target.value)}
              aria-invalid={invalid.has('project_completion_date')}
            />
          </Field>
          <Field label="당일 복구" hint="굴착 후 당일 복구가 필요하면 아래 작업 표에서 복구 작업을 지정합니다.">
            <label className="s2-check">
              <input
                type="checkbox"
                checked={form.same_day_restoration}
                onChange={(e) => set('same_day_restoration', e.target.checked)}
              />
              당일 복구 필요
            </label>
          </Field>
          <Field label="조정 불가 조건" hint="한 줄에 하나씩 · 선택 항목" htmlFor="s2-nonadj" wide>
            <textarea
              id="s2-nonadj"
              rows={3}
              value={form.non_adjustable}
              onChange={(e) => set('non_adjustable', e.target.value)}
              placeholder="예: 14시 이전 작업 시작 불가 (자재 반입 일정)"
            />
          </Field>
        </div>
      </section>

      {/* 장비 제약 */}
      <section className="panel span2">
        <div className="ph">
          <h2>장비 제약</h2>
          {fieldTag('equipment_constraints')}
        </div>
        {form.equipment.length === 0 ? (
          <p className="muted">추출된 장비가 없습니다. 장비 제약 없이 계획을 확정합니다.</p>
        ) : (
          <div className="scroll">
            <table className="s2-table">
              <thead>
                <tr>
                  <th>장비 ID</th>
                  <th>종류</th>
                  <th>
                    필요 사용시간(분) {fieldTag('equipment_required_usage_minutes')}
                  </th>
                  <th>일 최대 대수 {fieldTag('max_daily_equipment_count')}</th>
                  <th>장비 허용시간</th>
                  <th>규격 / 모델</th>
                  <th>출처</th>
                </tr>
              </thead>
              <tbody>
                {form.equipment.map((e, i) => (
                  <tr key={e.equipment_id}>
                    <td>
                      <code>{e.equipment_id}</code>
                    </td>
                    <td>
                      <input
                        aria-label={`${e.equipment_id} 종류`}
                        value={e.category}
                        onChange={(ev) => setEquipment(i, { category: ev.target.value })}
                        aria-invalid={invalid.has(`equipment.${i}.category`)}
                      />
                    </td>
                    <td>
                      <input
                        className="num"
                        inputMode="numeric"
                        aria-label={`${e.equipment_id} 필요 사용시간(분)`}
                        value={e.required_usage_minutes}
                        onChange={(ev) => setEquipment(i, { required_usage_minutes: ev.target.value })}
                        aria-invalid={invalid.has(`equipment.${i}.required_usage_minutes`)}
                      />
                    </td>
                    <td>
                      <input
                        className="num"
                        inputMode="numeric"
                        placeholder="제한 없음"
                        aria-label={`${e.equipment_id} 일 최대 대수`}
                        value={e.max_daily_count}
                        onChange={(ev) => setEquipment(i, { max_daily_count: ev.target.value })}
                        aria-invalid={invalid.has(`equipment.${i}.max_daily_count`)}
                      />
                    </td>
                    <td>
                      <TimeRange
                        label={`${e.equipment_id} 허용시간`}
                        start={e.window_start}
                        end={e.window_end}
                        onChange={(s, en) => setEquipment(i, { window_start: s, window_end: en })}
                        invalid={invalid.has(`equipment.${i}.window`)}
                      />
                    </td>
                    <td>
                      <div className="s2-stack">
                        <input
                          placeholder="규격"
                          aria-label={`${e.equipment_id} 규격`}
                          value={e.specification}
                          onChange={(ev) => setEquipment(i, { specification: ev.target.value })}
                        />
                        <input
                          placeholder="모델명"
                          aria-label={`${e.equipment_id} 모델명`}
                          value={e.model_name}
                          onChange={(ev) => setEquipment(i, { model_name: ev.target.value })}
                        />
                      </div>
                    </td>
                    <td>
                      <ProvenanceBadge status={draft.equipment_constraints[i]?.source_metadata.status ?? 'missing'} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="muted s2-note">장비 허용시간을 비우면 전체 작업 허용시간만 적용됩니다.</p>
      </section>

      {/* 작업 매핑 */}
      <section className="panel span2">
        <div className="ph">
          <h2>작업별 장비 배정</h2>
        </div>
        {form.tasks.length === 0 ? (
          <p className="muted">추출된 작업이 없습니다. S1에서 공고문을 보완해 다시 정리해 주세요.</p>
        ) : (
          <div className="scroll">
            <table className="s2-table">
              <thead>
                <tr>
                  <th>작업</th>
                  <th>선행 작업</th>
                  <th>사용 장비</th>
                  <th>투입 대수</th>
                  {form.same_day_restoration && <th>복구 작업</th>}
                </tr>
              </thead>
              <tbody>
                {form.tasks.map((t, i) => (
                  <tr key={t.id}>
                    <td>
                      {t.name} <span className="muted">({t.id})</span>
                    </td>
                    <td>{draft.predecessors[t.id]?.join(', ') || '–'}</td>
                    <td>
                      <select
                        aria-label={`${t.name} 사용 장비`}
                        value={t.equipment_id}
                        onChange={(ev) => setTask(i, { equipment_id: ev.target.value })}
                      >
                        <option value="">장비 없음</option>
                        {form.equipment.map((e) => (
                          <option key={e.equipment_id} value={e.equipment_id}>
                            {e.equipment_id}
                            {e.category ? ` · ${e.category}` : ''}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td>
                      <input
                        className="num"
                        inputMode="numeric"
                        aria-label={`${t.name} 투입 대수`}
                        value={t.count}
                        disabled={!t.equipment_id}
                        onChange={(ev) => setTask(i, { count: ev.target.value })}
                        aria-invalid={invalid.has(`tasks.${i}.count`)}
                      />
                    </td>
                    {form.same_day_restoration && (
                      <td>
                        <input
                          type="checkbox"
                          aria-label={`${t.name}을 복구 작업으로 지정`}
                          checked={t.restoration}
                          onChange={(ev) => setTask(i, { restoration: ev.target.checked })}
                        />
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="panel span2">
        {showErrors && issues.length > 0 && (
          <div className="hint error" role="alert">
            <b>확정하기 전에 입력값을 확인해 주세요.</b>
            <ul className="s2-issues">
              {issues.map((i) => (
                <li key={i.key + i.message}>{i.message}</li>
              ))}
            </ul>
          </div>
        )}
        <div className="row">
          <button type="button" className="ghost" onClick={onBack}>
            ← S1로 돌아가기
          </button>
          <button type="button" onClick={confirm}>
            계획 확정하고 제약 확인 (S3)
          </button>
          {!showErrors && issues.length > 0 && <span className="muted">입력 항목 확인이 필요합니다.</span>}
          {issues.length === 0 && !coordinateConfirmed && <span className="muted">공식 주소 좌표는 확인하지 않았습니다(선택 사항).</span>}
        </div>
      </section>
    </div>
  )
}

function S2Heading({ tag, extractor }: { tag?: string; extractor?: string }) {
  return (
    <div className="ph">
      <span className="step">S2</span>
      <h2>추출 확인</h2>
      {extractor && <span className="muted s2-extractor">{extractor}</span>}
      {tag && <span className="tag">{tag}</span>}
    </div>
  )
}

function Field({
  label,
  tag,
  hint,
  htmlFor,
  wide,
  children,
}: {
  label: string
  tag?: ReactNode
  hint?: string
  htmlFor?: string
  wide?: boolean
  children: ReactNode
}) {
  return (
    <div className={`s2-field${wide ? ' wide' : ''}`}>
      <div className="s2-label">
        {htmlFor ? <label htmlFor={htmlFor}>{label}</label> : <span>{label}</span>}
        {tag}
      </div>
      {children}
      {hint && <div className="s2-hint muted">{hint}</div>}
    </div>
  )
}

function TimeRange({
  label,
  start,
  end,
  onChange,
  invalid,
}: {
  label: string
  start: string
  end: string
  onChange: (start: string, end: string) => void
  invalid?: boolean
}) {
  return (
    <div className="s2-range">
      <input
        type="time"
        aria-label={`${label} 시작`}
        value={start}
        onChange={(e) => onChange(e.target.value, end)}
        aria-invalid={invalid}
      />
      <span>–</span>
      <input
        type="time"
        aria-label={`${label} 종료`}
        value={end}
        onChange={(e) => onChange(start, e.target.value)}
        aria-invalid={invalid}
      />
    </div>
  )
}
