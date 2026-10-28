import { useEffect, useState } from 'react'
import './ScenarioComparison.css'
import { rowsForDay, type DayResult } from './scenarioComparisonModel'

type ExperimentReport = {
  experiment_version: string
  generated_at: string
  generator: string
  data_sources: Record<string, string>
  model_assumptions: string[]
  environment: { python: string; platform: string; ortools: string; grid_minutes: number }
  global_optimality_claimed: boolean
  results: DayResult[]
}

const value = (input: number | null, suffix = '') => input === null ? 'N/A' : `${input.toLocaleString('ko-KR')}${suffix}`

export function ScenarioComparison() {
  const [report, setReport] = useState<ExperimentReport | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    fetch('/sprint36-comparison.json')
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        return response.json() as Promise<ExperimentReport>
      })
      .then(setReport)
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : '알 수 없는 오류'))
  }, [])

  if (error) return <section className="panel"><p className="hint error">비교 실험 데이터를 불러오지 못했습니다: {error}</p></section>
  if (!report) return <section className="panel"><p>비교 실험 데이터를 불러오는 중…</p></section>

  return (
    <main className="comparison-page">
      <section className="panel comparison-intro">
        <div className="ph"><span className="step">발표</span><h1>날짜별 시나리오 비교</h1><span className="tag">읽기 전용</span></div>
        <p className="sub">동일한 Sprint 29 실험 러너 결과입니다. Noise Impact는 모델 점수이며 실측 소음이나 실제 민원 감소를 뜻하지 않습니다.</p>
        <div className="callout-grid">
          <article><b>2026-09-11</b><strong>기존 일정 유지가 정상 결과</strong><span>cp_sat_v2도 원안 7.36보다 낮은 영향우선안을 찾지 않았습니다.</span></article>
          <article><b>2026-10-07</b><strong>모델 점수 13.72 → 13.12</strong><span>별도 지표인 일정 변경량은 420분입니다.</span></article>
        </div>
      </section>

      {report.results.map((day) => (
        <section className="panel" key={day.analysis_date} aria-labelledby={`day-${day.analysis_date}`}>
          <div className="ph"><h2 id={`day-${day.analysis_date}`}>{day.analysis_date}</h2><span className="tag">{day.scenario_id}</span></div>
          <div className="scroll">
            <table className="comparison-table">
              <thead><tr><th>안</th><th>Noise Impact</th><th>제약 위반</th><th>탐색 후보</th><th>Pareto 후보</th><th>일정 변경량</th><th>Quiet Window</th><th>연속 고소음시간</th></tr></thead>
              <tbody>{rowsForDay(day).map((row) => <tr key={row.label}>
                <th>{row.label}</th><td>{value(row.metrics.noise_impact)}</td><td>{row.metrics.constraint_violation_count === null ? 'N/A' : row.metrics.constraint_violation_count === 0 ? '없음' : `${row.metrics.constraint_violation_count}건`}</td>
                <td>{value(row.candidateCount)}</td><td>{value(row.paretoCount)}</td><td>{value(row.metrics.schedule_change_minutes, '분')}</td><td>{value(row.metrics.quiet_window_minutes, '분')}</td><td>{value(row.metrics.continuous_high_noise_minutes, '분')}</td>
              </tr>)}</tbody>
            </table>
          </div>
        </section>
      ))}

      <section className="panel provenance-detail">
        <div className="ph"><h2>실험 근거와 재현 정보</h2></div>
        <dl><dt>실험 버전</dt><dd>{report.experiment_version}</dd><dt>실행 시각</dt><dd>{new Date(report.generated_at).toLocaleString('ko-KR', { timeZone: 'Asia/Seoul' })}</dd><dt>생성 명령 기준</dt><dd><code>{report.generator}</code></dd><dt>환경</dt><dd>Python {report.environment.python} · OR-Tools {report.environment.ortools} · {report.environment.grid_minutes}분 grid</dd></dl>
        <h3>데이터 출처</h3><ul>{Object.entries(report.data_sources).map(([key, source]) => <li key={key}><code>{key}</code>: {source}</li>)}</ul>
        <h3>모델 가정</h3><ul>{report.model_assumptions.map((assumption) => <li key={assumption}>{assumption}</li>)}</ul>
        <p className="hint warn">전역 최적성 주장: {report.global_optimality_claimed ? '있음' : '없음'}. 계산하지 않은 값은 N/A로 표시합니다.</p>
      </section>
    </main>
  )
}
