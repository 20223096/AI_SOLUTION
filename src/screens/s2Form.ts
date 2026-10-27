import type { ConstructionTask, SourceMetadata } from '../api/notices'
import type { ConfirmedPlan, PlanningDraft, TimeWindow } from '../api/planning'
import { hhmm } from '../utils/time'

/** 모든 입력은 문자열로 들고 있다가 확정 시점에 변환한다. 빈 문자열 = 미입력. */
export interface EquipmentForm {
  equipment_id: string
  category: string
  specification: string
  model_name: string
  required_usage_minutes: string
  max_daily_count: string
  window_start: string
  window_end: string
}

export interface TaskForm {
  id: string
  name: string
  equipment_id: string // '' = 장비 없음
  count: string
  restoration: boolean
}

export interface PlanningForm {
  project_name: string
  location: string
  period_start: string
  period_end: string
  period_raw: string | null
  work_start: string
  work_end: string
  road_excavation: '' | 'yes' | 'no'
  has_permit_window: boolean
  permit_start: string
  permit_end: string
  same_day_restoration: boolean
  completion_date: string
  non_adjustable: string // 줄바꿈 구분
  equipment: EquipmentForm[]
  tasks: TaskForm[]
}

export interface FormIssue {
  key: string
  message: string
}

const str = (v: string | number | null | undefined) => (v == null ? '' : String(v))

export function formFromDraft(draft: PlanningDraft, tasks: ConstructionTask[]): PlanningForm {
  const equipment = draft.equipment_constraints.map<EquipmentForm>((e) => ({
    equipment_id: e.equipment_id,
    category: str(e.category),
    specification: str(e.specification),
    model_name: str(e.model_name),
    required_usage_minutes: str(e.required_usage_minutes),
    max_daily_count: str(e.max_daily_count),
    window_start: e.permitted_time_windows[0] ? hhmm(e.permitted_time_windows[0].start) : '',
    window_end: e.permitted_time_windows[0] ? hhmm(e.permitted_time_windows[0].end) : '',
  }))
  const equipmentIds = new Set(equipment.map((e) => e.equipment_id))

  return {
    project_name: str(draft.project_name),
    location: str(draft.location),
    period_start: str(draft.construction_period.start),
    period_end: str(draft.construction_period.end),
    period_raw: draft.construction_period.raw_text ?? null,
    work_start: draft.total_work_window ? hhmm(draft.total_work_window.start) : '',
    work_end: draft.total_work_window ? hhmm(draft.total_work_window.end) : '',
    road_excavation: draft.road_excavation == null ? '' : draft.road_excavation ? 'yes' : 'no',
    has_permit_window: draft.road_occupancy_permit_window != null,
    permit_start: draft.road_occupancy_permit_window ? hhmm(draft.road_occupancy_permit_window.start) : '',
    permit_end: draft.road_occupancy_permit_window ? hhmm(draft.road_occupancy_permit_window.end) : '',
    same_day_restoration: draft.same_day_restoration_required === true,
    completion_date: '',
    non_adjustable: '',
    equipment,
    // 장비 대수는 추출되지 않으므로 사용자가 직접 입력한다.
    tasks: tasks.map((t) => ({
      id: t.id,
      name: t.name,
      equipment_id: t.equipment_id && equipmentIds.has(t.equipment_id) ? t.equipment_id : '',
      count: '',
      restoration: false,
    })),
  }
}

const isPositiveInt = (s: string) => /^\d+$/.test(s.trim()) && Number(s) > 0
const isNonNegInt = (s: string) => /^\d+$/.test(s.trim())

function checkWindow(issues: FormIssue[], key: string, label: string, start: string, end: string, required: boolean) {
  if (!start && !end) {
    if (required) issues.push({ key, message: `${label}을 입력해 주세요.` })
    return
  }
  if (!start || !end) issues.push({ key, message: `${label}의 시작·종료 시각을 모두 입력해 주세요.` })
  else if (start >= end) issues.push({ key, message: `${label}의 종료 시각이 시작 시각보다 늦어야 합니다.` })
}

