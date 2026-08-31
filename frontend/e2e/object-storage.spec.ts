import { test, expect } from '@playwright/test'

const adminUser = {
  id: 1,
  username: 'object-storage-admin',
  is_superuser: true,
  access_profile: {
    visible_features: ['admin_object_storage', 'object_storage'],
    available_platforms: [
      {
        key: 'admin_console',
        default_path: '/management/object-storage/overview'
      }
    ],
    preferred_platform: 'admin_console',
    landing_path: '/management/object-storage/overview'
  }
}

const tenant = {
  id: 1,
  code: 'acme',
  name: 'Acme',
  enabled: true,
  default_bucket_quota: 5,
  delivery_lifetime_seconds: 86400
}

async function installMocks(page) {
  await page.addInitScript(() => {
    window.localStorage.setItem('access_token', 'e2e-access-token')
    window.localStorage.setItem('ui_language', 'zh-CN')
  })

  await page.route('**/api/v1/meta/**', (route) =>
    route.fulfill({
      json: {
        data: {
          enable_object_storage: true,
          enable_monitoring: true,
          enable_notifier: false,
          enable_agentcore_task: false,
          enable_agentcore_metering: false
        }
      }
    })
  )
  await page.route('**/api/v1/auth/user**', (route) =>
    route.fulfill({ json: { data: adminUser } })
  )
  await page.route('**/api/v1/object-storage/management/**', async (route) => {
    const url = new URL(route.request().url())
    const path = url.pathname
    let body = []
    if (path.endsWith('/tenants/')) body = [tenant]
    else if (path.includes('/feishu/')) body = { id: 1, app_id: 'app-id' }
    else if (path.includes('/resource-pools/')) body = []
    else if (path.includes('/audit-events/')) body = []
    else if (path.includes('/applications/')) body = []
    else if (path.includes('/members/')) body = []
    else if (path.includes('/cloud-identities/')) body = []
    else if (path.includes('/buckets/')) body = []
    else if (path.includes('/access-keys/')) body = []
    await route.fulfill({ json: { data: body } })
  })
}

test.describe('Object storage administration workspace', () => {
  test.beforeEach(async ({ page }) => {
    await installMocks(page)
  })

  for (const [path, heading] of [
    ['/management/object-storage/overview', '对象存储管理'],
    ['/management/object-storage/enterprise-access', '企业接入'],
    ['/management/object-storage/resources', '资源'],
    ['/management/object-storage/tasks', '任务'],
    ['/management/object-storage/audit', '审计']
  ]) {
    test(`${path} renders without horizontal overflow`, async ({ page }) => {
      await page.goto(path)
      await expect(page.locator('h1').first()).toContainText(heading)
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth)
      ).toBeLessThanOrEqual(
        await page.evaluate(() => document.documentElement.clientWidth)
      )
      await expect(page.locator('body')).not.toContainText('TOTP')
      await expect(page.locator('body')).not.toContainText('Huawei')
    })
  }
})
