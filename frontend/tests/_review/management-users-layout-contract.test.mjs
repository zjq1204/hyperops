import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import assert from 'node:assert/strict'

const repoRoot = resolve(process.cwd(), 'frontend')
const source = readFileSync(
  resolve(repoRoot, 'src/admin/pages/Management/Users.vue'),
  'utf8'
)
const styles = readFileSync(
  resolve(repoRoot, 'src/assets/css/flat-console.css'),
  'utf8'
)
const baseLocales = {
  en: JSON.parse(
    readFileSync(resolve(repoRoot, 'src/locales/en.json'), 'utf8')
  ),
  'zh-CN': JSON.parse(
    readFileSync(resolve(repoRoot, 'src/locales/zh-CN.json'), 'utf8')
  )
}
const adminLocales = {
  en: JSON.parse(
    readFileSync(resolve(repoRoot, 'src/admin/locales/en.json'), 'utf8')
  ),
  'zh-CN': JSON.parse(
    readFileSync(resolve(repoRoot, 'src/admin/locales/zh-CN.json'), 'utf8')
  )
}

const hasPath = (value, path) =>
  path.split('.').every((key) => {
    if (!value || !Object.hasOwn(value, key)) return false
    value = value[key]
    return true
  })

assert(
  source.includes('user-list-toolbar') &&
    source.includes('user-list-search') &&
    source.includes('management.userSearchPlaceholder'),
  'user management should expose a focused search toolbar'
)

assert(
  source.includes('user-list-table') &&
    source.includes('user-access-summary') &&
    source.includes('user-list-status'),
  'user management should use a compact identity, access, and status table'
)

assert(
  !source.includes("t('management.ldapLastSyncedAt')") &&
    !source.includes("t('management.dateJoined')"),
  'low-frequency sync and registration fields should not be default table columns'
)

assert(
  source.includes('userSearchEmptyTitle') && source.includes('clearUserSearch'),
  'user management should distinguish a search with no matches from an empty user list'
)

const referencedLocaleKeys = [...source.matchAll(/\bt\('([^']+)'/g)].map(
  (match) => match[1]
)

for (const locale of ['en', 'zh-CN']) {
  for (const key of new Set(referencedLocaleKeys)) {
    assert(
      hasPath(adminLocales[locale], key) || hasPath(baseLocales[locale], key),
      `${locale} locale should define ${key} used by user management`
    )
  }
}

assert(
  /\.user-list-table \.admin-table\s*{[^}]*width:\s*100%;[^}]*table-layout:\s*fixed;/s.test(
    styles
  ),
  'the desktop user table should fill its shell and use predictable column widths'
)

const expectedColumnWidths = ['27%', '12%', '22%', '18%', '12%', '9%']
for (const [index, width] of expectedColumnWidths.entries()) {
  assert(
    styles.includes(
      `.user-list-table :is(th, td):nth-child(${index + 1}) {\n    width: ${width};`
    ),
    `user table column ${index + 1} should use the intended ${width} width`
  )
}

assert(
  /\.user-list-table :is\(th, td\):last-child\s*{[^}]*padding-right:\s*0\.75rem;[^}]*padding-left:\s*0\.75rem;/s.test(
    styles
  ),
  'the action column should reserve enough usable width for its button'
)

assert(
  /\.user-list-table \.admin-table-head\s*{[^}]*font-size:\s*0\.75rem;/s.test(
    styles
  ) &&
    /\.user-list-table \.admin-table-cell\s*{[^}]*font-size:\s*0\.8125rem;/s.test(
      styles
    ),
  'user table headers and body copy should use a consistent compact type scale'
)

assert(
  /@media \(max-width:\s*900px\)[^{]*{[\s\S]*?\.user-list-table \.admin-table\s*{[^}]*min-width:\s*47rem;[^}]*table-layout:\s*auto;/s.test(
    styles
  ),
  'the user table should keep horizontal scrolling on narrow screens'
)

console.log('management users layout contract ok')
