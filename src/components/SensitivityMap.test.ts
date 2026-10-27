import { describe, expect, it } from 'vitest'
import { buildSensitivityMap } from './sensitivityMapModel'

describe('sensitivity map provenance', () => {
  it('plots only verified coordinates and keeps assumed/unverified receptors off-map', () => {
    const catalog = {
      official_facilities: [{ facility_id: 's', name: '학교', type: 'school', latitude: '37.5', longitude: '126.9' }],
      receptor_distances: [{ project_id: 'p', project_name: '공사', project_latitude: '37.4', project_longitude: '126.8' }],
      receptors: [{ name: '주거 수음점', type: 'residential', latitude: '', longitude: '', coordinate_accuracy: 'assumed_receptor' }],
    } as never
    const result = buildSensitivityMap(catalog)
    expect(result.points).toHaveLength(2)
    expect(result.points.find((p) => p.type === 'construction')?.role).toContain('공사 선형/경계 아님')
    expect(result.unavailable).toEqual([{ name: '주거 수음점', type: 'residential', status: 'assumed_receptor' }])
  })
})
