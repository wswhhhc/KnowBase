import { expect, test, type Page } from '@playwright/test'
import path from 'node:path'

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

test('editor can import a document, ask a question, and jump to the cited source', async ({ page }) => {
  await page.goto('/')
  await login(page, 'editor', 'editor-pass')

  await page.getByRole('button', { name: '知识库' }).click()
  const fileChooserPromise = page.waitForEvent('filechooser')
  await page.getByText('上传文档').click()
  const fileChooser = await fileChooserPromise
  await fileChooser.setFiles(path.resolve(process.cwd(), '../examples/demo-documents/meeting_notes.md'))

  let jobId = ''
  await expect.poll(async () => {
    const token = await page.evaluate(() => localStorage.getItem('knowbase_access_token') || '')
    const response = await page.request.get('/api/jobs', {
      headers: { Authorization: `Bearer ${token}` },
    })
    const jobs = await response.json()
    jobId = jobs.find((job: { job_type: string; id: string }) => job.job_type === 'ingest_file')?.id || ''
    return jobId
  }, { timeout: 10000 }).not.toBe('')

  await expect.poll(async () => {
    const token = await page.evaluate(() => localStorage.getItem('knowbase_access_token') || '')
    const response = await page.request.get(`/api/jobs/${jobId}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    const job = await response.json()
    return job.status
  }, { timeout: 20000 }).toBe('succeeded')

  await page.getByRole('button', { name: '聊天' }).click()
  await page.locator('textarea').fill('这份会议纪要的重点是什么？')
  await page.getByRole('button', { name: '发送' }).click()

  await expect(page.getByText('已根据当前工作区资料回答')).toBeVisible({ timeout: 10000 })
  await page.locator('sup', { hasText: '1' }).click()

  await expect(page.getByText('meeting_notes.md').first()).toBeVisible()
  await expect(page.getByText('支付网关项目会议纪要').first()).toBeVisible()
})

async function login(page: Page, username: string, password: string) {
  await page.getByLabel('用户名').fill(username)
  await page.getByLabel('密码').fill(password)
  await page.getByRole('button', { name: '登录' }).click()
  await expect(page.getByRole('button', { name: '退出登录' })).toBeVisible()
}
