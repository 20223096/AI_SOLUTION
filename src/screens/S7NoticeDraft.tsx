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
  type ResidentPublicNotice,
  type SelectedNoticeSchedule,
} from '../api/residentNotices'
import { ApiError } from '../api/client'
import { errorMessage } from '../utils/async'
import { assignmentTime, candidateLabel, taskNameMap } from './s4Display'
import { buildFacts, buildPreviewNotice, byStartTime, defaultHighNoise, defaultReason } from './s7Notice'
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
  onPreview: (notice: ResidentPublicNotice) => void
  onNext: () => void
}

export function S7NoticeDraft({ notice, plan, res, candidate, compare, confirmed, onConfirm, onPreview, onBack, onNext }: Props) {
  const facts = useMemo(() => buildFacts(plan, candidate), [plan, candidate])
  const [department, setDepartment] = useState('기후환경과')
  const [contact, setContact] = useState('')
  const [staffToken, setStaffToken] = useState('')
  const [mode, setMode] = useState<'preview' | 'staff'>('preview')
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
      }, staffToken)
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
        const existing = await getResidentNoticeDraft(plan.planning.notice_id, staffToken)
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
      }, staffToken)
    try {
      // 409(다른 탭 등에서 초안 revision이 바뀜): 최신 revision으로 한 번 다시 저장한다. 내용은 이 화면 기준으로 덮어쓴다.
      const updated = await update(draft.revision).catch(async (err: unknown) => {
        if (!isConflict(err)) throw err
        return update((await getResidentNoticeDraft(plan.planning.notice_id, staffToken)).revision)
      })
      const published = await confirmResidentNotice(plan.planning.notice_id, updated.revision, updated.schedule_version, staffToken)
      setDraft(published)
      onConfirm(published)
    } catch (err) {
      setMessage(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  const snapshotReady = Boolean(candidate.schedule_snapshot_id && candidate.schedule_version)
  const previewHeadline = headline.trim() || `${facts.projectName} 작업 시간 안내`
  const previewBody = body.trim() || `${facts.location} 공사 일정을 안내합니다.\n\n${reason}`.trim()

  function continuePreview() {
    onPreview(buildPreviewNotice(
      schedule(),
      `${res.analysis_date}T${plan.planning.total_work_window.start}:00+09:00`,
      `${res.analysis_date}T${plan.planning.total_work_window.end}:00+09:00`,
      previewHeadline,
      previewBody,
      publicContact,
    ))
  }

  return (
    <div className="grid s7">
      <section className="panel span2">
        <div className="ph"><span className="step">S7</span><h2>일정 확정과 주민 안내</h2><span className="tag">{confirmed ? '서버 확정·공개됨' : '비공개'}</span></div>
        <p className="sub">선택한 {candidateLabel(candidate.candidate_id)}로 시연 미리보기를 만들거나, 담당자 인증 후 서버에 저장·공개합니다.</p>
        {!snapshotReady && <div className="hint error">추천 snapshot ID 또는 schedule version이 없어 확정할 수 없습니다. S4부터 다시 진행하세요.</div>}
        <fieldset className="s7-mode">
          <legend>진행 방식</legend>
          <label><input type="radio" name="notice-mode" checked={mode === 'preview'} onChange={() => setMode('preview')} /><span><b>시연용 미리보기</b><small>로그인 없이 S8에서 확인 · 서버에 저장하거나 공개하지 않음</small></span></label>
          <label><input type="radio" name="notice-mode" checked={mode === 'staff'} onChange={() => setMode('staff')} /><span><b>담당자 서버 저장·공개</b><small>담당자 토큰 필요 · 실제 공개 API에 반영</small></span></label>
        </fieldset>
        {mode === 'staff' && <div className="s7-auth">
          <label><span>담당자 인증 비밀번호</span><input type="password" value={staffToken} onChange={(e) => setStaffToken(e.target.value)} autoComplete="off" /></label>
          <p className="muted">이 값은 현재 화면의 메모리에만 보관되며 담당자 API 요청에만 사용됩니다.</p>
          {!staffToken && <p className="hint warn" role="status">서버 저장·공개를 하려면 발급받은 담당자 토큰을 입력하세요. 입력 전에는 서버 요청을 보내지 않습니다.</p>}
        </div>}
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
        {mode === 'preview' && <div className="s7-preview-editor">
          <h3>시연 공고문 작성</h3>
          <label>제목<input value={headline} onChange={(e) => setHeadline(e.target.value)} placeholder={previewHeadline} /></label>
          <label>본문<textarea className="s7-draft web" rows={8} value={body} onChange={(e) => setBody(e.target.value)} placeholder={previewBody} /></label>
          <p className="muted">비워 두면 위 일정으로 만든 안전한 예시 문구를 사용합니다.</p>
        </div>}
        {mode === 'preview'
          ? <div className="s7-preview-action"><div className="hint warn">시연용 미리보기 · 서버에 공개되지 않은 내용입니다. 새로고침하면 사라지며, S1의 예시 공고문으로 다시 시작할 수 있습니다.</div><button type="button" disabled={!snapshotReady} onClick={continuePreview}>시연 화면으로 계속하기</button></div>
          : <button type="button" disabled={busy || !snapshotReady || !contact.trim() || !staffToken || Boolean(draft)} onClick={createDraft}>{busy ? '처리 중…' : '비공개 초안 서버 저장'}</button>}
      </section>

      {mode === 'staff' && draft && <section className="panel span2" aria-live="polite">
        <div className="ph"><h2>서버 안내문 초안</h2><span className="tag">{draft.publication_status === 'published' ? '공개' : '비공개'}</span></div>
        <label>제목<input value={headline} onChange={(e) => setHeadline(e.target.value)} /></label>
        <label>본문<textarea className="s7-draft web" rows={12} value={body} onChange={(e) => setBody(e.target.value)} /></label>
        {draft.missing_fields.length > 0 && <div className="hint warn">확정 전 필수값: {draft.missing_fields.join(', ')}</div>}
        <button type="button" disabled={busy || confirmed || !staffToken || !headline.trim() || !body.trim()} onClick={saveAndConfirm}>{busy ? '처리 중…' : '수정 저장 후 확정·공개'}</button>
      </section>}
      {mode === 'staff' && loadedExisting && !confirmed && <section className="panel span2"><div className="hint warn" role="status">서버에 이미 저장된 초안이 있어 불러왔습니다. 본문의 일정이 지금 고른 조정안과 맞는지 확인한 뒤 확정해 주세요. 확정하면 이 화면의 일정으로 덮어씁니다.</div></section>}
      {mode === 'staff' && message && <section className="panel span2"><div className="hint error" role="alert">{message}</div></section>}
      <section className="panel span2"><div className="row">
        <button type="button" className="ghost" onClick={onBack}>← S6으로 돌아가기</button>
        {mode === 'staff' && <button type="button" onClick={onNext} disabled={!confirmed}>실제 공개 결과 보기 (S8)</button>}
      </div></section>
    </div>
  )
}

const isConflict = (err: unknown) => err instanceof ApiError && err.status === 409
