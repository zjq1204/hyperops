import apiClient from '@/api/index'

function extractData(res) {
  const body = res?.data
  if (body && typeof body === 'object' && 'data' in body) return body.data
  return body ?? res
}

export const monitoringStackApi = {
  getConfig() {
    return apiClient.get('/v1/monitoring/config/').then(extractData)
  },
  updateConfig(body) {
    return apiClient.put('/v1/monitoring/config/', body).then(extractData)
  },
  getPrometheusHttpSdConfig() {
    return apiClient
      .get('/v1/monitoring/prometheus/http-sd/config/')
      .then(extractData)
  },
  rotatePrometheusHttpSdToken() {
    return apiClient
      .post('/v1/monitoring/prometheus/http-sd/token/')
      .then(extractData)
  },
  getInstallerAssets() {
    return apiClient.get('/v1/monitoring/installer/assets/').then(extractData)
  },
  buildInstallerAssets() {
    return apiClient.post('/v1/monitoring/installer/build/').then(extractData)
  },
  getProfiles() {
    return apiClient.get('/v1/monitoring/profiles/').then(extractData)
  },
  getProbeTargets(params = {}) {
    return apiClient
      .get('/v1/monitoring/probe-targets/', { params })
      .then(extractData)
  },
  getProbeNodes(params = {}) {
    return apiClient
      .get('/v1/monitoring/probe-nodes/', { params })
      .then(extractData)
  },
  getProbeNodeDiscoveries() {
    return apiClient
      .get('/v1/monitoring/prometheus/probe-nodes/discoveries/')
      .then(extractData)
  },
  onboardProbeNode(body) {
    return apiClient
      .post('/v1/monitoring/prometheus/probe-nodes/onboard/', body)
      .then(extractData)
  },
  createProbeNode(body) {
    return apiClient.post('/v1/monitoring/probe-nodes/', body).then(extractData)
  },
  updateProbeNode(id, body) {
    return apiClient
      .patch(`/v1/monitoring/probe-nodes/${id}/`, body)
      .then(extractData)
  },
  deleteProbeNode(id) {
    return apiClient.delete(`/v1/monitoring/probe-nodes/${id}/`)
  },
  createProbeTarget(body) {
    return apiClient.post('/v1/monitoring/probe-targets/', body).then(extractData)
  },
  updateProbeTarget(id, body) {
    return apiClient
      .patch(`/v1/monitoring/probe-targets/${id}/`, body)
      .then(extractData)
  },
  deleteProbeTarget(id) {
    return apiClient.delete(`/v1/monitoring/probe-targets/${id}/`)
  },
  getHosts(params = {}) {
    return apiClient.get('/v1/monitoring/hosts/', { params }).then(extractData)
  },
  testHostConnection(body) {
    return apiClient
      .post('/v1/monitoring/hosts/test-connection/', body)
      .then(extractData)
  },
  getCredentials(params = {}) {
    return apiClient
      .get('/v1/monitoring/credentials/', { params })
      .then(extractData)
  },
  getCredential(id) {
    return apiClient
      .get(`/v1/monitoring/credentials/${id}/`)
      .then(extractData)
  },
  createCredential(body) {
    return apiClient
      .post('/v1/monitoring/credentials/', body)
      .then(extractData)
  },
  rotateCredential(id, body) {
    return apiClient
      .post(`/v1/monitoring/credentials/${id}/rotate/`, body)
      .then(extractData)
  },
  validateCredential(id, body) {
    return apiClient
      .post(`/v1/monitoring/credentials/${id}/validate/`, body)
      .then(extractData)
  },
  activateCredential(id, versionId) {
    return apiClient
      .post(`/v1/monitoring/credentials/${id}/activate/`, {
        version_id: versionId
      })
      .then(extractData)
  },
  archiveCredential(id) {
    return apiClient
      .post(`/v1/monitoring/credentials/${id}/archive/`)
      .then(extractData)
  },
  deleteCredential(id) {
    return apiClient
      .delete(`/v1/monitoring/credentials/${id}/`)
      .then(extractData)
  },
  getAssetsReconciliation() {
    return apiClient
      .get('/v1/monitoring/assets/reconciliation/')
      .then(extractData)
  },
  createHost(body) {
    return apiClient.post('/v1/monitoring/hosts/', body).then(extractData)
  },
  updateHost(id, body) {
    return apiClient.patch(`/v1/monitoring/hosts/${id}/`, body).then(extractData)
  },
  deleteHost(id) {
    return apiClient.delete(`/v1/monitoring/hosts/${id}/`)
  },
  previewAnsible(body) {
    return apiClient.post('/v1/monitoring/ansible/preview/', body).then(extractData)
  },
  getJobs(params = {}) {
    return apiClient
      .get('/v1/monitoring/ansible/jobs/', { params })
      .then(extractData)
  },
  getJob(id) {
    return apiClient
      .get(`/v1/monitoring/ansible/jobs/${id}/`)
      .then(extractData)
  },
  createJob(body) {
    return apiClient.post('/v1/monitoring/ansible/jobs/', body).then(extractData)
  },
  retryJob(id) {
    return apiClient
      .post(`/v1/monitoring/ansible/jobs/${id}/retry/`)
      .then(extractData)
  },
  getPrometheusTargetsSummary() {
    return apiClient
      .get('/v1/monitoring/prometheus/targets/summary/')
      .then(extractData)
  },
  getBlackboxInstances() {
    return apiClient
      .get('/v1/monitoring/blackbox/instances/')
      .then(extractData)
  },
  getN9eSummary() {
    return apiClient.get('/v1/monitoring/n9e/summary/').then(extractData)
  },
  syncGovernance(source = 'all') {
    return apiClient
      .post('/v1/monitoring/governance/sync/', { source })
      .then(extractData)
  },
  getGovernanceOverview() {
    return apiClient
      .get('/v1/monitoring/governance/overview/')
      .then(extractData)
  },
  getGovernanceFindings(params = {}) {
    return apiClient
      .get('/v1/monitoring/governance/findings/', { params })
      .then(extractData)
  },
  resolveGovernanceFinding(id, body) {
    return apiClient
      .post(`/v1/monitoring/governance/findings/${id}/resolve/`, body)
      .then(extractData)
  },
  getRules() {
    return apiClient.get('/v1/monitoring/rules/').then(extractData)
  },
  getRule(name) {
    return apiClient.get(`/v1/monitoring/rules/${name}/`).then(extractData)
  },
  getRuleDiff(name, params = {}) {
    return apiClient
      .get(`/v1/monitoring/rules/${name}/diff/`, { params })
      .then(extractData)
  },
  createRule(name, body) {
    return apiClient.post(`/v1/monitoring/rules/${name}/`, body).then(extractData)
  },
  updateRule(name, body) {
    return apiClient.patch(`/v1/monitoring/rules/${name}/`, body).then(extractData)
  },
  deleteRule(name, body) {
    return apiClient
      .delete(`/v1/monitoring/rules/${name}/`, { data: body })
      .then(extractData)
  },
  discoverN9e(body) {
    return apiClient.post('/v1/monitoring/n9e/discover/', body).then(extractData)
  },
  importN9eRules(body) {
    return apiClient.post('/v1/monitoring/n9e/import-rules/', body).then(extractData)
  }
}
