import { useEffect, useRef, useState, type DragEvent, type FormEvent, type MouseEvent } from 'react'
import { ApiError } from '../api/client'
import {
  extractNoticeFromFile,
  extractNoticeFromText,
  evidenceText,
  evidenceNeedsReview,
  getFieldEvidence,
  type ConstructionNotice,
  type ExtractResponse,
} from '../api/notices'
import { Missing } from '../components/Missing'
import { ProvenanceBadge } from '../components/ProvenanceBadge'
import { hhmm } from '../utils/time'
import './S1NoticeInput.css'

type InputMode = 'text' | 'file'

type ExtractState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'success'; data: ExtractResponse; sourceKey: string }
  | { status: 'error'; message: string }

const SAMPLE_TEXT = `[공사 안내] 신촌로 상수도관 교체공사
기간: 2026.10.19 ~ 10.30
작업 시간: 09:00~18:00 중 약 2시간
사용 장비: 굴착기(0.6㎥), 브레이커
※ 14시 이전 작업 시작 불가 (자재 반입 일정)`

const ACCEPTED_EXT = ['.txt', '.pdf']

function isAcceptedFile(file: File) {
  const name = file.name.toLowerCase()
  return ACCEPTED_EXT.some((ext) => name.endsWith(ext))
}

/** 현재 입력을 식별하는 키. 성공 이후 입력이 바뀌면 결과를 stale로 본다. */
function inputKey(mode: InputMode, text: string, file: File | null) {
  return mode === 'text' ? `text:${text}` : file ? `file:${file.name}:${file.size}:${file.lastModified}` : 'file:'
}


interface Props {
  /** 추출 결과를 S2(추출 확인)로 넘긴다. */
  onNext: (result: ExtractResponse) => void
}

export function S1NoticeInput({ onNext }: Props) {
  const [mode, setMode] = useState<InputMode>('text')
  const [text, setText] = useState(SAMPLE_TEXT)
  const [file, setFile] = useState<File | null>(null)
  const [fileError, setFileError] = useState<string | null>(null)
  const [dragOver, setDragOver] = useState(false)
  const [state, setState] = useState<ExtractState>({ status: 'idle' })
  const abortRef = useRef<AbortController | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => () => abortRef.current?.abort(), [])

  const loading = state.status === 'loading'
  const currentKey = inputKey(mode, text, file)
  const canSubmit = !loading && (mode === 'text' ? text.trim().length > 0 : file !== null)
  const stale = state.status === 'success' && state.sourceKey !== currentKey

  function pickFile(f: File | undefined) {
    if (!f) return
    if (!isAcceptedFile(f)) {
      setFile(null)
      setFileError('UTF-8 텍스트(.txt) 또는 PDF 파일만 올릴 수 있습니다.')
      return
    }
    setFileError(null)
    setFile(f)
  }

  function onDrop(e: DragEvent<HTMLLabelElement>) {
    e.preventDefault()
    setDragOver(false)
    pickFile(e.dataTransfer.files[0])
  }

  async function submit(e?: FormEvent | MouseEvent<HTMLButtonElement>) {
    e?.preventDefault()
    if (!canSubmit) return

    const controller = new AbortController()
    abortRef.current = controller
    const key = currentKey
    setState({ status: 'loading' })

    try {
      const data =
        mode === 'text'
          ? await extractNoticeFromText(text, controller.signal)
          : await extractNoticeFromFile(file!, controller.signal)
      setState({ status: 'success', data, sourceKey: key })
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        setState({ status: 'idle' })
        return
      }
      const message = err instanceof ApiError ? err.message : '알 수 없는 오류가 발생했습니다.'
      setState({ status: 'error', message })
    } finally {
      if (abortRef.current === controller) abortRef.current = null
    }
  }

  return (
    <div className="grid">
      <section className="panel span2">
        <div className="ph">
          <span className="step">S1</span>
          <h2>공고문 올리기</h2>
        </div>
        <p className="sub">시공사가 보낸 공고문·신고서를 붙여넣거나 파일로 올리면 일정과 장비를 정리합니다.</p>

        <form onSubmit={submit}>
          <div className="seg" role="group" aria-label="입력 방식">
            <button type="button" aria-pressed={mode === 'text'} onClick={() => setMode('text')} disabled={loading}>
              텍스트 붙여넣기
            </button>
            <button type="button" aria-pressed={mode === 'file'} onClick={() => setMode('file')} disabled={loading}>
              파일 올리기
            </button>
          </div>

          <div className="s1-input">
            {mode === 'text' ? (
              <>
                <label htmlFor="notice-text" className="sr-only">
                  신고서 원문
                </label>
                <textarea
                  id="notice-text"
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder="공고문 또는 신고서 내용을 붙여넣으세요."
                  rows={8}
                  disabled={loading}
                />
                <div className="s1-meta muted">{text.trim().length.toLocaleString()}자</div>
              </>
            ) : (
              <>
                <label
                  className={`dropzone${dragOver ? ' over' : ''}${loading ? ' disabled' : ''}`}
                  onDragOver={(e) => {
                    e.preventDefault()
                    setDragOver(true)
                  }}
                  onDragLeave={() => setDragOver(false)}
                  onDrop={onDrop}
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".txt,.pdf,text/plain,application/pdf"
                    onChange={(e) => pickFile(e.target.files?.[0])}
                    disabled={loading}
                  />
                  {file ? (
                    <span>
                      <b>{file.name}</b>
                      <span className="muted"> · {(file.size / 1024).toFixed(1)} KB</span>
                    </span>
                  ) : (
                    <span>
                      파일을 끌어다 놓거나 <u>선택</u>하세요
                      <br />
                      <span className="muted">UTF-8 텍스트(.txt) 또는 텍스트 추출이 가능한 PDF</span>
                    </span>
                  )}
                </label>
                {fileError && <div className="hint error">{fileError}</div>}
              </>
            )}
          </div>

          <div className="row">
            <button type="submit" disabled={!canSubmit}>
              {loading ? '정리하는 중…' : '일정 정리하기'}
            </button>
            {loading && (
              <button type="button" className="ghost" onClick={() => abortRef.current?.abort()}>
                취소
              </button>
            )}
            {mode === 'text' && !loading && text !== SAMPLE_TEXT && (
              <button type="button" className="ghost" onClick={() => setText(SAMPLE_TEXT)}>
                예시 불러오기
              </button>
            )}
          </div>
        </form>

        {state.status === 'error' && (
          <div className="hint error" role="alert">
            {state.message}
            <div className="row">
              <button type="button" className="ghost" onClick={submit} disabled={!canSubmit}>
                다시 시도
              </button>
            </div>
          </div>
        )}
      </section>

      {state.status === 'success' && (
        <ExtractResult result={state.data} stale={stale} onNext={() => onNext(state.data)} />
      )}
    </div>
  )
}

