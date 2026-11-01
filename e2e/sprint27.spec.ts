import { devices, expect, test } from '@playwright/test'

test('S1-S8 no-login preview workflow, publication separation, refresh, and mobile layout', async ({ browser, page }) => {
  const consoleErrors: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text())
  })

  const apiResponses: string[] = []
  page.on('response', (response) => {
    if (response.url().includes('/api/')) apiResponses.push(`${response.status()} ${response.request().method()} ${new URL(response.url()).pathname}`)
  })

  await page.goto('/')
  await page.locator('#notice-text').fill('2026년 연세로 공사 07:00~18:00, 절단기, 브레이커, 굴착기, 롤러')
  await page.getByRole('button', { name: '일정 정리하기' }).click()
  await expect(page.getByText('규칙 기반 추출 (AI 아님)')).toBeVisible()
  await page.getByRole('button', { name: /다음: 추출 확인/ }).click()

  await page.getByRole('button', { name: '공식 주소·좌표 조회' }).waitFor()
  await page.locator('#s2-name').fill('Sprint 27 실제 브라우저 검증 공사')
  await page.locator('#s2-location').fill('서울특별시 서대문구 연세로2나길 20')
  await page.getByLabel('공사 시작일').fill('2026-09-11')
  await page.getByLabel('공사 종료일').fill('2026-09-11')
  await page.getByRole('button', { name: '굴착함' }).click()
  await page.getByRole('button', { name: '공식 주소·좌표 조회' }).click()
  await expect(page.getByText(/도로명주소 건물 출입구 대표점/)).toBeVisible({ timeout: 30_000 })
  await page.getByLabel('공식 주소 대표점을 확인했습니다').check()
  for (const input of await page.locator('input[aria-label$="투입 대수"]').all()) await input.fill('1')
  await page.getByRole('button', { name: /계획 확정하고 제약 확인/ }).click()

  await page.getByRole('button', { name: '일정 검증하기' }).click()
  const toS4 = page.getByRole('button', { name: /S4/ })
  await expect(toS4).toBeEnabled({ timeout: 30_000 })
  await toS4.click()
  const toS5 = page.getByRole('button', { name: /다음: 조정안 고르기/ })
  await expect(toS5).toBeVisible({ timeout: 30_000 })
  await toS5.click()

  const choices = page.getByRole('radio')
  await expect(choices.first()).toBeVisible()
  await choices.first().click()
  await page.getByRole('button', { name: /다음: 조정 전후 비교/ }).click()
  const toS7 = page.getByRole('button', { name: /다음: 일정 확정/ })
  await expect(toS7).toBeEnabled({ timeout: 30_000 })
  await toS7.click()

  await page.getByPlaceholder('필수').fill('서대문구 공사안내 02-0000-0000')
  await page.getByLabel('제목').fill('심사위원 시연 공고문')
  await page.getByLabel('본문').fill('서버에 공개되지 않는 시연 내용입니다.')

  const before = await page.evaluate(async () => {
    const response = await fetch('/api/public/construction/extracted-mock/resident-notice')
    return response.json()
  })
  expect(before.status).toBe('not_published')

  await page.getByRole('button', { name: '시연 화면으로 계속하기' }).click()
  await expect(page.getByText('시연용 미리보기 · 서버에 공개되지 않은 내용')).toBeVisible()
  await expect(page.getByText('심사위원 시연 공고문')).toBeVisible()
  expect(apiResponses.some((entry) => entry.includes('/api/staff/resident-notices'))).toBeFalsy()

  await page.getByRole('button', { name: '실제 공개 조회' }).click()
  await expect(page.getByText(/공개 API에 확정된 주민 안내가 없습니다/)).toBeVisible()

  const after = await page.evaluate(async () => {
    const response = await fetch('/api/public/construction/extracted-mock/resident-notice')
    return response.json()
  })
  expect(after.status).toBe('not_published')
  expect(JSON.stringify(after)).not.toMatch(/predicted_db|noise_impact|receptor|constraint_violations/)

  expect(apiResponses.some((entry) => entry.includes('POST /api/locations/address-coordinate'))).toBeTruthy()
  expect(apiResponses.every((entry) => entry.startsWith('200 '))).toBeTruthy()
  expect(consoleErrors).toEqual([])

  await page.reload()
  await expect(page.getByRole('heading', { name: '공고문 올리기' })).toBeVisible()
  const persisted = await page.evaluate(async () => (await fetch('/api/public/construction/extracted-mock/resident-notice')).json())
  expect(persisted.status).toBe('not_published')

  const mobile = await browser.newPage({ ...devices['iPhone 13'] })
  await mobile.goto('/')
  await expect(mobile.getByRole('heading', { name: '공고문 올리기' })).toBeVisible()
  const overflow = await mobile.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
  expect(overflow).toBeLessThanOrEqual(1)
  await mobile.close()
})
