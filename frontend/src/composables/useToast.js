import { reactive } from 'vue'
import { normalizeApiError } from '@/utils/apiError'

const MAX_VISIBLE_TOASTS = 3
const toastState = reactive({ items: [] })
const timers = new Map()
let nextToastId = 1

function clearTimer(id) {
  const timer = timers.get(id)
  if (timer) clearTimeout(timer)
  timers.delete(id)
}

function remove(id) {
  clearTimer(id)
  const index = toastState.items.findIndex((item) => item.id === id)
  if (index >= 0) toastState.items.splice(index, 1)
}

function startAutoHide(id, duration) {
  if (!duration || duration <= 0) return
  clearTimer(id)
  timers.set(
    id,
    setTimeout(() => remove(id), duration)
  )
}

function enqueueToast(message, type, duration, options = {}) {
  const content = String(message || '').trim()
  if (!content) return null

  const dedupeKey = options.dedupeKey || `${type}:${content}`
  const existing = toastState.items.find((item) => item.dedupeKey === dedupeKey)
  if (existing) {
    existing.createdAt = Date.now()
    startAutoHide(existing.id, duration)
    return existing.id
  }

  const item = {
    id: nextToastId++,
    type,
    title: options.title || '',
    message: content,
    requestId: options.requestId || '',
    action: options.action || null,
    duration,
    dedupeKey,
    createdAt: Date.now()
  }
  toastState.items.push(item)
  while (toastState.items.length > MAX_VISIBLE_TOASTS) {
    remove(toastState.items[0].id)
  }
  startAutoHide(item.id, duration)
  return item.id
}

function showError(error, duration = 6000, options = {}) {
  const appError =
    typeof error === 'string'
      ? normalizeApiError(new Error(error), options)
      : normalizeApiError(error, options)
  return enqueueToast(appError.message, 'error', duration, {
    ...options,
    requestId: options.requestId || appError.requestId
  })
}

export function useToast() {
  return {
    showToast: (message, type = 'success', duration, options = {}) =>
      type === 'error'
        ? showError(message, duration || 6000, options)
        : enqueueToast(
            message,
            type,
            duration || (type === 'warning' ? 5000 : 3000),
            options
          ),
    showSuccess: (message, duration = 3000, options = {}) =>
      enqueueToast(message, 'success', duration, options),
    showError,
    showWarning: (message, duration = 5000, options = {}) =>
      enqueueToast(message, 'warning', duration, options),
    showInfo: (message, duration = 4000, options = {}) =>
      enqueueToast(message, 'info', duration, options),
    remove,
    hide: remove,
    clear: () => [...toastState.items].forEach((item) => remove(item.id)),
    state: toastState
  }
}
