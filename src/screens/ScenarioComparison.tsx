import { useEffect, useState } from 'react'
import { getRecommendationDiagnostics, type RecommendationDiagnostics } from '../api/demoComparison'
import { errorMessage, isAbort, type Async } from '../utils/async'
import './ScenarioComparison.css'

type ComparisonData = { congestion: RecommendationDiagnostics; clear: RecommendationDiagnostics }

const clock = (iso: string | null) => iso ? iso.slice(11, 16) : '미조회'
const addMinutes = (iso: string | null, minutes: number) => {
  if (!iso) return '미조회'
  const [hour, minute] = clock(iso).split(':').map(Number)
  const total = hour * 60 + minute + minutes
  return `${String(Math.floor(total / 60) % 24).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`
}
const candidate = (day: RecommendationDiagnostics, id: string) => day.candidates.find((row) => row.id === id)

export function ScenarioComparison() {
  const [state, setState] = useState<Async<ComparisonData>>({ status: 'loading' })
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    Promise.all([
      getRecommendationDiagnostics('2026-09-11', controller.signal),
      getRecommendationDiagnostics('2026-10-07', controller.signal),
    ])
      .then(([congestion, clear]) => setState({ status: 'success', data: { congestion, clear } }))
      .catch((error) => !isAbort(error) && setState({ status: 'error', message: errorMessage(error) }))
    return () => controller.abort()
  }, [reloadKey])

  if (state.status === 'loading') return <section className="panel"><p role="status">최신 계산 결과를 불러오는 중…</p></section>
  if (state.status === 'error') return <section className="panel"><div className="hint error">비교 계산 결과를 불러오지 못했습니다: {state.message}</div><button onClick={() => { setState({ status: 'loading' }); setReloadKey((key) => key + 1) }}>다시 시도</button></section>

  const { congestion, clear } = state.data
  const sepOriginal = candidate(congestion, 'offset-0')
  const sepRecommended = candidate(congestion, congestion.recommended_candidate_ids[0] ?? '')
  const octOriginal = candidate(clear, 'offset-0')
  const octRecommended = candidate(clear, clear.recommended_candidate_ids[0] ?? '')
  if (!sepOriginal || !sepRecommended || !octOriginal || !octRecommended) {
    return <section className="panel"><div className="hint error">현재 계산 결과에 발표 비교에 필요한 원안 또는 대표 추천안이 없습니다.</div></section>
  }

  const cards = [
    { day: congestion, original: sepOriginal, recommended: sepRecommended, title: '주변 철거가 있는 날', assumption: '주변 철거 고소음 08:00~11:00 적용', tone: 'changed' },
    { day: clear, original: octOriginal, recommended: octRecommended, title: '주변 철거가 없는 날', assumption: '날짜 한정 주변 철거 오버레이 미적용', tone: 'kept' },
  ] as const

  return <main className="comparison-page">
    <section className="panel comparison-intro">
      <div className="ph"><span className="step">발표</span><h1>날짜별 추천 결과 비교</h1><span className="tag">백엔드 최신 계산</span></div>
      <p className="sub">동일한 신규 공사 작업과 장비 허용시간을 두 날짜에 적용하고, 주변 철거 이벤트 적용 여부만 비교합니다.</p>
      <div className="comparison-highlight"><b>3시간 → 1시간</b><span>시연 가정 조건에서 동시 고소음시간 2시간 감소</span></div>
    </section>

    <section className="comparison-days" aria-label="날짜별 비교 결과">
      {cards.map(({ day, original, recommended, title, assumption, tone }) => {
        const reduced = original.existing_high_noise_overlap_minutes - recommended.existing_high_noise_overlap_minutes
        return <article className={`panel comparison-card ${tone}`} key={day.analysis_date}>
          <div className="ph"><div><h2>{day.analysis_date}</h2><p className="comparison-kicker">{title}</p></div><span className="tag">{recommended.id}</span></div>
          <p className="comparison-assumption">{assumption}</p>
          <div className="schedule-pair">
            <div><span>원안</span><b>{clock(original.first_task_start)}~{addMinutes(original.first_task_start, 420)}</b><small>동시 고소음 {original.existing_high_noise_overlap_minutes}분</small></div>
            <span aria-hidden="true">→</span>
            <div><span>추천안</span><b>{clock(recommended.first_task_start)}~{addMinutes(recommended.first_task_start, 420)}</b><small>동시 고소음 {recommended.existing_high_noise_overlap_minutes}분</small></div>
          </div>
          <dl className="comparison-facts"><div><dt>변경량</dt><dd>{recommended.project_start_shift_minutes}분</dd></div><div><dt>겹침 감소</dt><dd>{reduced}분</dd></div><div><dt>장비 허용시간</dt><dd>08:00~17:00 준수</dd></div></dl>
          <p className="comparison-reason">{reduced > 0 ? `주변 철거와 동시 고소음 작업이 겹치는 시간을 ${original.existing_high_noise_overlap_minutes}분에서 ${recommended.existing_high_noise_overlap_minutes}분으로 줄이는 최소 변경안을 추천했습니다.` : '동시 고소음 겹침이 없어 변경량이 가장 작은 원안을 유지합니다.'}</p>
        </article>
      })}
    </section>

    <section className="panel comparison-notes">
      <h2>데이터 구분과 해석</h2>
      <div className="comparison-note-grid"><p><b>실제 데이터</b>공개자료에서 확인한 공사와 공사기간</p><p><b>시연 가정</b>철거 고소음시간 08~11시, 82dB, 25m 주거 계산 지점, 신규 공사 하루 장비 배치</p><p><b>계산 결과</b>동시 고소음시간, 추천 일정, 일정 변경량</p></div>
      <div className="hint warn">철거 고소음시간 08~11시는 시연 가정입니다. 예측/시뮬레이션 결과이며 실측 피해 감소가 아닙니다.</div>
    </section>
  </main>
}