function ExtractResult({ result, stale, onNext }: { result: ExtractResponse; stale: boolean; onNext: () => void }) {
  const { notice } = result
  const evidence = Object.entries(getFieldEvidence(result))

  return (
    <section className={`panel span2${stale ? ' stale' : ''}`} aria-live="polite">
      <div className="ph">
        <span className="step">✓</span>
        <h2>추출 결과</h2>
        <span className="tag">
          {result.mode === 'llm' ? `AI 추출 · ${result.provider} / ${result.model}` : '규칙 기반 추출 (AI 아님)'}
        </span>
      </div>

      {stale && <div className="hint warn">입력이 바뀌었습니다. 다시 정리해야 다음 단계로 넘어갈 수 있습니다.</div>}

      {result.warnings.length > 0 && (
        <div className="hint warn">
          {result.warnings.map((w) => (
            <div key={w}>{w}</div>
          ))}
        </div>
      )}

      <h3>공사 개요</h3>
      <div className="scroll">
        <NoticeSummary notice={notice} />
      </div>

      <h3>
        작업 목록 <span className="muted">({notice.tasks.length})</span>
      </h3>
      {notice.tasks.length === 0 ? (
        <p className="muted">추출된 작업이 없습니다. S2에서 직접 입력해야 합니다.</p>
      ) : (
        <div className="scroll">
          <table>
            <thead>
              <tr>
                <th>작업</th>
                <th>장비</th>
                <th>소요 시간</th>
                <th>선행 작업</th>
                <th>시간 이동</th>
              </tr>
            </thead>
            <tbody>
              {notice.tasks.map((t) => (
                <tr key={t.id}>
                  <td>
                    {t.name} <span className="muted">({t.id})</span>
                  </td>
                  <td>{t.equipment_id ?? <Missing />}</td>
                  <td>{t.duration_minutes != null ? `${t.duration_minutes}분` : <Missing />}</td>
                  <td>{t.predecessors?.length ? t.predecessors.join(', ') : '–'}</td>
                  <td>{t.is_movable ? '가능' : '고정'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h3>출처</h3>
      <ul className="prov-list">
        {Object.entries(notice.source_provenance).map(([field, meta]) => (
          <li key={field}>
            <ProvenanceBadge status={meta.status} />
            <span>
              <b>{field}</b>
              {meta.source && <span className="muted"> · {meta.source}</span>}
              {meta.note && <span className="muted"> · {meta.note}</span>}
            </span>
          </li>
        ))}
      </ul>

      {evidence.length > 0 && (
        <>
          <h3>원문 근거</h3>
          <ul className="prov-list">
            {evidence.map(([field, value]) => (
              <li key={field}>
                <b>{field}</b>
                {evidenceText(value) == null ? <Missing /> : <q>{evidenceText(value)}</q>}
                {evidenceNeedsReview(value) && (
                  <span className="tag">검토 필요</span>
                )}
              </li>
            ))}
          </ul>
        </>
      )}

      <div className="row">
        <button type="button" onClick={onNext} disabled={stale}>
          다음: 추출 확인 (S2)
        </button>
      </div>
    </section>
  )
}

function NoticeSummary({ notice }: { notice: ConstructionNotice }) {
  const period = notice.construction_period
  const win = notice.original_work_window

  return (
    <table>
      <tbody>
        <tr>
          <th>공사명</th>
          <td>{notice.name ?? <Missing />}</td>
        </tr>
        <tr>
          <th>장소</th>
          <td>{notice.location ?? <Missing />}</td>
        </tr>
        <tr>
          <th>공사 기간</th>
          <td>
            {period.start || period.end ? (
              `${period.start ?? '?'} ~ ${period.end ?? '?'}`
            ) : (
              <Missing />
            )}
            {period.raw_text && <div className="muted">원문: “{period.raw_text}”</div>}
          </td>
        </tr>
        <tr>
          <th>작업 시간</th>
          <td>{win ? `${hhmm(win.start)} – ${hhmm(win.end)}` : <Missing />}</td>
        </tr>
        {notice.constraints && Object.keys(notice.constraints).length > 0 && (
          <tr>
            <th>조건</th>
            <td>
              <pre className="s1-pre">{JSON.stringify(notice.constraints, null, 2)}</pre>
            </td>
          </tr>
        )}
      </tbody>
    </table>
  )
}
