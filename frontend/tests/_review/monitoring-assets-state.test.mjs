import { strict as assert } from 'node:assert'
import { resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

const modulePath = resolve(
  process.cwd(),
  'src/admin/pages/Monitoring/assets/hostListState.js'
)
const {
  attentionCount,
  componentStatePresentation,
  connectionStatePresentation,
  filterHosts,
  hostMatchesScope,
  hostMatchesSearch,
  isProbeNode
} = await import(pathToFileURL(modulePath).href)

assert.deepEqual(
  componentStatePresentation({
    code: 'healthy',
    installation_status: 'installed',
    runtime_status: 'online'
  }),
  {
    installation: 'installed',
    runtime: 'online',
    showRuntime: true
  }
)
assert.equal(
  connectionStatePresentation({
    status: 'verified',
    matches_current_settings: true
  }),
  'connected'
)
assert.equal(
  connectionStatePresentation({
    status: 'failed',
    matches_current_settings: true
  }),
  'failed'
)
assert.equal(
  connectionStatePresentation({
    status: 'verified',
    matches_current_settings: false
  }),
  'unverified'
)
assert.deepEqual(
  componentStatePresentation({
    code: 'abnormal',
    installation_status: 'installed',
    runtime_status: 'abnormal'
  }),
  {
    installation: 'installed',
    runtime: 'abnormal',
    showRuntime: true
  }
)
assert.deepEqual(
  componentStatePresentation({
    code: 'pending_deployment',
    installation_status: 'not_installed',
    runtime_status: 'not_applicable'
  }),
  {
    installation: 'not_installed',
    runtime: 'not_applicable',
    showRuntime: false
  }
)

const healthyHost = {
  hostname: 'healthy-host',
  address: '10.0.0.21',
  roles: ['collection_host'],
  collection_state: { code: 'healthy' },
  probe_state: { code: 'not_applicable' },
  next_action: { code: 'running_normally' }
}
const pendingHost = {
  hostname: 'pending-host',
  address: '10.0.0.22',
  roles: ['collection_host'],
  collection_state: { code: 'pending_deployment' },
  probe_state: { code: 'not_applicable' },
  next_action: { code: 'verify_ssh' }
}
const probeHost = {
  hostname: 'probe-host',
  address: '10.0.0.23',
  roles: ['collection_host', 'probe_node'],
  collection_state: { code: 'healthy' },
  probe_state: { code: 'abnormal' },
  next_action: { code: 'inspect_probe' }
}

assert.equal(hostMatchesSearch(healthyHost, '10.0.0.21'), true)
assert.equal(hostMatchesSearch(healthyHost, 'HEALTHY'), true)
assert.equal(hostMatchesSearch(healthyHost, 'missing'), false)
assert.equal(hostMatchesScope(healthyHost, 'probe_issue'), false)
assert.equal(hostMatchesScope(probeHost, 'probe_issue'), true)
assert.equal(hostMatchesScope(pendingHost, 'ssh_issue'), true)
assert.equal(isProbeNode(healthyHost), false)
assert.equal(isProbeNode(probeHost), true)
assert.equal(attentionCount([healthyHost, pendingHost, probeHost]), 2)
assert.deepEqual(
  filterHosts([healthyHost, pendingHost, probeHost], {
    query: 'host',
    scope: 'needs_attention'
  }),
  [pendingHost, probeHost]
)
