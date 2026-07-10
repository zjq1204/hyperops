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

// HMR: when any of the locale JSON files change, rebuild messages
// and hot-replace them so the running app picks up the new strings
// without a full page reload.
if (import.meta.hot) {
  const reloadMessages = (modules = []) => {
    const [nextEn, nextZhCN, nextAdminEn, nextAdminZhCN] = modules.map(
      (mod) => mod?.default || null
    )
    const messages = buildMessages({
      en: deepMergeMessages(nextEn || en, nextAdminEn || adminEn),
      'zh-CN': deepMergeMessages(nextZhCN || zhCN, nextAdminZhCN || adminZhCN)
    })
    Object.entries(messages).forEach(([locale, value]) => {
      i18n.global.setLocaleMessage(locale, value)
    })
  }

  import.meta.hot.accept(
    [
      '../locales/en.json',
      '../locales/zh-CN.json',
      '../admin/locales/en.json',
      '../admin/locales/zh-CN.json'
    ],
    reloadMessages
  )
}

export default i18n
