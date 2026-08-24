const COMPONENTS = ['categraf', 'blackbox']

function emptyComponentSummary() {
  return {
    latest: null,
    attempt_count: 0,
    history: []
  }
}

function normalizeComponentSummary(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return emptyComponentSummary()
  }

  const history = Array.isArray(value.history)
    ? value.history.filter((item) => item && typeof item === 'object')
    : []
  const latest = value.latest && typeof value.latest === 'object'
    ? value.latest
    : history[0] || null
  const attemptCount = Number(value.attempt_count)

  return {
    latest,
    attempt_count: Number.isFinite(attemptCount) && attemptCount >= 0
      ? attemptCount
      : history.length,
    history
  }
}

export function normalizeHostSummaries(payload) {
  const rows = Array.isArray(payload)
    ? payload
    : Array.isArray(payload?.results)
      ? payload.results
      : []

  return rows
    .filter((row) => row && typeof row === 'object' && !Array.isArray(row))
    .map((row) => ({
      host_id: row.host_id ?? row.id ?? null,
      hostname: String(row.hostname || ''),
      address: String(row.address || ''),
      components: Object.fromEntries(
        COMPONENTS.map((component) => [
          component,
          normalizeComponentSummary(row.components?.[component])
        ])
      )
    }))
}

export async function keepLogPinnedAfterRender({
  element,
  getCurrentElement,
  nextRender
}) {
  if (!element) return

  const nearBottom =
    element.scrollHeight - element.scrollTop - element.clientHeight < 48
  if (!nearBottom) return

  await nextRender()
  if (getCurrentElement() !== element) return

  element.scrollTop = element.scrollHeight
}
