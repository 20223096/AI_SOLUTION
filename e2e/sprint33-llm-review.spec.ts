import { expect, test } from '@playwright/test'
import { readFileSync } from 'node:fs'

const extractionFixture = JSON.parse(readFileSync(new URL('./fixtures/sprint32-llm-extract.json', import.meta.url), 'utf8'))

test('actual GPT fixture can be corrected, confirmed, scheduled, and published without another LLM call', async ({ page }) => {
  let extractionRequests = 0
  let recommendationPayload: Record<string, unknown> | null = null
  await page.route('**/api/notices/extract', async (route) => {
    extractionRequests += 1
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(extractionFixture) })
  })
  page.on('request', (request) => {
    if (request.url().includes('/api/prd/recommendations/constraint-filtered')) {
      recommendationPayload = request.postDataJSON() as Record<string, unknown>
    }
  })

  await page.goto('/')
  await page.locator('#notice-text').fill(`공사명: 신촌 보도 정비공사
위치: 서울특별시 서대문구 연세로 12 앞
공사기간: 2026-09-11 ~ 2026-09-11
작업시간: 08:00~17:00
장비: 굴착기 1대(09:00~11:00), 브레이커 2대(13:00~14:00)
작업순서: 굴착 후 포장 복구
조정 불가: 포장 복구는 당일 완료`)
  await page.getByRole('button', { name: '일정 정리하기' }).click()
  await expect(page.getByText(/AI 추출 · openai_compatible/)).toBeVisible()
  await page.getByRole('button', { name: /다음: 추출 확인/ }).click()

  await expect(page.getByTestId('llm-review-alert')).toContainText('작업별 장비 배정')
  await expect(page.getByText('입력 필요').first()).toBeVisible()
  await expect(page.getByText('LLM 추출').first()).toBeVisible()

  await page.getByRole('button', { name: /계획 확정하고 제약 확인/ }).click()
  await expect(page.getByRole('alert')).toContainText('[작업별 장비 배정] 포장 복구: 작업시간(분)을 입력해 주세요.')
  await expect(page.getByRole('alert')).toContainText('도로 굴착 여부를 선택해 주세요.')
  await expect(page.getByRole('alert')).toContainText('담당자 확인 체크박스를 선택해 주세요.')

  await page.getByRole('button', { name: '굴착함' }).click()
  await page.getByLabel('허가시간 제한 있음').check()
  await page.getByLabel('도로점용 허가시간 시작').fill('08:00')
  await page.getByLabel('도로점용 허가시간 종료').fill('17:00')
  await page.getByLabel('도로점용 허가조건을 확인했습니다').check()
  await page.getByLabel('restore 공정명').fill('포장 복구')
  await page.getByLabel('포장 복구 작업시간(분)').fill('60')
  await page.getByLabel('포장 복구을 복구 작업으로 지정').check()
  await page.getByLabel('break 공정명').fill('포장 파쇄')

  await page.getByRole('button', { name: '공식 주소·좌표 조회' }).click()
  await expect(page.getByText(/도로명주소 건물 출입구 대표점/)).toBeVisible({ timeout: 30_000 })
  await page.getByLabel('공식 주소 대표점을 확인했습니다').check()
  await page.getByLabel('원문 근거, LLM 추출값, 담당자 수정값을 모두 검토했습니다').check()
  await expect(page.getByText('담당자 수정').first()).toBeVisible()
  await page.getByRole('button', { name: /계획 확정하고 제약 확인/ }).click()

  await page.getByLabel('굴착 시작').fill('09:00')
  await page.getByLabel('굴착 종료').fill('11:00')
  await page.getByLabel('포장 복구 시작').fill('11:00')
  await page.getByLabel('포장 복구 종료').fill('12:00')
  await page.getByLabel('포장 파쇄 시작').fill('13:00')
  await page.getByLabel('포장 파쇄 종료').fill('14:00')
  await page.getByRole('button', { name: '일정 검증하기' }).click()
  const toS4 = page.getByRole('button', { name: /S4/ })
  await expect(toS4).toBeEnabled({ timeout: 30_000 })
  await toS4.click()
  const toS5 = page.getByRole('button', { name: /다음: 조정안 고르기/ })
  await expect(toS5).toBeVisible({ timeout: 30_000 })

  const body = recommendationPayload as {
    planning: { user_review_completed: boolean; user_modified_fields: string[] }
    task_duration_by_task: Record<string, number>
    task_name_by_task: Record<string, string>
    equipment_by_task: Record<string, string | null>
  }
  expect(body.planning.user_review_completed).toBe(true)
  expect(body.planning.user_modified_fields).toEqual(expect.arrayContaining([
    'road_excavation', 'road_occupancy_permit_window', 'tasks.1.duration_minutes', 'tasks.2.name',
  ]))
  expect(body.task_duration_by_task).toMatchObject({ excavate: 120, restore: 60, break: 60 })
  expect(body.task_name_by_task).toMatchObject({ restore: '포장 복구', break: '포장 파쇄' })
  expect(body.equipment_by_task).toMatchObject({ excavate: 'excavator', restore: null, break: 'breaker' })

  await toS5.click()
  await page.getByRole('radio').first().click()
  await page.getByRole('button', { name: /다음: 조정 전후 비교/ }).click()
  const toS7 = page.getByRole('button', { name: /다음: 일정 확정/ })
  await expect(toS7).toBeEnabled({ timeout: 30_000 })
  await toS7.click()
  await page.getByPlaceholder('필수').fill('서대문구 공사안내 02-0000-0000')
  await page.getByRole('button', { name: '비공개 초안 서버 저장' }).click()
  await expect(page.getByText('서버 안내문 초안')).toBeVisible({ timeout: 30_000 })
  await page.getByRole('button', { name: /수정 저장 후 확정/ }).click()
  await expect(page.getByText('서버 확정·공개됨')).toBeVisible({ timeout: 30_000 })
  await page.getByRole('button', { name: /다음: 주민 공개 화면/ }).click()
  await expect(page.getByText('공개 API 조회 결과')).toBeVisible()
  const published = await page.evaluate(async () => (await fetch('/api/public/construction/extracted-llm/resident-notice')).json())
  expect(published.status).toBe('published')
  expect(extractionRequests).toBe(1)
})
