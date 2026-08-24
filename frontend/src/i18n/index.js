import { createI18n } from 'vue-i18n'

import en from '../locales/en.json'
import zhCN from '../locales/zh-CN.json'
import adminEn from '../admin/locales/en.json'
import adminZhCN from '../admin/locales/zh-CN.json'
import {
  getStoredUiLanguage,
  normalizeUiLanguage,
  SUPPORTED_UI_LANGUAGES
} from '../utils/uiLanguage'

export { normalizeUiLanguage, SUPPORTED_UI_LANGUAGES }

const isPlainObject = (value) =>
  value !== null && typeof value === 'object' && !Array.isArray(value)

const deepMergeMessages = (base, extra) => {
  const output = { ...base }

  Object.entries(extra).forEach(([key, value]) => {
    if (isPlainObject(value) && isPlainObject(output[key])) {
      output[key] = deepMergeMessages(output[key], value)
      return
    }
    output[key] = value
  })

  return output
}

const buildMessages = (source = {}) => ({
  en: deepMergeMessages(en, adminEn),
  'zh-CN': deepMergeMessages(zhCN, adminZhCN),
  ...source
})

// Create Vue i18n instance
const i18n = createI18n({
  legacy: false,
  locale: getStoredUiLanguage(),
  fallbackLocale: 'en',
  messages: buildMessages()
})

// Reload locale bundles atomically. Vue and JSON HMR updates can arrive in
// separate batches, which otherwise lets new keys fall back to another locale.
if (import.meta.hot) {
  import.meta.hot.accept(
    [
      '../locales/en.json',
      '../locales/zh-CN.json',
      '../admin/locales/en.json',
      '../admin/locales/zh-CN.json'
    ],
    () => window.location.reload()
  )
}

export default i18n
