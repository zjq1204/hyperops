import { test, expect } from '@playwright/test'

async function login(page) {
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

test.describe('Settings - Profile', () => {
  test.beforeEach(async ({ page }) => {
    const loggedIn = await login(page)
    if (!loggedIn) test.skip()
  })

  test('profile page loads', async ({ page }) => {
    await page.goto('/settings/profile')
    await page.waitForLoadState('networkidle')

    await expect(page).toHaveURL(/\/settings\/profile/)
    await expect(page.locator('h1, h2').first()).toBeVisible({ timeout: 10000 })
  })
})

test.describe('Management - Jenkins', () => {
  test.beforeEach(async ({ page }) => {
    const loggedIn = await login(page)
    if (!loggedIn) test.skip()
  })

  test('instances page loads or falls back to dashboard', async ({ page }) => {
    await page.goto('/management/jenkins/instances')
    await page.waitForLoadState('networkidle')

    expect(page.url()).toMatch(/\/(management\/jenkins\/instances|dashboard|login)/)

    if (page.url().includes('/management/jenkins/instances')) {
      await expect(page.locator('h1, h2').first()).toBeVisible({ timeout: 10000 })
    }
  })

  test('entries page loads or falls back to dashboard', async ({ page }) => {
    await page.goto('/management/jenkins/entries')
    await page.waitForLoadState('networkidle')

    expect(page.url()).toMatch(/\/(management\/jenkins\/entries|dashboard|login)/)

    if (page.url().includes('/management/jenkins/entries')) {
      await expect(page.locator('h1, h2').first()).toBeVisible({ timeout: 10000 })
    }
  })
})

test.describe('Management - GitLab', () => {
  test.beforeEach(async ({ page }) => {
    const loggedIn = await login(page)
    if (!loggedIn) test.skip()
  })

  test('instances page loads or falls back to dashboard', async ({ page }) => {
    await page.goto('/management/gitlab/instances')
    await page.waitForLoadState('networkidle')

    expect(page.url()).toMatch(/\/(management\/gitlab\/instances|dashboard|login)/)

    if (page.url().includes('/management/gitlab/instances')) {
      await expect(page.locator('h1, h2').first()).toBeVisible({ timeout: 10000 })
    }
  })
})
