import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import assert from 'node:assert/strict'

const repoRoot = resolve(process.cwd(), 'frontend')
const source = readFileSync(
  resolve(repoRoot, 'src/admin/pages/Actions/Templates.vue'),
  'utf8'
)
const zhCN = JSON.parse(
  readFileSync(resolve(repoRoot, 'src/admin/locales/zh-CN.json'), 'utf8')
)
const en = JSON.parse(
  readFileSync(resolve(repoRoot, 'src/admin/locales/en.json'), 'utf8')
)
const baseZhCN = JSON.parse(
  readFileSync(resolve(repoRoot, 'src/locales/zh-CN.json'), 'utf8')
)
const baseEn = JSON.parse(
  readFileSync(resolve(repoRoot, 'src/locales/en.json'), 'utf8')
)

const hasPath = (value, path) =>
  path.split('.').every((key) => {
    if (!value || !Object.hasOwn(value, key)) return false
    value = value[key]
    return true
  })

assert(
  !source.includes(':eyebrow="t(\'adminPages.actionTemplates.eyebrow\')"'),
  'template list should not render a decorative eyebrow above the page title'
)

assert(
  source.includes('action-template-toolbar') &&
    source.includes('action-template-search'),
  'template list should group count, search, refresh, and create actions into a focused toolbar'
)

assert(
  source.includes('action-template-row-actions') &&
    source.includes('action-template-row-action--primary') &&
    source.includes('action-template-row-action--danger'),
  'row operations should use a quiet action hierarchy instead of three equal buttons'
)

assert(
  source.includes('loadingTemplates') &&
    source.includes('actionTemplates.search.emptyTitle'),
  'initial loading and search-empty states should be distinct from a genuinely empty template list'
)

assert(
  source.includes('actionTemplates.listSummary') &&
    typeof zhCN.adminPages.actionTemplates.listSummary === 'string' &&
    typeof en.adminPages.actionTemplates.listSummary === 'string',
  'template list summary should use a dedicated string key in both locale bundles'
)

assert(
  typeof zhCN.adminPages.actionTemplates.summary === 'object' &&
    typeof en.adminPages.actionTemplates.summary === 'object',
  'flow-preview summary translations must remain an object and must not collide with list copy'
)

const referencedLocaleKeys = [...source.matchAll(/\bt\('([^']+)'/g)].map(
  (match) => match[1]
)

for (const [locale, adminMessages, baseMessages] of [
  ['zh-CN', zhCN, baseZhCN],
  ['en', en, baseEn]
]) {
  for (const key of new Set(referencedLocaleKeys)) {
    assert(
      hasPath(adminMessages, key) || hasPath(baseMessages, key),
      `${locale} locale should define ${key} used by action templates`
    )
  }
}

console.log('action template list layout contract ok')
