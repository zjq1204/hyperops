import { test, expect } from '@playwright/test'

const user = {
  id: 1,
  username: 'admin',
  is_staff: true,
  access_profile: {
    visible_features: ['admin_monitoring'],
    available_platforms: [
      {
        key: 'admin_console',
        default_path: '/management/monitoring/credentials'
      }
    ],
    preferred_platform: 'admin_console',
    landing_path: '/management/monitoring/credentials',
    operation_permissions: [
      'monitoring_credentials_view',
      'monitoring_credentials_use',
      'monitoring_credentials_manage',
      'monitoring_credentials_delete'
    ]
  }
}

const hostA = {
  id: 11,
  hostname: 'host-a',
  address: '10.0.0.11',
  ssh_user: 'root',
  ssh_port: 22,
  enabled: true
}

function credential(overrides = {}) {
  return {
    id: 7,
    name: '生产环境',
    status: 'active',
    active_version: {
      id: 71,
      version: 1,
      algorithm: 'ssh-ed25519',
      curve: 'Ed25519',
      public_key_fingerprint: 'SHA256:test-fingerprint',
      has_passphrase: false,
      validation_status: 'valid'
    },
    usage_count: 1,
    referenced_host_count: 1,
    last_validated_at: '2026-08-13T08:00:00Z',
    updated_at: '2026-08-13T08:00:00Z',
    associated_hosts: [hostA],
    validations: [
      {
        id: 1,
        host_id: hostA.id,
        host_name: hostA.hostname,
        status: 'passed',
        checked_at: '2026-08-13T08:00:00Z'
      }
    ],
    versions: [],
    audit_history: [],
    ...overrides
  }
}

async function installCredentialApiMocks(page, options = {}) {
  const state = {
    credentials: options.credentials || [credential()],
    deleteConflict: Boolean(options.deleteConflict),
    archiveRequests: 0,
    deleteRequests: 0
  }
  const authenticatedUser = options.user || user

  await page.addInitScript(() => {
    window.localStorage.setItem('access_token', 'e2e-access-token')
    window.localStorage.setItem('ui_language', 'zh-CN')
  })

  await page.route('**/api/v1/meta/**', (route) =>
    route.fulfill({
      json: {
        data: {
          enable_monitoring: true,
          enable_notifier: false,
          enable_agentcore_task: false,
          enable_agentcore_metering: false
        }
      }
    })
  )
  await page.route('**/api/v1/auth/user**', (route) =>
    route.fulfill({ json: { data: authenticatedUser } })
  )
  await page.route('**/api/v1/monitoring/hosts/**', (route) =>
    route.fulfill({ json: { results: [hostA] } })
  )
  await page.route('**/api/v1/monitoring/credentials/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname
    const method = request.method()

    if (path.endsWith('/validate/') && method === 'POST') {
      return route.fulfill({
        json: {
          results: [
            {
              id: 2,
              host_id: hostA.id,
              host_name: hostA.hostname,
              status: 'passed',
              latency_ms: 18
            }
          ],
          activation_eligible: true
        }
      })
    }
    if (path.endsWith('/activate/') && method === 'POST') {
      return route.fulfill({ json: credential() })
    }
    if (path.endsWith('/archive/') && method === 'POST') {
      state.archiveRequests += 1
      return route.fulfill({ json: credential({ status: 'archived' }) })
    }
    if (/\/credentials\/\d+\/$/.test(path) && method === 'DELETE') {
      state.deleteRequests += 1
      if (state.deleteConflict) {
        return route.fulfill({
          status: 409,
          json: { code: 'CREDENTIAL_IN_USE', hosts: [hostA] }
        })
      }
      state.credentials = []
      return route.fulfill({ status: 204, body: '' })
    }
    if (/\/credentials\/\d+\/$/.test(path) && method === 'GET') {
      const id = Number(path.match(/credentials\/(\d+)/)?.[1])
      return route.fulfill({
        json: state.credentials.find((item) => item.id === id) || credential()
      })
    }
    if (path.endsWith('/credentials/') && method === 'POST') {
      const created = credential({
        id: 8,
        name: request.postDataJSON().name,
        referenced_host_count: 0,
        usage_count: 0,
        associated_hosts: []
      })
      state.credentials = [created, ...state.credentials]
      return route.fulfill({ status: 201, json: created })
    }
    return route.fulfill({ json: { results: state.credentials } })
  })

  return state
}

test('creates, reviews metadata, validates, and completes a credential', async ({
  page
}) => {
  await installCredentialApiMocks(page, { credentials: [] })
  await page.goto('/management/monitoring/credentials')

  await page.getByRole('button', { name: '新增凭据' }).click()
  await page.getByLabel('凭据名称').fill('生产环境')
  await page.getByLabel('私钥文件').setInputFiles({
    name: 'id_ed25519',
    mimeType: 'text/plain',
    buffer: Buffer.from('test-only-private-key-input')
  })
  await page.getByRole('button', { name: '解析密钥' }).click()
  await expect(page.getByText('SHA256:test-fingerprint')).toBeVisible()
  await page.getByRole('button', { name: '下一页' }).click()
  await page.getByLabel(/host-a/).check()
  await page.getByRole('button', { name: '验证主机' }).click()
  await expect(page.getByText('通过', { exact: true }).last()).toBeVisible()
  await page.getByRole('button', { name: '激活' }).click()
  await expect(page.getByText('生产环境').first()).toBeVisible()
})

