export type ScreenId = 'S1' | 'S2' | 'S3' | 'S4' | 'S5' | 'S6' | 'S7' | 'S8'

const SCREENS: { id: ScreenId; label: string }[] = [
  { id: 'S1', label: 'S1 공고문 올리기' },
  { id: 'S2', label: 'S2 추출 확인' },
  { id: 'S3', label: 'S3 제약 확인' },
  { id: 'S4', label: 'S4 후보 추천' },
  { id: 'S5', label: 'S5 조정안 고르기' },
  { id: 'S6', label: 'S6 조정 전후 비교' },
  { id: 'S7', label: 'S7 확정·주민 안내' },
  { id: 'S8', label: 'S8 주민 화면' },
]

export function AppHeader({ current }: { current: ScreenId }) {
  return (
    <>
      <header className="top">
        <div className="brand">
          <b>쉿간표</b>
          <span>서대문구 기후환경과</span>
        </div>
        <div className="ctx">
          <span className="chip">신촌동 생활권</span>
        </div>
      </header>
      <ol className="steps" aria-label="진행 단계">
        {SCREENS.map((s) => (
          <li key={s.id} aria-current={s.id === current ? 'step' : undefined}>
            {s.label}
          </li>
        ))}
      </ol>
    </>
  )
}
