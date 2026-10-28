import { devices, expect, test } from '@playwright/test'

test('presentation comparison is traceable and responsive', async ({ browser, page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: '발표 비교' }).click()
  await expect(page.getByRole('heading', { name: '날짜별 시나리오 비교' })).toBeVisible()
  await expect(page.getByText('기존 일정 유지가 정상 결과')).toBeVisible()
  await expect(page.getByText('모델 점수 13.72 → 13.12')).toBeVisible()
  await expect(page.getByText('scripts/run_sprint29_experiments.py')).toBeVisible()
  await expect(page.getByRole('heading', { name: '2026-09-11' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '2026-10-07' })).toBeVisible()
  await page.screenshot({ path: 'docs/assets/sprint36/comparison-desktop.png', fullPage: true })

  const mobile = await browser.newPage({ ...devices['iPhone 13'] })
  await mobile.goto('/')
  await mobile.getByRole('button', { name: '발표 비교' }).click()
  await expect(mobile.getByText('기존 일정 유지가 정상 결과')).toBeVisible()
  expect(await mobile.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(1)
  await mobile.screenshot({ path: 'docs/assets/sprint36/comparison-mobile.png', fullPage: true })
  await mobile.close()
})
