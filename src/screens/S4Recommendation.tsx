import { useEffect, useState } from 'react'
import type { ConfirmedPlan } from '../api/planning'
import { isSelectable, requestRecommendations, type RecommendationResponse } from '../api/recommendations'
import { ANALYSIS_DATE, type ScheduleValidationResponse } from '../api/schedules'
import { CandidateBadge } from '../components/CandidateBadge'
import { errorMessage, isAbort, type Async } from '../utils/async'
import { candidateLabel, candidateReason, caveatText, formatDelta, formatNumber } from './s4Display'
import { S4SensitivityMap } from './S4SensitivityMap'
import './S4Recommendation.css'

interface Props {
  plan: ConfirmedPlan
  /** S3에서 검증한 원 일정 결과(요약 표시용) */
  s3Validation: ScheduleValidationResponse
  onBack: () => void
  onEditPlan: () => void
  onNext: (res: RecommendationResponse) => void
}

/** plan이 바뀌면 부모가 key로 다시 마운트한다. */
export function S4Recommendation({ plan, s3Validation, onBack, onEditPlan, onNext }: Props) {
  const [rec, setRec] = useState<Async<RecommendationResponse>>({ status: 'loading' })
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    requestRecommendations(plan, controller.signal)
      .then((data) => setRec({ status: 'success', data }))
      .catch((err) => !isAbort(err) && setRec({ status: 'error', message: errorMessage(err) }))
    return () => controller.abort()
  }, [plan, reloadKey])

  const heading = (
    <div className="ph">
      <span className="step">S4</span>
      <h2>후보 추천</h2>
      <span className="tag">분석일 {ANALYSIS_DATE} · 시뮬레이션</span>
    </div>
  )

  if (rec.status === 'loading') {
    return (
      <section className="panel">
        {heading}
        <p className="muted" role="status">
          이동 후보를 만들고 제약으로 거르는 중…
        </p>
      </section>
    )
  }

  if (rec.status === 'error') {
    return (
      <section className="panel">
        {heading}
        <div className="hint error" role="alert">
          {rec.message}
        </div>
        <div className="row">
          <button
            type="button"
            onClick={() => {
              setRec({ status: 'loading' })
              setReloadKey((k) => k + 1)
            }}
          >
            다시 시도
          </button>
          <button type="button" className="ghost" onClick={onBack}>
            ← S3로 돌아가기
          </button>
        </div>
      </section>
    )
  }

  const res = rec.data
  const selectable = res.candidates.filter((c) => isSelectable(c, res))
  const noneFeasible = res.recommendation_status === 'none_feasible' || selectable.length === 0

  return (
    <div className="grid s4">
      <section className="panel span2">
        {heading}
        <p className="sub">
          기존 최적화기의 15분 단위 이동 후보(0~120분) 중 확정한 제약을 모두 지키고 조건부 Pareto에 속한 후보만 추천합니다.
          전역 최적해가 아닙니다.
        </p>

        <div className="s4-summary">
          <div className={`s4-stat ${s3Validation.feasible ? 'ok' : 'fail'}`}>
            <span>원 일정 (S3)</span>
            <b>{s3Validation.feasible ? '제약 통과' : `위반 ${s3Validation.violations.length}건`}</b>
          </div>
          <div className="s4-stat">
            <span>생성된 후보</span>
            <b>{res.candidates.length}개</b>
          </div>
          <div className="s4-stat">
            <span>제약 충족</span>
            <b>{res.candidates.filter((c) => c.prd_feasible).length}개</b>
          </div>
          <div className={`s4-stat ${noneFeasible ? 'fail' : 'ok'}`}>
            <span>추천 가능</span>
            <b>{selectable.length}개</b>
          </div>
        </div>

        {noneFeasible && (
          <div className="hint error" role="alert">
            <b>제약을 모두 지키는 추천 후보가 없습니다.</b> 서버 오류가 아니라 입력한 제약 안에서 가능한 이동 후보가 없다는 결과입니다.
            {res.no_recommendation_reasons.length > 0 && (
              <ul className="s4-list">
                {res.no_recommendation_reasons.map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            )}
          </div>
        )}

        {res.missing_information.length > 0 && (
          <div className="hint warn">
            <b>결측 정보</b>
            <ul className="s4-list">
              {res.missing_information.map((m) => (
                <li key={m}>{m}</li>
              ))}
            </ul>
          </div>
        )}
      </section>

      <section className="panel span2">
        <div className="ph">
          <h2>소음 민감도 지도</h2>
          <span className="tag">공사장 기준 100m·200m</span>
        </div>
        <S4SensitivityMap scenarioId={res.scenario_id} />
      </section>

      <section className="panel span2">
        <div className="ph">
          <h2>이동 후보 판정</h2>
        </div>
        <div className="scroll">
          <table className="s4-table">
            <thead>
              <tr>
                <th>후보</th>
                <th>판정</th>
                <th>착공 이동</th>
                <th>일정 변경량</th>
                <th>추가 소음 영향</th>
                <th>기존 소음과 겹침</th>
                <th>사유</th>
              </tr>
            </thead>
            <tbody>
              {res.candidates.map((c) => {
                const can = isSelectable(c, res)
                return (
                  <tr key={c.candidate_id} className={can ? 'recommended' : 'disabled'}>
                    <td>
                      <b>{candidateLabel(c.candidate_id)}</b> <span className="muted">({c.candidate_id})</span>
                      {c.candidate_id === res.original_schedule?.candidate_id && <span className="muted"> · 원 일정</span>}
                    </td>
                    <td>
                      <CandidateBadge candidate={c} selectable={can} />
                    </td>
                    <td>{formatDelta(c.project_start_change_minutes)}분</td>
                    <td>{formatNumber(c.schedule_change_minutes)}분</td>
                    <td>{formatNumber(c.noise_impact.incremental_impact_cost)}</td>
                    <td>{formatNumber(c.noise_impact.existing_noise_overlap_receptor_minutes)}</td>
                    <td className="s4-reason">{candidateReason(c, can)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </section>

      {res.caveats.length > 0 && (
        <section className="panel span2">
          <div className="ph">
            <h2>해석 시 유의사항</h2>
            <span className="tag">{res.optimization_claim}</span>
          </div>
          <ul className="s4-list">
            {res.caveats.map((c) => (
              <li key={c}>{caveatText(c)}</li>
            ))}
          </ul>
        </section>
      )}

      <section className="panel span2">
        <div className="row">
          <button type="button" className="ghost" onClick={onBack}>
            ← S3로 돌아가기
          </button>
          {noneFeasible ? (
            <button type="button" onClick={onEditPlan}>
              S2에서 계획 수정하기
            </button>
          ) : (
            <button type="button" onClick={() => onNext(res)}>
              다음: 조정안 고르기 (S5)
            </button>
          )}
        </div>
      </section>
    </div>
  )
}
