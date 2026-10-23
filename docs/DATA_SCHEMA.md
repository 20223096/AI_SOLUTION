# 데이터 스키마

모든 시간은 ISO 8601 및 `Asia/Seoul`, 구간은 반개구간 `[start, end)`입니다. 시간 슬롯은 기본 15분입니다. dB 값은 단위 종류를 필드명과 `acoustic_unit_type`으로 구분합니다.

| 모델 | 주요 필드 | 단위/검증 |
|---|---|---|
| ConstructionNotice | id, name?, location?, construction_period, original_work_window?, tasks, constraints, source_provenance | 누락값은 null/missing |
| ConstructionTask | id, equipment_id?, duration_minutes?, windows, predecessors, is_movable, required_resources | duration > 0 또는 null |
| Equipment | category, model_name?, count, sound_power_level_db?, acoustic_unit_type | Lw_dBA/Lp_dBA/missing |
| Receptor | type, location, distance_to_source_m, profiles | 거리 m > 0 |
| BackgroundNoise | receptor_id, time_slot, laeq_db | LAeq dB(A) |
| ExistingNoiseEvent | category, start/end, source_noise_data, is_fixed | 고정 외부 일정 |
| SensitivityProfile | time_period, base_weight, adjustments | 무차원 실험 가중치 |
| ScheduleCandidate | assignments, feasibility, reasons, metrics, objectives, provenance | 불가능 후보는 추천 제외 |

출처 상태는 `verified_public`, `user_provided`, `assumed`, `derived`, `missing` 중 하나입니다. 현재 장비값은 모두 `user_provided`, 배경과 민감도는 `assumed`, 계산값은 `derived`, 덤프트럭 및 미확정 공정 시간은 `missing`입니다.
