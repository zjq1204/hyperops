import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import assert from 'node:assert/strict'

const frontendRoot = resolve(process.cwd(), 'frontend')
const switcher = readFileSync(
  resolve(frontendRoot, 'src/components/ui/LanguageSwitcher.vue'),
  'utf8'
)
const authPage = readFileSync(
  resolve(frontendRoot, 'src/pages/Auth.vue'),
  'utf8'
)

assert(
  !/[🇺🇸🇨🇳]/u.test(switcher),
  'language switcher should use UI-consistent language marks instead of flag emoji'
)

assert(
  switcher.includes('aria-haspopup="menu"') &&
    switcher.includes(':aria-expanded="showDropdown"') &&
    switcher.includes('role="menu"') &&
    switcher.includes('role="menuitemradio"') &&
    switcher.includes(':aria-checked="isSelected(lang.value)"'),
  'language switcher should expose its menu and selected state to assistive technology'
)

assert(
  switcher.includes("label: 'English'") &&
    switcher.includes("label: '简体中文'") &&
    switcher.includes('language-switcher__check'),
  'language options should use full names and a clear selected indicator'
)

assert(
  switcher.includes(':aria-label="triggerLabel"') &&
    !switcher.includes('language-switcher__current') &&
    !switcher.includes('language-switcher__chevron'),
  'the header trigger should be an accessible icon button without a competing locale badge'
)

assert(
  switcher.includes("event.key !== 'Escape'") &&
    switcher.includes('triggerRef.value?.focus()'),
  'Escape should close the menu and restore focus to its trigger'
)

assert(
  switcher.includes('width: 2.75rem') &&
    switcher.includes('height: 2.75rem') &&
    switcher.includes('border-color: transparent') &&
    switcher.includes('width: 11rem') &&
    switcher.includes('border-radius: 0.375rem'),
  'language control should use mature header sizing and compact flat menu geometry'
)

assert(
  !authPage.includes('.auth-card__lang :deep(button)'),
  'login page should not broadly restyle every button inside the shared language switcher'
)

console.log('language switcher contract ok')
