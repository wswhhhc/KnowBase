import { expect, test, type Page } from '@playwright/test'

test('editor can trigger a clear-workspace job and sees it in task center', async ({ page }) => {
  await page.goto('/')
  await login(page, 'editor', 'editor-pass')

  const job = await page.evaluate(async () => {
    const token = localStorage.getItem('knowbase_access_token') || ''
    const response = await fetch('/api/documents/clear?workspace_id=', {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
    })
    return {
      status: response.status,
      body: await response.json(),
    }
  })
  expect(job.status, JSON.stringify(job.body)).toBe(200)

  await page.getByRole('button', { name: '任务' }).click()
  await expect(page.getByRole('heading', { name: '任务中心' })).toBeVisible()
  await expect(page.getByText(job.body.job_id)).toBeVisible()
  await expect(page.getByText('清空工作区')).toBeVisible()
  await expect.poll(async () => {
    const token = await page.evaluate(() => localStorage.getItem('knowbase_access_token') || '')
    const response = await page.request.get(`/api/jobs/${job.body.job_id}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    const payload = await response.json()
    return payload.status
  }, { timeout: 15000 }).toBe('succeeded')
  await page.reload()
  await expect(page.getByRole('button', { name: '退出登录' })).toBeVisible()
  await page.getByRole('button', { name: '任务' }).click()
  await expect(page.getByText('已完成')).toBeVisible({ timeout: 10000 })
})

async function login(page: Page, username: string, password: string) {
  await page.getByLabel('用户名').fill(username)
  await page.getByLabel('密码').fill(password)
  await page.getByRole('button', { name: '登录' }).click()
  await expect(page.getByRole('button', { name: '退出登录' })).toBeVisible()
}