export function validateForm(f: PlanningForm): FormIssue[] {
  const issues: FormIssue[] = []
  if (!f.project_name.trim()) issues.push({ key: 'project_name', message: '공사명을 입력해 주세요.' })
  if (!f.location.trim()) issues.push({ key: 'location', message: '장소를 입력해 주세요.' })

  if (!f.period_start || !f.period_end) {
    issues.push({ key: 'construction_period', message: '공사 시작일과 종료일을 확인해 주세요.' })
  } else if (f.period_start > f.period_end) {
    issues.push({ key: 'construction_period', message: '공사 종료일이 시작일보다 빠릅니다.' })
  }

  checkWindow(issues, 'total_work_window', '전체 작업 허용시간', f.work_start, f.work_end, true)
  if (!f.road_excavation) issues.push({ key: 'road_excavation', message: '도로 굴착 여부를 선택해 주세요.' })
  if (f.has_permit_window) {
    checkWindow(issues, 'road_occupancy_permit_window', '도로점용 허가시간', f.permit_start, f.permit_end, true)
  }
  if (f.completion_date && f.period_start && f.completion_date < f.period_start) {
    issues.push({ key: 'project_completion_date', message: '계획 완료일이 공사 시작일보다 빠릅니다.' })
  }

  f.equipment.forEach((e, i) => {
    const label = `장비 ${e.equipment_id}`
    if (!e.category.trim()) issues.push({ key: `equipment.${i}.category`, message: `${label}: 장비 종류를 입력해 주세요.` })
    if (!isPositiveInt(e.required_usage_minutes)) {
      issues.push({ key: `equipment.${i}.required_usage_minutes`, message: `${label}: 필요 사용시간(분)을 입력해 주세요.` })
    }
    if (e.max_daily_count && !isPositiveInt(e.max_daily_count)) {
      issues.push({ key: `equipment.${i}.max_daily_count`, message: `${label}: 일 최대 대수는 1 이상의 정수여야 합니다.` })
    }
    checkWindow(issues, `equipment.${i}.window`, `${label} 허용시간`, e.window_start, e.window_end, false)
  })

  f.tasks.forEach((t, i) => {
    if (t.equipment_id && !isPositiveInt(t.count)) {
      issues.push({ key: `tasks.${i}.count`, message: `작업 ${t.name}: 투입 장비 대수를 입력해 주세요.` })
    } else if (!t.equipment_id && t.count && !isNonNegInt(t.count)) {
      issues.push({ key: `tasks.${i}.count`, message: `작업 ${t.name}: 장비 대수는 정수여야 합니다.` })
    }
  })
  if (f.same_day_restoration && !f.tasks.some((t) => t.restoration)) {
    issues.push({ key: 'restoration', message: '당일 복구가 필요하면 복구 작업을 하나 이상 지정해 주세요.' })
  }
  return issues
}

const CONFIRMED: SourceMetadata = { status: 'user_provided', source: 'confirmed form', note: null, unit: null }
const win = (start: string, end: string): TimeWindow => ({ start, end })
const orNull = (s: string) => (s.trim() ? s.trim() : null)

/** validateForm 통과 후에만 호출한다. */
export function toConfirmedPlan(f: PlanningForm, draft: PlanningDraft): ConfirmedPlan {
  const confirmedFields = [
    'project_name',
    'location',
    'construction_period',
    'total_work_window',
    'road_excavation',
    'equipment_constraints',
    'equipment_required_usage_minutes',
    'same_day_restoration_required',
    ...(f.equipment.some((e) => e.max_daily_count) ? ['max_daily_equipment_count'] : []),
    ...(f.has_permit_window ? ['road_occupancy_permit_window'] : []),
    ...(f.completion_date ? ['project_completion_date'] : []),
  ]

  // source_evidence 입력 타입은 문자열 값만 받는다.
  const sourceEvidence = Object.fromEntries(
    Object.entries(draft.source_evidence).filter((e): e is [string, string] => typeof e[1] === 'string'),
  )

  const tasksWithEquipment = f.tasks.filter((t) => t.equipment_id)

  return {
    planning: {
      notice_id: draft.notice_id,
      project_name: f.project_name.trim(),
      location: f.location.trim(),
      construction_period: { start: f.period_start, end: f.period_end, raw_text: f.period_raw },
      total_work_window: win(f.work_start, f.work_end),
      road_excavation: f.road_excavation === 'yes',
      road_occupancy_permit_window: f.has_permit_window ? win(f.permit_start, f.permit_end) : null,
      equipment_constraints: f.equipment.map((e) => ({
        equipment_id: e.equipment_id,
        category: e.category.trim(),
        specification: orNull(e.specification),
        model_name: orNull(e.model_name),
        max_daily_count: e.max_daily_count ? Number(e.max_daily_count) : null,
        required_usage_minutes: Number(e.required_usage_minutes),
        permitted_time_windows: e.window_start && e.window_end ? [win(e.window_start, e.window_end)] : [],
        source_metadata: CONFIRMED,
      })),
      // 고정 작업은 추출되지 않았으므로 생성하지 않는다(가이드 1절).
      fixed_tasks: [],
      same_day_restoration_required: f.same_day_restoration,
      project_completion_date: f.completion_date || null,
      non_adjustable_conditions: f.non_adjustable
        .split('\n')
        .map((s) => s.trim())
        .filter(Boolean),
      source_evidence: sourceEvidence,
      field_provenance: {
        ...draft.field_provenance,
        ...Object.fromEntries(confirmedFields.map((k) => [k, CONFIRMED])),
      },
      provenance: 'user_provided',
    },
    predecessors: draft.predecessors,
    equipment_by_task: Object.fromEntries(f.tasks.map((t) => [t.id, t.equipment_id || null])),
    equipment_count_by_task: Object.fromEntries(tasksWithEquipment.map((t) => [t.id, Number(t.count)])),
    restoration_task_ids: f.same_day_restoration ? f.tasks.filter((t) => t.restoration).map((t) => t.id) : [],
  }
}
