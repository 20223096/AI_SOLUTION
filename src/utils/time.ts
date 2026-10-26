/** "07:00:00" → "07:00" (input[type=time] 값과 화면 표시에 사용) */
export const hhmm = (t: string) => t.slice(0, 5)

/** "07:30" → 450 */
export function toMinutes(t: string): number {
  const [h, m] = t.split(':').map(Number)
  return h * 60 + m
}

/** 450 → "07:30". 하루(24:00)를 넘으면 null. */
export function fromMinutes(min: number): string | null {
  if (min < 0 || min >= 24 * 60) return null
  return `${String(Math.floor(min / 60)).padStart(2, '0')}:${String(min % 60).padStart(2, '0')}`
}
