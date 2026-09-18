import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import assert from 'node:assert/strict'

const frontendRoot = resolve(process.cwd(), 'frontend')
const sidebar = readFileSync(
  resolve(frontendRoot, 'src/admin/layout/AdminSidebar.vue'),
  'utf8'
)
const styles = readFileSync(
  resolve(frontendRoot, 'src/assets/css/flat-console.css'),
  'utf8'
)

assert(
  /\.layout-admin-sidebar\s*{[^}]*width:\s*18rem\s*!important;[^}]*min-width:\s*18rem;/s.test(
    styles
  ),
  'desktop admin sidebar should reserve enough width for English navigation labels'
)

assert(
  sidebar.includes(':title="section.title"') &&
    sidebar.includes(':title="item.label"') &&
    !sidebar.includes(
      'class="truncate text-[0.98rem] font-semibold text-slate-900"'
    ) &&
    !sidebar.includes('class="min-w-0 flex-1 truncate"'),
  'admin navigation labels should wrap and expose their full text on hover'
)

console.log('admin sidebar layout contract ok')
