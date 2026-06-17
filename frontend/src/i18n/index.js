import { createI18n } from 'vue-i18n'

import en from '../locales/en.json'
import zhCN from '../locales/zh-CN.json'
import adminEn from '../admin/locales/en.json'
import adminZhCN from '../admin/locales/zh-CN.json'

export const SUPPORTED_UI_LANGUAGES = ['en', 'zh-CN']

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

export const normalizeUiLanguage = (language) =>
  SUPPORTED_UI_LANGUAGES.includes(language) ? language : 'en'

// Get language from localStorage or default to 'en'.
const getStoredLanguage = () => {
  if (typeof localStorage === 'undefined') return 'en'
  const stored = localStorage.getItem('userLanguage')
  const normalized = normalizeUiLanguage(stored)

  if (stored && stored !== normalized) {
    localStorage.setItem('userLanguage', normalized)
  }

  return normalized
}

const buildMessages = () => ({
  en: deepMergeMessages(en, adminEn),
  'zh-CN': deepMergeMessages(zhCN, adminZhCN)
})

// Create Vue i18n instance
const i18n = createI18n({
  legacy: false,
  locale: getStoredLanguage(),
  fallbackLocale: 'en',
  messages: buildMessages()
})

// HMR: when any of the locale JSON files change, rebuild messages
// and hot-replace them so the running app picks up the new strings
// without a full page reload.
if (import.meta.hot) {
  const reloadMessages = () => {
    const messages = buildMessages()
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
