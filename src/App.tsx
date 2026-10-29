import { useState } from 'react'
import type { ExtractResponse } from './api/notices'
import type { ConfirmedPlan } from './api/planning'
import { isSelectable, representativeId, type CompareResponse, type RecommendationResponse } from './api/recommendations'
import type { ResidentNoticeDraft } from './api/residentNotices'
import { AppHeader, type ScreenId } from './components/AppHeader'
import { S1NoticeInput } from './screens/S1NoticeInput'
import { S2ExtractionReview } from './screens/S2ExtractionReview'
import { S3ConstraintCheck, type S3Result } from './screens/S3ConstraintCheck'
import { S4Recommendation } from './screens/S4Recommendation'
import { S5CandidatePicker } from './screens/S5CandidatePicker'
import { S6Comparison } from './screens/S6Comparison'
import { S7NoticeDraft } from './screens/S7NoticeDraft'
import { S8ResidentView } from './screens/S8ResidentView'

type Stage = 'plan' | 's3' | 'rec' | 'candidate' | 'comparison'
const STAGES: Stage[] = ['plan', 's3', 'rec', 'candidate', 'comparison']

function App() {
  const [screen, setScreen] = useState<ScreenId>('S1')
  // 단계별 결과. 앞 단계 결과가 바뀌면 뒤 단계 결과는 모두 폐기한다(가이드 6절).
  const [extraction, setExtraction] = useState<ExtractResponse | null>(null) // S1 → S2
  const [plan, setPlan] = useState<ConfirmedPlan | null>(null) // S2 → S3, S4
  const [s3Result, setS3Result] = useState<S3Result | null>(null) // S3 → S4
  const [rec, setRec] = useState<RecommendationResponse | null>(null) // S4 → S5
  const [candidateId, setCandidateId] = useState<string | null>(null) // S5 → S6
  const [comparison, setComparison] = useState<CompareResponse | null>(null) // S6 → S7
  const [confirmedDraft, setConfirmedDraft] = useState<ResidentNoticeDraft | null>(null) // S7 → S8
  // 앞 단계 결과가 바뀌면 다음 화면을 key로 다시 마운트해 이전 상태를 버린다.
  const [extractionVersion, setExtractionVersion] = useState(0)
  const [planVersion, setPlanVersion] = useState(0)

  /** stage와 그 뒤 단계의 결과를 모두 비운다. */
  function resetFrom(stage: Stage) {
    const from = STAGES.indexOf(stage)
    if (from <= 0) setPlan(null)
    if (from <= 1) setS3Result(null)
    if (from <= 2) setRec(null)
    if (from <= 3) setCandidateId(null)
    if (from <= 4) setComparison(null)
    setConfirmedDraft(null)
  }

  const candidate = rec?.candidates.find((c) => c.candidate_id === candidateId && isSelectable(c, rec)) ?? null

  return (
    <div className="wrap">
      <AppHeader current={screen} />

      {/* 각 화면은 마운트해 두어 앞 단계로 돌아가도 입력이 유지되게 한다. */}
      <div hidden={screen !== 'S1'}>
        <S1NoticeInput
          onNext={(result) => {
            if (result !== extraction) {
              setExtraction(result)
              setExtractionVersion((v) => v + 1)
              resetFrom('plan')
            }
            setScreen('S2')
          }}
        />
      </div>

      {extraction && (
        <div hidden={screen !== 'S2'}>
          <S2ExtractionReview
            key={extractionVersion}
            extraction={extraction}
            onBack={() => setScreen('S1')}
            onConfirm={(confirmed) => {
              resetFrom('s3')
              setPlan(confirmed)
              setPlanVersion((v) => v + 1)
              setScreen('S3')
            }}
          />
        </div>
      )}

      {extraction && plan && (
        <div hidden={screen !== 'S3'}>
          <S3ConstraintCheck
            key={planVersion}
            notice={extraction.notice}
            plan={plan}
            onBack={() => setScreen('S2')}
            onNext={(result) => {
              setS3Result(result)
              setScreen('S4')
            }}
          />
        </div>
      )}

      {plan && s3Result && (
        <div hidden={screen !== 'S4'}>
          <S4Recommendation
            key={planVersion}
            plan={plan}
            s3Validation={s3Result.validation}
            onBack={() => setScreen('S3')}
            onEditPlan={() => setScreen('S2')}
            onNext={(res) => {
              if (res !== rec) {
                resetFrom('candidate')
                setRec(res)
                // S5에서 API 결과 기준 대표 추천을 기본 선택해 둔다. 담당자가 바꿀 수 있다.
                setCandidateId(representativeId(res))
              }
              setScreen('S5')
            }}
          />
        </div>
      )}

      {rec && (
        <div hidden={screen !== 'S5'}>
          <S5CandidatePicker
            res={rec}
            selectedId={candidateId}
            onSelect={(id) => {
              if (id !== candidateId) {
                resetFrom('comparison')
                setCandidateId(id)
              }
            }}
            onBack={() => setScreen('S4')}
            onNext={() => setScreen('S6')}
          />
        </div>
      )}

      {extraction && plan && rec && candidate && (
        <div hidden={screen !== 'S6'}>
          <S6Comparison
            key={candidate.candidate_id}
            res={rec}
            candidate={candidate}
            notice={extraction.notice}
            plan={plan}
            onBack={() => setScreen('S5')}
            onNext={(data) => {
              setComparison(data)
              setScreen('S7')
            }}
          />
        </div>
      )}

      {extraction && plan && rec && candidate && comparison && (
        <div hidden={screen !== 'S7'}>
          <S7NoticeDraft
            key={candidate.candidate_id}
            notice={extraction.notice}
            plan={plan}
            res={rec}
            candidate={candidate}
            compare={comparison}
            confirmed={confirmedDraft?.candidate_id === candidate.candidate_id && confirmedDraft.publication_status === 'published'}
            onConfirm={setConfirmedDraft}
            onBack={() => setScreen('S6')}
            onNext={() => setScreen('S8')}
          />
        </div>
      )}

      {screen === 'S8' && plan && candidate && confirmedDraft?.candidate_id === candidate.candidate_id && (
        <S8ResidentView projectId={plan.planning.notice_id} location={plan.planning.location} onBack={() => setScreen('S7')} />
      )}

      <footer>쉿간표 PoC · 추출 결과는 사용자 확인 전까지 확정값이 아닙니다.</footer>
    </div>
  )
}

export default App
