import { useMemo, useState } from 'react'
import type { ConstructionNotice } from '../api/notices'
import type { ConfirmedPlan } from '../api/planning'
import type { CandidateResult, CompareResponse, RecommendationResponse } from '../api/recommendations'
import { assignmentTime, candidateLabel } from './s4Display'
import { CHANNEL_LABEL, buildDrafts, buildFacts, defaultReason, type Channel, type NoticeInputs } from './s7Notice'
import './S7NoticeDraft.css'

interface Props {
  notice: ConstructionNotice
  plan: ConfirmedPlan
  res: RecommendationResponse
  candidate: CandidateResult
  compare: CompareResponse
  confirmed: boolean
  onConfirm: () => void
  onBack: () => void
  onNext: () => void
}

const CHANNELS: Channel[] = ['web', 'sms', 'board']

function Source({ children }: { children: string }) {
  return <span className="s7-src">{children}</span>
}

/** 선택 후보가 바뀌면 부모가 key로 다시 마운트한다. */
export function S7NoticeDraft({ notice, plan, res, candidate, compare, confirmed, onConfirm, onBack, onNext }: Props) {
  const facts = useMemo(() => buildFacts(plan, candidate), [plan, candidate])
  const [inputs, setInputs] = useState<NoticeInputs>(() => ({
    department: '서대문구 생활환경과',
    phone: '',
    reason: defaultReason(plan, res, candidate, compare),
  }))
  const [drafts, setDrafts] = useState<Record<Channel, string> | null>(null)
  const [draftKey, setDraftKey] = useState('')
  const [channel, setChannel] = useState<Channel>('web')
  const [copied, setCopied] = useState(false)

  const inputKey = JSON.stringify(inputs)
  const stale = drafts != null && draftKey !== inputKey
  const taskNames = new Map(notice.tasks.map((t) => [t.id, t.name]))
  const set = (patch: Partial<NoticeInputs>) => setInputs((i) => ({ ...i, ...patch }))

  function generate() {
    if (drafts && stale && !window.confirm('직접 수정한 초안 내용이 새 초안으로 바뀝니다. 계속할까요?')) return
    setDrafts(buildDrafts(facts, inputs))
    setDraftKey(inputKey)
    setCopied(false)
    if (!confirmed) onConfirm()
  }

  async function copy() {
    if (!drafts) return
    try {
      await navigator.clipboard.writeText(drafts[channel])
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      window.alert('복사하지 못했습니다. 내용을 직접 선택해 복사해 주세요.')
    }
  }

  return (
    <div className="grid s7">
      <section className="panel span2">
        <div className="ph">
          <span className="step">S7</span>
          <h2>일정 확정과 주민 안내</h2>
          <span className="tag">{confirmed ? '일정 확정됨' : '확정 전'}</span>
        </div>
        <p className="sub">
          선택한 조정안({candidateLabel(candidate.candidate_id)})으로 일정을 확정하고 주민 안내문 초안을 만듭니다. 안내문에는 아래
          정보만 사용하며, 정보에 없는 날짜·번호·내용은 쓰지 않습니다.
        </p>

        <h3>확정된 일정 정보</h3>
        <div className="scroll">
          <table className="s7-facts">
            <tbody>
              <tr>
                <th>공사명</th>
                <td>{facts.projectName}</td>
                <td>
                  <Source>확정 계획</Source>
                </td>
              </tr>
              <tr>
                <th>장소</th>
                <td>{facts.location}</td>
                <td>
                  <Source>확정 계획</Source>
                </td>
              </tr>
              <tr>
                <th>공사 기간</th>
                <td>{facts.period || <span className="muted">미입력</span>}</td>
                <td>
                  <Source>확정 계획</Source>
                </td>
              </tr>
              <tr>
                <th>작업 시간</th>
                <td>
                  <b>
                    {facts.workStart} ~ {facts.workEnd}
                  </b>{' '}
                  <span className="muted">({facts.dateLabel} 기준)</span>
                  <ul className="s7-tasks">
                    {candidate.assignments.map((a) => (
                      <li key={a.task_id}>
                        {assignmentTime(a.start)}–{assignmentTime(a.end)} {taskNames.get(a.task_id) ?? a.task_id}
                      </li>
                    ))}
                  </ul>
                </td>
                <td>
                  <Source>조정안</Source>
                </td>
              </tr>
              <tr>
                <th>사용 장비</th>
                <td>{facts.equipment.join(', ') || <span className="muted">없음</span>}</td>
                <td>
                  <Source>확정 계획</Source>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <h3>담당자 입력</h3>
        <div className="s7-inputs">
          <label>
            <span>담당 부서</span>
            <input value={inputs.department} onChange={(e) => set({ department: e.target.value })} />
          </label>
          <label>
            <span>문의 연락처</span>
            <input
              value={inputs.phone}
              onChange={(e) => set({ phone: e.target.value })}
              placeholder="예: 02-000-0000 (비우면 안내문에서 빠집니다)"
              inputMode="tel"
            />
          </label>
          <label className="wide">
            <span>
              이 시간으로 정한 이유 <span className="muted">· 검증·비교 결과로 만든 문구, 수정 가능</span>
            </span>
            <textarea rows={3} value={inputs.reason} onChange={(e) => set({ reason: e.target.value })} />
          </label>
        </div>

        <div className="row">
          <button type="button" onClick={generate}>
            {!confirmed ? '일정 확정하고 안내문 초안 만들기' : drafts ? '초안 다시 만들기' : '안내문 초안 만들기'}
          </button>
          {stale && <span className="muted">입력이 바뀌었습니다. 초안을 다시 만들어 반영하세요.</span>}
        </div>
      </section>

      {drafts && (
        <section className="panel span2" aria-live="polite">
          <div className="ph">
            <h2>안내문 초안</h2>
            <span className="tag">초안 · 승인·게시 기능 없음</span>
          </div>
          <p className="sub">올릴 곳에 맞게 길이와 형식이 다릅니다. 내용을 확인·수정한 뒤 담당자가 직접 게시해 주세요.</p>
          <div className="seg" role="group" aria-label="안내 채널">
            {CHANNELS.map((c) => (
              <button key={c} type="button" aria-pressed={channel === c} onClick={() => setChannel(c)}>
                {CHANNEL_LABEL[c]}
              </button>
            ))}
          </div>
          <label className="sr-only" htmlFor="s7-draft">
            {CHANNEL_LABEL[channel]} 초안
          </label>
          <textarea
            id="s7-draft"
            className={`s7-draft ${channel}`}
            value={drafts[channel]}
            onChange={(e) => setDrafts((d) => (d ? { ...d, [channel]: e.target.value } : d))}
            rows={channel === 'sms' ? 4 : 14}
          />
          <div className="row">
            <button type="button" className="ghost" onClick={copy}>
              {copied ? '복사됨' : '안내문 복사'}
            </button>
            {channel === 'sms' && <span className="muted">{drafts.sms.length}자</span>}
          </div>
        </section>
      )}

      <section className="panel span2">
        <div className="row">
          <button type="button" className="ghost" onClick={onBack}>
            ← S6으로 돌아가기
          </button>
          <button type="button" onClick={onNext} disabled={!confirmed}>
            다음: 주민 화면 미리보기 (S8)
          </button>
          {!confirmed && <span className="muted">일정을 확정해야 주민 화면을 볼 수 있습니다.</span>}
        </div>
      </section>
    </div>
  )
}
