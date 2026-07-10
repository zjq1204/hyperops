export const DEFAULT_UI_LANGUAGE = 'zh-CN'
export const SUPPORTED_UI_LANGUAGES = ['en', 'zh-CN']

export function normalizeUiLanguage(language, fallback = DEFAULT_UI_LANGUAGE) {
  const value = String(language || '').trim()
  const lowerValue = value.toLowerCase()

  if (value === 'zh-CN' || lowerValue === 'zh-cn' || lowerValue.startsWith('zh')) {
    return 'zh-CN'
  }

  if (value === 'en' || lowerValue.startsWith('en')) {
    return 'en'
  }

  return fallback
}

export function detectUiLanguage(fallback = DEFAULT_UI_LANGUAGE) {
  if (typeof navigator === 'undefined') return fallback

  const languages = [
    ...(Array.isArray(navigator.languages) ? navigator.languages : []),
    navigator.language,
    navigator.userLanguage
  ].filter(Boolean)

  for (const language of languages) {
    const normalized = normalizeUiLanguage(language, '')
    if (normalized) return normalized
  }

  return fallback
}

export function getStoredUiLanguage() {
  if (typeof localStorage === 'undefined') return DEFAULT_UI_LANGUAGE

  const stored = localStorage.getItem('userLanguage')
  if (!stored) return DEFAULT_UI_LANGUAGE

  const normalized = normalizeUiLanguage(stored)
  if (stored !== normalized) {
    localStorage.setItem('userLanguage', normalized)
  }

  return normalized
}

export function getRequestUiLanguage() {
  if (typeof localStorage === 'undefined') return DEFAULT_UI_LANGUAGE
  return normalizeUiLanguage(localStorage.getItem('userLanguage'))
}
