function normalizedNodeId(value) {
  if (value && typeof value === 'object') return String(value.id || '')
  return String(value || '')
}

export function targetEffectState(target, nodes, prometheusSummary) {
  if (!target?.enabled) return { key: 'disabled', error: '' }

  const nodeId = normalizedNodeId(target?.probe_node)
  const node = (nodes || []).find((item) => String(item.id) === nodeId)
  if (!node || !node.enabled) return { key: 'incomplete', error: '' }

  if (!prometheusSummary?.connected) {
    return {
      key: 'unknown',
      error: String(prometheusSummary?.error || '')
    }
  }

  const identity = `${target.type}:${target.target}`
  const matched = prometheusSummary?.probe_statuses?.[identity]
  if (!matched) return { key: 'pending', error: '' }
  if (matched.health === 'up') return { key: 'effective', error: '' }
  if (matched.health === 'down') {
    return { key: 'abnormal', error: String(matched.last_error || '') }
  }
  return { key: 'unknown', error: String(matched.last_error || '') }
}

export function validateProbeTarget(type, value) {
  const target = String(value || '').trim()
  if (!target) return 'required'

  if (type === 'http') {
    try {
      const parsed = new URL(target)
      return ['http:', 'https:'].includes(parsed.protocol) ? '' : 'invalid_http'
    } catch (_error) {
      return 'invalid_http'
    }
  }

  if (type === 'tcp') {
    const matched = target.match(/^(?:\[[^\]]+\]|[^:\s]+):(\d{1,5})$/)
    if (!matched) return 'invalid_tcp'
    const port = Number(matched[1])
    return port >= 1 && port <= 65535 ? '' : 'invalid_tcp'
  }

  if (type === 'icmp') {
    return /\s|:\/\/|:/.test(target) ? 'invalid_icmp' : ''
  }

  return 'required'
}

export function probeLabelPairs(labels) {
  return Object.entries(labels || {})
    .filter(([, value]) => value !== null && String(value).trim() !== '')
    .map(([key, value]) => [key, String(value)])
}

export function matchesProbeFilters(target, state, filters) {
  if (filters.type && target.type !== filters.type) return false
  if (filters.config === 'enabled' && !target.enabled) return false
  if (filters.config === 'disabled' && target.enabled) return false
  if (filters.effect && state.key !== filters.effect) return false

  const search = String(filters.search || '')
    .trim()
    .toLowerCase()
  if (!search) return true
  const labelText = probeLabelPairs(target.labels).flat().join(' ')
  const searchable = [
    target.target,
    target.probe_node_name,
    target.blackbox_address,
    labelText
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase()
  return searchable.includes(search)
}
