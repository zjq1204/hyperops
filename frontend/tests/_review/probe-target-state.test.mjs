import { strict as assert } from 'node:assert'
import {
  matchesProbeFilters,
  probeLabelPairs,
  targetEffectState,
  validateProbeTarget
} from '../../src/admin/pages/Monitoring/probes/targetState.js'

const nodes = [
  { id: 1, name: 'blackbox-beijing', enabled: true },
  { id: 2, name: 'blackbox-disabled', enabled: false }
]
const target = {
  id: 10,
  type: 'http',
  target: 'https://example.com/health',
  probe_node: 1,
  probe_node_name: 'blackbox-beijing',
  enabled: true,
  labels: { env: 'prod', team: 'ops', empty: '' }
}

assert.deepEqual(
  targetEffectState({ ...target, enabled: false }, nodes, { connected: true }),
  { key: 'disabled', error: '' }
)
assert.equal(
  targetEffectState({ ...target, probe_node: null }, nodes, { connected: true })
    .key,
  'incomplete'
)
assert.equal(
  targetEffectState({ ...target, probe_node: 2 }, nodes, { connected: true })
    .key,
  'incomplete'
)
assert.equal(
  targetEffectState(target, nodes, { connected: false }).key,
  'unknown'
)
assert.equal(
  targetEffectState(target, nodes, { connected: true, probe_statuses: {} }).key,
  'pending'
)
assert.equal(
  targetEffectState(target, nodes, {
    connected: true,
    probe_statuses: { 'http:https://example.com/health': { health: 'up' } }
  }).key,
  'effective'
)
assert.deepEqual(
  targetEffectState(target, nodes, {
    connected: true,
    probe_statuses: {
      'http:https://example.com/health': {
        health: 'down',
        last_error: 'request timeout'
      }
    }
  }),
  { key: 'abnormal', error: 'request timeout' }
)

assert.equal(validateProbeTarget('http', 'example.com'), 'invalid_http')
assert.equal(validateProbeTarget('http', 'https://example.com/health'), '')
assert.equal(validateProbeTarget('tcp', 'db.example.com:3306'), '')
assert.equal(validateProbeTarget('tcp', 'db.example.com'), 'invalid_tcp')
assert.equal(validateProbeTarget('icmp', '8.8.8.8'), '')
assert.equal(validateProbeTarget('icmp', 'https://example.com'), 'invalid_icmp')
assert.equal(validateProbeTarget('icmp', 'example.com:443'), 'invalid_icmp')

assert.deepEqual(probeLabelPairs(target.labels), [
  ['env', 'prod'],
  ['team', 'ops']
])

const effectiveState = { key: 'effective', error: '' }
assert.equal(
  matchesProbeFilters(target, effectiveState, {
    search: 'beijing',
    type: '',
    config: '',
    effect: ''
  }),
  true
)
assert.equal(
  matchesProbeFilters(target, effectiveState, {
    search: 'redis',
    type: '',
    config: '',
    effect: ''
  }),
  false
)
assert.equal(
  matchesProbeFilters(target, effectiveState, {
    search: '',
    type: 'tcp',
    config: '',
    effect: ''
  }),
  false
)
assert.equal(
  matchesProbeFilters(target, effectiveState, {
    search: '',
    type: 'http',
    config: 'enabled',
    effect: 'effective'
  }),
  true
)

console.log('probe-target-state.test.mjs: OK')
