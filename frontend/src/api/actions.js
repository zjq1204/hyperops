import apiClient from '@/api/index'

function extractData(res) {
  const body = res?.data
  if (body && typeof body === 'object' && 'data' in body) return body.data
  return body ?? res
}

function normalizeList(payload) {
  if (Array.isArray(payload)) return payload
  if (payload && Array.isArray(payload.results)) return payload.results
  return []
}

export const actionsApi = {
  listAdminTemplates(params = {}) {
    return apiClient
      .get('/v1/actions/templates/', { params })
      .then(extractData)
  },

  createTemplate(body) {
    return apiClient.post('/v1/actions/templates/', body).then(extractData)
  },

  updateTemplate(templateId, body) {
    return apiClient
      .patch(`/v1/actions/templates/${templateId}/`, body)
      .then(extractData)
  },

  deleteTemplate(templateId) {
    return apiClient.delete(`/v1/actions/templates/${templateId}/`)
  },

  listWorkspaceTemplates() {
    return apiClient
      .get('/v1/actions/workspace/templates/')
      .then(extractData)
      .then(normalizeList)
  },

  listRuns(params = {}) {
    return apiClient.get('/v1/actions/runs/', { params }).then(extractData)
  },

  getRun(runId) {
    return apiClient.get(`/v1/actions/runs/${runId}/`).then(extractData)
  },

  startRun(body) {
    return apiClient.post('/v1/actions/runs/', body).then(extractData)
  },

  approveRun(runId, comment = '') {
    return apiClient
      .post(`/v1/actions/runs/${runId}/approve/`, { comment })
      .then(extractData)
  },

  rejectRun(runId, comment = '') {
    return apiClient
      .post(`/v1/actions/runs/${runId}/reject/`, { comment })
      .then(extractData)
  }
}

export default actionsApi
