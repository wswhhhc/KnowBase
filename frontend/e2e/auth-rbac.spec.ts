import { expect, test, type Page } from '@playwright/test'

test('unauthenticated users land on login and admins can open settings', async ({ page }) => {
  await page.goto('/')

  await expect(page.getByRole('heading', { name: 'KnowBase' })).toBeVisible()
  await expect(page.getByLabel('用户名')).toBeVisible()

  await login(page, 'admin', 'admin-pass')

  await expect(page.getByRole('button', { name: '设置' })).toBeVisible()
  await page.getByRole('button', { name: '设置' }).click()
  await expect(page.getByText('用户管理')).toBeVisible()
  await expect(page.getByRole('heading', { name: '审计日志' })).toBeVisible()
})

test('viewer sessions hide admin navigation and receive 403 from settings api', async ({ page }) => {
  await page.goto('/')

  await login(page, 'viewer', 'viewer-pass')

  await expect(page.getByRole('button', { name: '设置' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: '指标' })).toHaveCount(0)

  const status = await page.evaluate(async () => {
    const token = localStorage.getItem('knowbase_access_token') || ''
    const response = await fetch('/api/settings', {
      headers: { Authorization: `Bearer ${token}` },
    })
    return response.status
  })

  expect(status).toBe(403)
})

async function login(page: Page, username: string, password: string) {
  await page.getByLabel('用户名').fill(username)
  await page.getByLabel('密码').fill(password)
  await page.getByRole('button', { name: '登录' }).click()
  await expect(page.getByRole('button', { name: '退出登录' })).toBeVisible()
}
