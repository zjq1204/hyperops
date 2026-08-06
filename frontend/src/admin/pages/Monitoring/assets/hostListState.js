const ISSUE_COMPONENT_STATES = new Set([
  'pending_deployment',
  'deployment_failed',
  'abnormal',
  'unknown'
])

const LEGACY_COMPONENT_PRESENTATION = {
  healthy: ['installed', 'online'],
  abnormal: ['installed', 'abnormal'],
  deploying: ['installing', 'not_applicable'],
  deployment_failed: ['failed', 'not_applicable'],
  pending_deployment: ['not_installed', 'not_applicable'],
  unknown: ['unknown', 'not_applicable'],
  not_applicable: ['not_applicable', 'not_applicable']
}

export function componentStatePresentation(state) {
  const fallback =
    LEGACY_COMPONENT_PRESENTATION[state?.code] ||
    LEGACY_COMPONENT_PRESENTATION.unknown
  const installation = state?.installation_status || fallback[0]
  const runtime = state?.runtime_status || fallback[1]
  return {
    installation,
    runtime,
    showRuntime: installation === 'installed' && runtime !== 'not_applicable'
  }
}

export function connectionStatePresentation(verification) {
  if (!verification?.matches_current_settings) return 'unverified'
  if (verification.status === 'verified') return 'connected'
  if (verification.status === 'failed') return 'failed'
  return 'unverified'
}

export function isProbeNode(host) {
  return Array.isArray(host?.roles) && host.roles.includes('probe_node')
}

export function hostMatchesSearch(host, query) {
  const needle = String(query || '')
    .trim()
    .toLowerCase()
  if (!needle) return true
  return [host?.hostname, host?.address].some((value) =>
    String(value || '')
      .toLowerCase()
      .includes(needle)
  )
}

export function hostMatchesScope(host, scope) {
  if (!scope || scope === 'all') return true
  const action = host?.next_action?.code || 'status_unconfirmed'
  if (scope === 'needs_attention') {
    return !['running_normally', 'deployment_in_progress'].includes(action)
  }
  if (scope === 'healthy') return action === 'running_normally'
  if (scope === 'ssh_issue') {
    return ['verify_ssh', 'fix_ssh'].includes(action)
  }
  if (scope === 'collection_issue') {
    return ISSUE_COMPONENT_STATES.has(host?.collection_state?.code)
  }
  if (scope === 'probe_issue') {
    return (
      isProbeNode(host) && ISSUE_COMPONENT_STATES.has(host?.probe_state?.code)
    )
  }
  return false
}

export function filterHosts(hosts, { query = '', scope = 'all' } = {}) {
  return (hosts || []).filter(
    (host) => hostMatchesSearch(host, query) && hostMatchesScope(host, scope)
  )
}

export function attentionCount(hosts) {
  return (hosts || []).filter((host) =>
    hostMatchesScope(host, 'needs_attention')
  ).length
}
