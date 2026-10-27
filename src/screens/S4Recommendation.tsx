import { useEffect, useState } from 'react'
import type { ConfirmedPlan } from '../api/planning'
import { isSelectable, requestRecommendations, type RecommendationResponse } from '../api/recommendations'
import { ANALYSIS_DATE, type ScheduleValidationResponse } from '../api/schedules'
import { CandidateBadge } from '../components/CandidateBadge'
import { SensitivityMap } from '../components/SensitivityMap'
import { errorMessage, isAbort, type Async } from '../utils/async'
import { candidateLabel, candidateReason, caveatText, formatDelta, formatNumber } from './s4Display'
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
          OR-Tools가 작업별 시작시간과 확정 제약으로 찾은 해 중, 소음 영향·일정 변경·연속 고소음·기존 소음 중첩의
          비지배 후보만 추천합니다. 탐색한 해 집합 안의 결과이며 전역 최적해가 아닙니다.
        </p>
        <p className="s4-note"><span className="badge prov-derived">물리모델 계산값</span> 추천 엔진 <b>cp_sat_v2</b> · 배경소음 <span className="badge prov-observed">과거 관측 기반 대표값</span> · 민감도 <span className="badge prov-assumed">시나리오 가정값</span></p>

        <div className="s4-summary">
          <div className={`s4-stat ${s3Validation.feasible ? 'ok' : 'fail'}`}>
            <span>원 일정 (S3)</span>
            <b>{s3Validation.feasible ? '제약 통과' : `위반 ${s3Validation.violations.length}건`}</b>
          </div>
          <div className="s4-stat">
            <span>생성된 후보</span>
            <b>{res.explored_candidate_count}개</b>
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
        <div className="ph"><h2>신촌 민감도 지도</h2><span className="tag">실제 좌표 / 시나리오 가정 분리</span></div>
        <SensitivityMap />
      </section>

      <section className="panel span2">
        <div className="ph"><h2>시간대별 적용 민감도</h2><span className="tag">legacy_v1 · 가정 가중치</span></div>
        <div className="scroll"><table><thead><tr><th>조건</th><th>실제 엔진 설정</th><th>구현 상태</th></tr></thead><tbody>
          <tr><td>일반 주간 (07:00–18:00)</td><td>기본 1.0</td><td>계산 적용</td></tr>
          <tr><td>이른 아침·저녁 (05:00–07:00, 18:00–22:00)</td><td>기본 1.5</td><td>계산 적용</td></tr>
          <tr><td>야간 (22:00–05:00)</td><td>기본 2.0</td><td>계산 적용</td></tr>
          <tr><td>시험기간·대학</td><td>+0.5</td><td>학사일정 일치 시 적용</td></tr>
          <tr><td>학교·병원</td><td>+0.5</td><td>수음점 유형 기준 적용</td></tr>
          <tr><td>주말 주거 휴식</td><td>+0.3</td><td>weekend_rest 입력 시 적용</td></tr>
          <tr><td>학교 수업시간 / 그 외</td><td>전용 가중치 없음</td><td>미구현</td></tr>
          <tr><td>공휴일</td><td>전용 가중치 없음</td><td>미구현</td></tr>
        </tbody></table></div>
        <p className="s4-note muted">민감도는 Noise Impact 점수에만 반영되며 물리적 dB를 바꾸지 않습니다. 같은 시간에 조건이 겹치면 legacy_v1은 기본값에 조정값을 더합니다.</p>
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
