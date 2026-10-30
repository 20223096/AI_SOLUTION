import { expect, test } from '@playwright/test'

test('opens and refreshes the live final-demo comparison route', async ({ page }) => {
  await page.goto('/demo-comparison')
  await expect(page.getByRole('heading', { name: '날짜별 추천 결과 비교' })).toBeVisible()
  await expect(page.getByText('10:00~17:00')).toBeVisible()
  await expect(page.getByText('offset-120')).toBeVisible()
  await expect(page.getByText('offset-0')).toBeVisible()
  await expect(page.getByText('예측/시뮬레이션 결과이며 실측 피해 감소가 아닙니다.')).toBeVisible()

  await page.reload()
  await expect(page.getByRole('heading', { name: '날짜별 추천 결과 비교' })).toBeVisible()
  await expect(page.getByText('08:00~15:00')).toHaveCount(3)

  await page.getByRole('button', { name: 'S1~S8로 돌아가기' }).click()
  await expect(page.getByRole('heading', { name: '공고문 올리기' })).toBeVisible()
})
