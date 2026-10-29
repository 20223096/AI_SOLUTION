import { useEffect, useState } from 'react'
import { getPublicResidentNotice, type ResidentPublicResponse } from '../api/residentNotices'
import { errorMessage, isAbort, type Async } from '../utils/async'
import { assignmentTime } from './s4Display'
import { byStartTime } from './s7Notice'
import './S8ResidentView.css'

interface Props { projectId: string; location: string; onBack: () => void }

export function S8ResidentView({ projectId, location, onBack }: Props) {
  const [state, setState] = useState<Async<ResidentPublicResponse>>({ status: 'loading' })
  useEffect(() => {
    const controller = new AbortController()
    getPublicResidentNotice(projectId, controller.signal)
      .then((data) => setState({ status: 'success', data }))
      .catch((err) => !isAbort(err) && setState({ status: 'error', message: errorMessage(err) }))
    return () => controller.abort()
  }, [projectId])

  const published = state.status === 'success' && state.data.status === 'published' ? state.data.notice : null
  return <div className="grid s8">
    <section className="panel span2">
      <div className="ph"><span className="step">S8</span><h2>주민 공개 화면</h2><span className="tag">공개 API 조회 결과</span></div>
      {state.status === 'loading' && <p role="status">확정 안내를 조회하는 중…</p>}
      {state.status === 'error' && <div className="hint error" role="alert">{state.message}</div>}
      {state.status === 'success' && state.data.status === 'not_published' && <div className="hint warn">확정된 주민 안내가 없습니다.</div>}
      {published && <div className="phone">
        <div className="ph-top">{location}</div>
        <div className="qcard">
          <div className="ql">오늘 이 공사가 쉬어가는 시간</div>
          <div className="qt">{published.longest_quiet_interval ? `${assignmentTime(published.longest_quiet_interval.start)} – ${assignmentTime(published.longest_quiet_interval.end)}` : '없음'}</div>
          <div className="qs">이 공사 기준이에요</div>
          <div className="qd">{published.quiet_interval_limitation}</div>
        </div>
        <h3>오늘 일정</h3>
        <ul className="day">{byStartTime(published.today_schedule).map((item) => <li key={`${item.start}-${item.task_name}`}><span className="dt">{assignmentTime(item.start)}–{assignmentTime(item.end)}</span><span className="dot build" aria-hidden="true" />{item.task_name}</li>)}</ul>
        <h3>시간대별 작업 상태</h3>
        <ul className="day">{byStartTime(published.hourly_noise_levels).map((slot) => <li key={slot.start}><span className="dt">{assignmentTime(slot.start)}–{assignmentTime(slot.end)}</span>{slot.label}</li>)}</ul>
        <p className="ph-note">{published.confirmed_notice}</p>
        <p className="ph-note">문의: {published.public_contact}</p>
        {published.publication_provenance.data_classification === 'demo' && <span className="tag">시연 데이터</span>}
      </div>}
    </section>
    <section className="panel span2"><button type="button" className="ghost" onClick={onBack}>← S7로 돌아가기</button></section>
  </div>
}
