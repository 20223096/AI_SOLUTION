import { useMemo, useState } from 'react'
import type { ConstructionNotice } from '../api/notices'
import type { ConfirmedPlan } from '../api/planning'
import type { CandidateResult, CompareResponse, RecommendationResponse } from '../api/recommendations'
import {
  confirmResidentNotice,
  createResidentNoticeDraft,
  getResidentNoticeDraft,
  updateResidentNoticeDraft,
  type ResidentNoticeDraft,
  type SelectedNoticeSchedule,
} from '../api/residentNotices'
import { ApiError } from '../api/client'
import { errorMessage } from '../utils/async'
import { assignmentTime, candidateLabel, taskNameMap } from './s4Display'
import { buildFacts, byStartTime, defaultHighNoise, defaultReason } from './s7Notice'
import './S7NoticeDraft.css'

interface Props {
  notice: ConstructionNotice
  plan: ConfirmedPlan
  res: RecommendationResponse
  candidate: CandidateResult
  compare: CompareResponse
  confirmed: boolean
  onConfirm: (draft: ResidentNoticeDraft) => void
  onBack: () => void
  onNext: () => void
}

export function S7NoticeDraft({ notice, plan, res, candidate, compare, confirmed, onConfirm, onBack, onNext }: Props) {
  const facts = useMemo(() => buildFacts(plan, candidate), [plan, candidate])
  const [department, setDepartment] = useState('기후환경과')
  const [contact, setContact] = useState('')
  const [reason, setReason] = useState(() => defaultReason(plan, res, candidate, compare))
  const [highNoise, setHighNoise] = useState<Record<string, boolean>>(() =>
    defaultHighNoise(plan, candidate.assignments.map((a) => a.task_id)),
  )
  const [draft, setDraft] = useState<ResidentNoticeDraft | null>(null)
  const [headline, setHeadline] = useState('')
  const [body, setBody] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [loadedExisting, setLoadedExisting] = useState(false)
  const taskNames = taskNameMap(notice.tasks)
  const assignments = useMemo(() => byStartTime(candidate.assignments), [candidate])
  // 공개 문의처는 "담당 부서 연락처" 한 줄로 서버에 보낸다.
  const publicContact = [department.trim(), contact.trim()].filter(Boolean).join(' ')

  const schedule = (): SelectedNoticeSchedule => ({
    schedule_id: `${plan.planning.notice_id}-${candidate.candidate_id}`,
    schedule_version: candidate.schedule_version ?? '',
    candidate_id: candidate.candidate_id,
    recommendation_source: '/api/prd/recommendations/constraint-filtered',
    candidate_valid: candidate.recommendable && candidate.prd_feasible,
    schedule_snapshot_id: candidate.schedule_snapshot_id,
    assignments: assignments.map((item) => ({
      ...item,
      task_name: taskNames.get(item.task_id) ?? item.task_id,
      high_noise: highNoise[item.task_id] ?? false,
      classification_source: 'user_confirmed',
    })),
  })

  async function createDraft() {
    setBusy(true)
    setMessage('')
    try {
      const data = await createResidentNoticeDraft({
        project_id: plan.planning.notice_id,
        project_name: plan.planning.project_name,
        public_location: plan.planning.location,
        construction_date: res.analysis_date,
        public_window_start: `${res.analysis_date}T${plan.planning.total_work_window.start}:00+09:00`,
        public_window_end: `${res.analysis_date}T${plan.planning.total_work_window.end}:00+09:00`,
        public_contact: publicContact || null,
        schedule: schedule(),
        provenance: [{ field: 'selected_schedule', status: 'user_confirmed', source: 'S5 담당자 선택' }],
        data_classification: 'demo',
      })
      setDraft(data)
      setHeadline(data.headline)
      setBody(`${data.body}\n\n일정 조정 참고: ${reason}`)
    } catch (err) {
      if (!isConflict(err)) {
        setMessage(errorMessage(err))
        return
      }
      // 409: 이 공사의 초안이 서버에 이미 있다(이전 실행에서 저장). 기존 초안을 불러와 이어서 수정·확정한다.
      try {
        const existing = await getResidentNoticeDraft(plan.planning.notice_id)
        setDraft(existing)
        setHeadline(existing.headline)
        setBody(existing.body)
        setLoadedExisting(true)
      } catch (loadErr) {
        setMessage(errorMessage(loadErr))
      }
    } finally {
      setBusy(false)
    }
  }

  async function saveAndConfirm() {
    if (!draft) return
    setBusy(true)
    setMessage('')
    const update = (revision: number) =>
      updateResidentNoticeDraft(plan.planning.notice_id, {
        expected_revision: revision,
        project_name: plan.planning.project_name,
        public_location: plan.planning.location,
        public_contact: publicContact || null,
        headline,
        body,
        schedule: schedule(),
        provenance: [{ field: 'selected_schedule', status: 'user_confirmed', source: 'S5 담당자 선택' }],
      })
    try {
      // 409(다른 탭 등에서 초안 revision이 바뀜): 최신 revision으로 한 번 다시 저장한다. 내용은 이 화면 기준으로 덮어쓴다.
      const updated = await update(draft.revision).catch(async (err: unknown) => {
        if (!isConflict(err)) throw err
        return update((await getResidentNoticeDraft(plan.planning.notice_id)).revision)
      })
      const published = await confirmResidentNotice(plan.planning.notice_id, updated.revision, updated.schedule_version)
      setDraft(published)
      onConfirm(published)
    } catch (err) {
      setMessage(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  const snapshotReady = Boolean(candidate.schedule_snapshot_id && candidate.schedule_version)

  return (
    <div className="grid s7">
      <section className="panel span2">
        <div className="ph"><span className="step">S7</span><h2>일정 확정과 주민 안내</h2><span className="tag">{confirmed ? '서버 확정·공개됨' : '비공개'}</span></div>
        <p className="sub">선택한 {candidateLabel(candidate.candidate_id)}의 서버 snapshot과 version을 검증해 안내문을 저장·확정합니다.</p>
        {!snapshotReady && <div className="hint error">추천 snapshot ID 또는 schedule version이 없어 확정할 수 없습니다. S4부터 다시 진행하세요.</div>}
        <div className="scroll"><table className="s7-facts"><tbody>
          <tr><th>공사명</th><td>{facts.projectName}</td></tr>
          <tr><th>장소</th><td>{facts.location}</td></tr>
          <tr><th>작업 시간</th><td>{assignments.map((a) => <div key={a.task_id}>{assignmentTime(a.start)}–{assignmentTime(a.end)} {taskNames.get(a.task_id) ?? a.task_id}</div>)}</td></tr>
        </tbody></table></div>
        <h3>시끄러운 작업 분류</h3>
        <p className="muted">서버가 추정하지 않습니다. 담당자가 각 작업을 직접 확인하세요.</p>
        {assignments.map((item) => <label className="s2-check" key={item.task_id}><input type="checkbox" checked={highNoise[item.task_id] ?? false} onChange={(e) => setHighNoise((v) => ({ ...v, [item.task_id]: e.target.checked }))} />{taskNames.get(item.task_id) ?? item.task_id}</label>)}
        <div className="s7-inputs">
          <label><span>담당 부서</span><input value={department} onChange={(e) => setDepartment(e.target.value)} /></label>
          <label><span>공개 문의처</span><input value={contact} onChange={(e) => setContact(e.target.value)} placeholder="필수" /></label>
          <label className="wide"><span>일정 조정 참고 문구</span><textarea rows={3} value={reason} onChange={(e) => setReason(e.target.value)} /></label>
        </div>
        <button type="button" disabled={busy || !snapshotReady || !contact.trim() || Boolean(draft)} onClick={createDraft}>{busy ? '처리 중…' : '비공개 초안 서버 저장'}</button>
      </section>

      {draft && <section className="panel span2" aria-live="polite">
        <div className="ph"><h2>서버 안내문 초안</h2><span className="tag">{draft.publication_status === 'published' ? '공개' : '비공개'}</span></div>
        <label>제목<input value={headline} onChange={(e) => setHeadline(e.target.value)} /></label>
        <label>본문<textarea className="s7-draft web" rows={12} value={body} onChange={(e) => setBody(e.target.value)} /></label>
        {draft.missing_fields.length > 0 && <div className="hint warn">확정 전 필수값: {draft.missing_fields.join(', ')}</div>}
        <button type="button" disabled={busy || confirmed || !headline.trim() || !body.trim()} onClick={saveAndConfirm}>{busy ? '처리 중…' : '수정 저장 후 확정·공개'}</button>
      </section>}
      {loadedExisting && !confirmed && <section className="panel span2"><div className="hint warn" role="status">서버에 이미 저장된 초안이 있어 불러왔습니다. 본문의 일정이 지금 고른 조정안과 맞는지 확인한 뒤 확정해 주세요. 확정하면 이 화면의 일정으로 덮어씁니다.</div></section>}
      {message && <section className="panel span2"><div className="hint error" role="alert">{message}</div></section>}
      <section className="panel span2"><div className="row">
        <button type="button" className="ghost" onClick={onBack}>← S6으로 돌아가기</button>
        <button type="button" onClick={onNext} disabled={!confirmed}>다음: 주민 공개 화면 (S8)</button>
      </div></section>
    </div>
  )
}

const isConflict = (err: unknown) => err instanceof ApiError && err.status === 409
