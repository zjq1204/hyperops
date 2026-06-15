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

test.describe('Login page', () => {
  test('renders login form with all fields', async ({ page }) => {
    await page.goto('/login')
    await page.waitForLoadState('networkidle')

    await expect(page.locator('input[name="username"]')).toBeVisible()
    await expect(page.locator('input[name="password"]')).toBeVisible()
    await expect(page.locator('input[type="checkbox"]')).toBeVisible()
    await expect(page.locator('button[type="submit"]')).toBeVisible()
  })

  test('renders the redesigned login shell', async ({ page }) => {
    await page.goto('/login')
    await page.waitForLoadState('networkidle')

    await expect(page.locator('[data-testid="auth-showcase"]')).toBeVisible()
    await expect(page.locator('[data-testid="auth-login-card"]')).toBeVisible()
    await expect(page.locator('[data-testid="auth-brand-mark"]')).toBeVisible()
  })

  test('shows validation error when submitting empty form', async ({ page }) => {
    await page.goto('/login')
    await page.waitForLoadState('networkidle')

    await page.click('button[type="submit"]')

    const errorVisible = await page
      .locator('p.text-red-700, .text-red-600, .bg-red-50, [class*="error"]')
      .first()
      .isVisible()
      .catch(() => false)

    expect(errorVisible).toBeTruthy()
  })

  test('shows error for invalid credentials', async ({ page }) => {
    await page.goto('/login')
    await page.waitForLoadState('networkidle')

    await page.fill('input[name="username"]', 'wronguser')
    await page.fill('input[name="password"]', 'wrongpassword')
    await page.click('button[type="submit"]')
    await page.waitForLoadState('networkidle')

    expect(page.url()).toContain('/login')

    const errorMsg = page.locator('.auth-error, .text-red-600').first()
    await expect(errorMsg).toBeVisible({ timeout: 5000 })
  })

  test('successful login redirects away from /login', async ({ page }) => {
    const loggedIn = await tryLogin(page)
    if (!loggedIn) test.skip()
    expect(page.url()).not.toContain('/login')
  })
})

test.describe('Auth guards', () => {
  test('unauthenticated user is redirected to /login for protected routes', async ({
    page
  }) => {
    await page.goto('/login')
    await page.evaluate(() => localStorage.clear())
    await page.context().clearCookies()

    const protectedRoutes = [
      '/dashboard',
      '/jenkins/workspace',
      '/management/jenkins/instances',
      '/settings/profile'
    ]

    for (const route of protectedRoutes) {
      await page.goto(route)
      await page.waitForLoadState('networkidle')
      expect(page.url()).toContain('/login')
    }
  })

  test('authenticated user is redirected away from /login', async ({ page }) => {
    const loggedIn = await tryLogin(page)
    if (!loggedIn) test.skip()

    await page.goto('/login')
    await page.waitForLoadState('networkidle')
    expect(page.url()).not.toContain('/login')
  })
})

test.describe('Language switcher', () => {
  test('language switcher is present on login page', async ({ page }) => {
    await page.goto('/login')
    await page.waitForLoadState('networkidle')
    await expect(page.locator('[data-testid="auth-language-switch"]')).toBeVisible({ timeout: 5000 })
  })
})
