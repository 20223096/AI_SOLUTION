const SOURCES = [
  ['공식 공공데이터', 'prov-verified_public'],
  ['과거 관측 기반 대표값', 'prov-observed'],
  ['사용자 입력·확인값', 'prov-user_provided'],
  ['시나리오 가정값', 'prov-assumed'],
  ['물리모델 계산값', 'prov-derived'],
  ['LLM 추출값', 'prov-llm'],
] as const

export function DataProvenanceLegend() {
  return (
    <aside className="provenance-key" aria-label="데이터 출처 구분">
      <b>데이터 출처</b>
      {SOURCES.map(([label, className]) => <span key={label} className={`badge ${className}`}>{label}</span>)}
    </aside>
  )
}
