import { expect, test, type Page } from '@playwright/test'

test('unauthenticated users land on login and admins can open settings', async ({ page }) => {
  await page.goto('/')

  await expect(page.getByRole('heading', { name: '登录工作台' })).toBeVisible()
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

test('viewer can browse an assigned workspace but cannot delete sources', async ({ page }) => {
  await page.goto('/')

  await login(page, 'viewer', 'viewer-pass')

  const result = await page.evaluate(async () => {
    const token = localStorage.getItem('knowbase_access_token') || ''
    const headers = { Authorization: `Bearer ${token}` }
    const workspacesResponse = await fetch('/api/workspaces', { headers })
    const workspaces = await workspacesResponse.json()
    const workspaceId = workspaces[0]?.id || ''
    const deleteResponse = await fetch(
      `/api/documents/source/${encodeURIComponent('missing-source.txt')}?workspace_id=${encodeURIComponent(workspaceId)}`,
      {
        method: 'DELETE',
        headers,
      },
    )
    return {
      workspacesStatus: workspacesResponse.status,
      workspaceCount: Array.isArray(workspaces) ? workspaces.length : 0,
      deleteStatus: deleteResponse.status,
    }
  })

  expect(result.workspacesStatus).toBe(200)
  expect(result.workspaceCount).toBeGreaterThan(0)
  expect(result.deleteStatus).toBe(403)
})

test('admin can create a user, create a workspace, assign membership, and the new user sees that workspace', async ({ page }) => {
  const suffix = `${Date.now()}`
  const username = `qa-viewer-${suffix}`
  const password = `viewer-pass-${suffix}`
  const workspaceName = `E2E Space ${suffix}`

  await page.goto('/')
  await login(page, 'admin', 'admin-pass')
  await page.reload()
  await expect(page.getByRole('button', { name: '退出登录' })).toBeVisible()

  await page.getByRole('button', { name: '设置' }).click()
  await page.getByLabel('新用户用户名').fill(username)
  await page.getByLabel('新用户密码').fill(password)
  await page.getByLabel('新用户角色').selectOption('viewer')
  const createUserResponsePromise = page.waitForResponse((response) =>
    response.url().includes('/api/admin/users') && response.request().method() === 'POST',
  )
  await page.getByRole('button', { name: '创建用户' }).click()
  const createUserResponse = await createUserResponsePromise
  expect(createUserResponse.status(), await createUserResponse.text()).toBe(200)
  await expect(page.getByLabel(`${username} 角色`)).toBeVisible()

  await page.getByTitle('创建工作区').click()
  const workspaceDialog = page.getByRole('dialog')
  await workspaceDialog.getByPlaceholder('工作区名称').fill(workspaceName)
  await workspaceDialog.getByRole('button', { name: '创建' }).click()

  await page.reload()
  await expect(page.getByRole('button', { name: '退出登录' })).toBeVisible()
  await page.getByRole('button', { name: '设置', exact: true }).click()
  await page.getByLabel('选择授权工作区').selectOption({ label: workspaceName })
  await page.getByLabel('添加工作区成员').selectOption({ label: username })
  await page.getByRole('button', { name: '添加成员' }).click()
  await expect(page.getByLabel(`${username} 工作区角色`)).toBeVisible()
  await page.getByRole('button', { name: '保存授权' }).click()

  await page.getByRole('button', { name: '退出登录' }).click()
  await expect(page.getByLabel('用户名')).toBeVisible()

  await login(page, username, password)
  await expect(page.getByRole('button', { name: '设置' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: '指标' })).toHaveCount(0)
  await expect(page.getByRole('combobox')).toContainText(workspaceName)
})

async function login(page: Page, username: string, password: string) {
  await page.getByLabel('用户名').fill(username)
  await page.getByLabel('密码', { exact: true }).fill(password)
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page.getByRole('button', { name: '退出登录' })).toBeVisible()
}
