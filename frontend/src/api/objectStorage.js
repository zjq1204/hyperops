import apiClient from '@/api/index'

const bucketsEndpoint = '/v1/object-storage/workspace/buckets/'
const applicationsEndpoint = '/v1/object-storage/workspace/applications/'
const credentialsEndpoint = '/v1/object-storage/workspace/credentials/'
const overviewEndpoint = '/v1/object-storage/workspace/overview/'

function extractData(response) {
  const body = response?.data
  if (body && typeof body === 'object' && 'data' in body) return body.data
  return body ?? response
}

function normalizeList(payload) {
  if (Array.isArray(payload)) return payload
  if (payload && Array.isArray(payload.results)) return payload.results
  return []
}

function createIdempotencyKey() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID()

  const random = Math.random().toString(36).slice(2)
  return `web-${Date.now().toString(36)}-${random}`
}

function mutationConfig() {
  return {
    headers: {
      'Idempotency-Key': createIdempotencyKey()
    }
  }
}

export const objectStorageReadCapabilities = Object.freeze({
  overview: true,
  applicationList: true,
  credentialList: false
})

export const objectStorageApi = {
  getOverview() {
    return apiClient.get(overviewEndpoint).then(extractData)
  },

  listBuckets() {
    return apiClient.get(bucketsEndpoint).then(extractData).then(normalizeList)
  },

  releaseBucket(bucketId, body) {
    return apiClient
      .post(`${bucketsEndpoint}${bucketId}/release/`, body, mutationConfig())
      .then(extractData)
  },

  createApplication(body) {
    return apiClient
      .post(applicationsEndpoint, body, mutationConfig())
      .then(extractData)
  },

  listApplications() {
    return apiClient
      .get(applicationsEndpoint)
      .then(extractData)
      .then(normalizeList)
  },

  getApplicationDetail(applicationId) {
    return apiClient
      .get(`${applicationsEndpoint}${applicationId}/`)
      .then(extractData)
  },

  retryApplication(applicationId) {
    return apiClient
      .post(
        `${applicationsEndpoint}${applicationId}/retry/`,
        {},
        mutationConfig()
      )
      .then(extractData)
  },

  getApplicationDeliveryToken(applicationId) {
    return apiClient
      .get(`${applicationsEndpoint}${applicationId}/delivery-token/`, {
        headers: { 'Cache-Control': 'no-store' }
      })
      .then(extractData)
  },

  getCredentialSummary(keyId) {
    return apiClient.get(`${credentialsEndpoint}${keyId}/`).then(extractData)
  },

  getCredentialDetail(keyId) {
    return this.getCredentialSummary(keyId)
  },

  deliverCredentials(token) {
    return apiClient
      .post(`${credentialsEndpoint}deliver/`, { token }, mutationConfig())
      .then(extractData)
  },

  getRotationPreview() {
    return apiClient
      .get(`${credentialsEndpoint}rotation-preview/`)
      .then(extractData)
  },

  rotateCredentials(body) {
    return apiClient
      .post(`${credentialsEndpoint}rotation-preview/`, body, mutationConfig())
      .then(extractData)
  }
}

export default objectStorageApi