test('shows linked host actions instead of deleting a referenced credential', async ({
  page
}) => {
  const state = await installCredentialApiMocks(page, { deleteConflict: true })
  await page.goto('/management/monitoring/credentials')
  await page.getByRole('row', { name: /生产环境/ }).click()
  await page.getByRole('button', { name: '删除' }).click()
  await expect(page.getByRole('heading', { name: '删除 SSH 凭据？' })).toBeVisible()
  expect(state.deleteRequests).toBe(0)
  await page.getByRole('button', { name: '删除', exact: true }).last().click()
  expect(state.deleteRequests).toBe(1)
  await expect(page.getByRole('link', { name: 'host-a', exact: true })).toBeVisible()
})

test('asks for confirmation before archiving a credential', async ({ page }) => {
  const state = await installCredentialApiMocks(page, {
    credentials: [
      credential({
        referenced_host_count: 0,
        usage_count: 0,
        associated_hosts: []
      })
    ]
  })
  await page.goto('/management/monitoring/credentials')
  await page.getByRole('row', { name: /生产环境/ }).click()
  const detailDrawer = page.getByRole('dialog', { name: '凭据详情' })
  await detailDrawer.getByRole('button', { name: '归档' }).click()
  await expect(page.getByRole('heading', { name: '归档 SSH 凭据？' })).toBeVisible()
  expect(state.archiveRequests).toBe(0)
  await page.getByRole('button', { name: '取消', exact: true }).click()
  await expect(page.getByRole('heading', { name: '归档 SSH 凭据？' })).toHaveCount(0)
  expect(state.archiveRequests).toBe(0)
  await detailDrawer.getByRole('button', { name: '归档' }).click()
  await page.getByRole('button', { name: '归档', exact: true }).last().click()
  expect(state.archiveRequests).toBe(1)
})

test('shows credential navigation to viewers but hides management actions', async ({
  page
}) => {
  await installCredentialApiMocks(page, {
    user: {
      ...user,
      access_profile: {
        ...user.access_profile,
        operation_permissions: ['monitoring_credentials_view']
      }
    }
  })
  await page.goto('/management/monitoring/credentials')
  await expect(page.getByRole('link', { name: 'SSH 凭据', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: '新增凭据' })).toHaveCount(0)
  await page.getByRole('row', { name: /生产环境/ }).click()
  await expect(page.getByRole('button', { name: '轮换' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: '归档' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: '删除' })).toHaveCount(0)
})

test('hides credential navigation without view permission', async ({ page }) => {
  await installCredentialApiMocks(page, {
    user: {
      ...user,
      access_profile: {
        ...user.access_profile,
        landing_path: '/management/monitoring/assets',
        operation_permissions: []
      }
    }
  })
  await page.goto('/management/monitoring/credentials')
  await expect(page).toHaveURL(/\/management\/monitoring\/assets$/)
  await expect(page.getByRole('link', { name: '采集主机', exact: true })).toBeVisible()
  await expect(page.getByRole('link', { name: 'SSH 凭据', exact: true })).toHaveCount(0)
})

test('uses mobile list rows without horizontal page overflow', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await installCredentialApiMocks(page)
  await page.goto('/management/monitoring/credentials')
  await expect(page.getByTestId('credential-mobile-list')).toBeVisible()
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth
  )
  expect(overflow).toBe(false)
})

test('asset credential changes invalidate the connection receipt and manage action navigates', async ({
  page
}) => {
  await installCredentialApiMocks(page, {
    credentials: [
      credential({ id: 7, name: '生产环境' }),
      credential({ id: 9, name: '灾备环境', referenced_host_count: 0 })
    ]
  })
  await page.route('**/api/v1/monitoring/config/**', (route) =>
    route.fulfill({ json: {} })
  )
  await page.route('**/api/v1/monitoring/profiles/**', (route) =>
    route.fulfill({ json: [] })
  )
  await page.route('**/api/v1/monitoring/assets/reconciliation/**', (route) =>
    route.fulfill({ json: { results: [], summary: {} } })
  )
  await page.route('**/api/v1/monitoring/hosts/test-connection/**', (route) =>
    route.fulfill({
      json: { verification_receipt: 'receipt-1', latency_ms: 10 }
    })
  )

  await page.goto('/management/monitoring/assets')
  await page.getByRole('button', { name: /新增主机/ }).click()
  await page.getByRole('button', { name: '密钥', exact: true }).click()
  const selector = page.getByLabel('SSH 凭据')
  await selector.selectOption('7')
  await page.getByLabel(/主机地址|地址/).fill('10.0.0.20')
  await page.getByRole('button', { name: '测试连接', exact: true }).click()
  await expect(page.getByRole('button', { name: '保存' })).toBeEnabled()
  await selector.selectOption('9')
  await expect(page.getByRole('button', { name: '保存' })).toBeDisabled()
  await page.getByRole('button', { name: '管理凭据' }).click()
  await expect(page).toHaveURL(/\/management\/monitoring\/credentials/)
})
