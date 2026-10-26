/** 값이 없는(missing) 필드 표시. 값처럼 보이지 않게 구분한다. */
export function Missing({ label = '미확인' }: { label?: string }) {
  return <span className="missing">{label}</span>
}
