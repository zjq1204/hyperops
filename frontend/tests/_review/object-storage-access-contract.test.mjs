import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const adminRoutes = fs.readFileSync(
  new URL('../../src/admin/routes.js', import.meta.url),
  'utf8'
)
const adminSidebar = fs.readFileSync(
  new URL('../../src/admin/layout/AdminSidebar.vue', import.meta.url),
  'utf8'
)

test('object storage management route requires a superuser', () => {
  const routeStart = adminRoutes.indexOf(
    "path: '/management/object-storage/overview'"
  )
  const routeEnd = adminRoutes.indexOf('\n  }', routeStart)
  const routeDefinition = adminRoutes.slice(routeStart, routeEnd)

  assert.notEqual(routeStart, -1)
  assert.match(routeDefinition, /requiresSuperuser:\s*true/)
})

test('object storage management navigation requires a superuser', () => {
  const sectionStart = adminSidebar.indexOf("key: 'object-storage'")
  const sectionEnd = adminSidebar.indexOf('\n  }\n])', sectionStart)
  const sectionDefinition = adminSidebar.slice(sectionStart, sectionEnd)

  assert.notEqual(sectionStart, -1)
  assert.match(sectionDefinition, /requiresSuperuser:\s*true/)
  assert.match(
    adminSidebar,
    /section\.requiresSuperuser\s*&&\s*!currentUser\.value\?\.is_superuser/
  )
})
