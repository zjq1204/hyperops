import { test, expect } from '@playwright/test'

async function tryLogin(page) {
  const username = process.env.TEST_USERNAME || 'admin'
  const password = process.env.TEST_PASSWORD || 'admin'

  await page.goto('/login')
  await page.waitForLoadState('networkidle')

  const loginForm = page.locator('form').first()
  const formVisible = await loginForm.isVisible().catch(() => false)
  if (!formVisible) return false

  await page.fill('input[name="username"]', username)
  await page.fill('input[name="password"]', password)
  await page.click('button[type="submit"]')
  await page.waitForLoadState('networkidle')
  return !page.url().includes('/login')
}

test.describe('App shell', () => {
  test('home redirects to dashboard or login', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    expect(page.url()).toMatch(/\/(dashboard|login)(\?|$)/)
  })

  test('unknown routes show 404 page', async ({ page }) => {
    await page.goto('/this-route-does-not-exist-xyz')
    await page.waitForLoadState('networkidle')

    const bodyText = (await page.locator('body').textContent()) || ''
    expect(
      page.url().includes('404') || bodyText.toLowerCase().includes('not found')
    ).toBeTruthy()
  })
})

test.describe('Workspace routes', () => {
  test.beforeEach(async ({ page }) => {
    const loggedIn = await tryLogin(page)
    if (!loggedIn) test.skip()
  })

  test('dashboard shows the product shell', async ({ page }) => {
    await page.goto('/dashboard')
    await page.waitForLoadState('networkidle')

    await expect(page).toHaveURL(/\/dashboard/)
    await expect(page.locator('h1', { hasText: 'HyperOps' })).toBeVisible({
      timeout: 10000
    })
    await expect(page.locator('text=Jenkins').first()).toBeVisible({
      timeout: 5000
    })
  })

  test('jenkins workspace route loads', async ({ page }) => {
    await page.goto('/jenkins/workspace')
    await page.waitForLoadState('networkidle')

    await expect(page).toHaveURL(/\/jenkins\/workspace/)
    await expect(page.locator('h1', { hasText: /Jenkins/ })).toBeVisible({
      timeout: 10000
    })
  })

  test('jenkins records route loads', async ({ page }) => {
    await page.goto('/jenkins/records')
    await page.waitForLoadState('networkidle')

    await expect(page).toHaveURL(/\/jenkins\/records/)
    await expect(page.locator('h1, h2').first()).toBeVisible({ timeout: 10000 })
  })

  test('jenkins settings route loads', async ({ page }) => {
    await page.goto('/jenkins/settings')
    await page.waitForLoadState('networkidle')

    await expect(page).toHaveURL(/\/jenkins\/settings/)
    await expect(page.locator('h1, h2').first()).toBeVisible({ timeout: 10000 })
  })
})
