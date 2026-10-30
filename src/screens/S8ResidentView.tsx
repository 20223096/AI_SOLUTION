import { useEffect, useState } from 'react'
import { getPublicResidentNotice, type ResidentPublicResponse } from '../api/residentNotices'
import { errorMessage, isAbort, type Async } from '../utils/async'
import { assignmentTime } from './s4Display'
import { byStartTime } from './s7Notice'
import './S8ResidentView.css'

interface Props { projectId: string; location: string; onBack: () => void }

type PublicNotice = NonNullable<ResidentPublicResponse['notice']>
type Interval = { start: string; end: string }
type Level = 'loud' | 'moderate' | 'quiet'

const WEEKDAY = ['일', '월', '화', '수', '목', '금', '토']
const LEVEL_LABEL: Record<Level, string> = { loud: '시끄러움', moderate: '보통', quiet: '조용' }

/** "2026-09-11T07:00:00+09:00" → "9월 11일 (금)" (시각의 날짜 부분만 쓴다) */
function dateLabel(iso: string): string {
  const [y, m, d] = iso.slice(0, 10).split('-').map(Number)
  return `${m}월 ${d}일 (${WEEKDAY[new Date(Date.UTC(y, m - 1, d)).getUTCDay()]})`
}

const span = (i: Interval) => `${assignmentTime(i.start)} ~ ${assignmentTime(i.end)}`

/**
 * 공개 응답의 작업 목록에는 시끄러운 작업 여부가 없다.
 * 시끄러운 작업 구간(noisy_work_intervals) 안에 들어 있으면 '시끄러움', 아니면 예정 작업이므로 '보통'으로 표시한다.
 */
const taskLevel = (task: Interval, noisy: Interval[]): Level =>
  noisy.some((n) => n.start <= task.start && task.end <= n.end) ? 'loud' : 'moderate'

/** 문의처에서 전화번호를 찾아 tel: 링크로 쓴다. 없으면 null. */
function telHref(contact: string): string | null {
  const m = /0\d{1,2}-?\d{3,4}-?\d{4}/.exec(contact)
  return m ? `tel:${m[0].replace(/-/g, '')}` : null
}

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
      {published && <ResidentPhone notice={published} location={location} />}
    </section>
    <section className="panel span2"><button type="button" className="ghost" onClick={onBack}>← S7로 돌아가기</button></section>
  </div>
}

function ResidentPhone({ notice, location }: { notice: PublicNotice; location: string }) {
  const slots = byStartTime(notice.hourly_noise_levels)
  const schedule = byStartTime(notice.today_schedule)
  const noisy = byStartTime(notice.noisy_work_intervals)
  const quiet = notice.longest_quiet_interval
  const day = slots[0]?.start ?? schedule[0]?.start
  const tel = telHref(notice.public_contact)

  return <div className="s8r">
    <header className="s8r-top">
      <div className="s8r-brand">
        <svg width="36" height="36" viewBox="0 0 220 220" aria-hidden="true">
          <circle cx="110" cy="110" r="92" fill="none" stroke="#FFFFFF" strokeWidth="14" />
          <path d="M110 110 L150 132" stroke="#8FD3C8" strokeWidth="14" strokeLinecap="round" />
          <rect x="99" y="52" width="22" height="70" rx="11" fill="#8FD3C8" />
          <path d="M92 118 Q92 104 106 104 L116 104 Q130 104 130 118 L130 132 Q111 142 92 132 Z" fill="#8FD3C8" />
        </svg>
        <b>쉿간표</b>
        {notice.publication_provenance.data_classification === 'demo' && <span className="s8r-demo">시연 예시</span>}
      </div>
      <p className="s8r-sub">{[day && dateLabel(day), location].filter(Boolean).join(' · ')}</p>
      <h1>오늘 우리 동네 공사 안내</h1>
    </header>

    <div className="s8r-body">
      <section className="s8r-card">
        <p className="s8r-h">오늘 한눈에</p>
        <div className="s8r-glance">
          <span className="s8r-ic loud" aria-hidden="true">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#B5432F" strokeWidth="2" strokeLinecap="round"><path d="M11 5 6 9H2v6h4l5 4z" /><path d="M15.5 8.5a5 5 0 0 1 0 7" /><path d="M19 5a10 10 0 0 1 0 14" /></svg>
          </span>
          <div>
            <p className="s8r-gl">시끄러운 작업</p>
            {noisy.length > 0
              ? noisy.map((n) => <p key={n.start} className="s8r-gt">{span(n)}</p>)
              : <p className="s8r-gt">없음</p>}
          </div>
        </div>
        <div className="s8r-glance">
          <span className="s8r-ic quiet" aria-hidden="true">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#1F6F65" strokeWidth="2" strokeLinecap="round"><path d="M11 5 6 9H2v6h4l5 4z" /><path d="m22 9-6 6" /><path d="m16 9 6 6" /></svg>
          </span>
          <div>
            <p className="s8r-gl">시끄러운 작업이 없는 시간</p>
            <p className="s8r-gt">{quiet ? span(quiet) : '없음'}</p>
            <p className="s8r-gs">이 공사 기준이에요</p>
          </div>
        </div>
      </section>

      {slots.length > 0 && <section className="s8r-card">
        <p className="s8r-h">이 공사 소리, 시간별로</p>
        <div className="s8r-bars" style={{ gridTemplateColumns: `repeat(${slots.length}, minmax(0, 1fr))` }}>
          {slots.map((s) => <span key={s.start} className={`s8r-bar ${s.level}`} title={`${assignmentTime(s.start)}–${assignmentTime(s.end)} ${s.label}`} aria-label={`${assignmentTime(s.start)}시 ${s.label}`} />)}
        </div>
        <div className="s8r-hours" style={{ gridTemplateColumns: `repeat(${slots.length}, minmax(0, 1fr))` }} aria-hidden="true">
          {slots.map((s) => <span key={s.start}>{Number(assignmentTime(s.start).slice(0, 2))}</span>)}
        </div>
        <div className="s8r-legend">
          {(['loud', 'moderate', 'quiet'] as const).map((l) => <span key={l}><i className={`s8r-bar ${l}`} />{LEVEL_LABEL[l]}</span>)}
        </div>
      </section>}

      <section className="s8r-card s8r-list">
        <p className="s8r-h">오늘 작업 일정</p>
        {schedule.length === 0 && <p className="s8r-empty">오늘 예정된 작업이 없어요.</p>}
        {schedule.map((t) => {
          const level = taskLevel(t, noisy)
          return <div key={`${t.start}-${t.task_name}`} className="s8r-row">
            <span className="s8r-time">{assignmentTime(t.start)}~{assignmentTime(t.end)}</span>
            <span className="s8r-task">{t.task_name}</span>
            <span className={`s8r-lv ${level}`}>{LEVEL_LABEL[level]}</span>
          </div>
        })}
      </section>

      <section className="s8r-note">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#1F6F65" strokeWidth="2" strokeLinecap="round" aria-hidden="true"><circle cx="12" cy="12" r="9" /><path d="M12 8v4" /><path d="M12 16h.01" /></svg>
        <p>{notice.confirmed_notice}</p>
      </section>

      <section className="s8r-card">
        <p className="s8r-h">문의</p>
        {tel
          ? <a className="s8r-call" href={tel}>문의 · {notice.public_contact}</a>
          : <p className="s8r-call">문의 · {notice.public_contact}</p>}
      </section>

      <p className="s8r-foot">{notice.quiet_interval_limitation}<br />소음 단계는 작업 종류 기준이며 측정값이 아니에요.</p>
    </div>
  </div>
}
