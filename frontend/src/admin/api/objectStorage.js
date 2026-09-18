import apiClient from '@/api/index'
import { extractResponseData } from '@/utils/api'

const endpoint = '/v1/object-storage/management'

function normalizeList(payload) {
  if (Array.isArray(payload)) return payload
  return Array.isArray(payload?.results) ? payload.results : []
}

function read(request) {
  return request.then(extractResponseData)
}

function readList(request) {
  return read(request).then(normalizeList)
}

function idempotencyKey() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID()
  return `admin-${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`
}

function mutationConfig({ noStore = false } = {}) {
  const headers = { 'Idempotency-Key': idempotencyKey() }
  if (noStore) headers['Cache-Control'] = 'no-store'
  return { headers }
}

function action(path, body = {}, options = {}) {
  return read(apiClient.post(`${endpoint}/${path}/`, body, mutationConfig(options)))
}

export const objectStorageAdminApi = {
  getSettings() {
    return read(apiClient.get(`${endpoint}/settings/`))
  },
  updateSettings(body) {
    return read(apiClient.patch(`${endpoint}/settings/`, body, mutationConfig()))
  },
  enablePlatform(resourcePoolId) {
    return action('enable', { resource_pool_id: resourcePoolId })
  },
  listAccessGroups() {
    return readList(apiClient.get(`${endpoint}/access-groups/`))
  },
  getFeishu() {
    return read(apiClient.get(`${endpoint}/feishu-settings/`))
  },
  saveFeishu(body) {
    return read(
      apiClient.patch(`${endpoint}/feishu-settings/`, body, mutationConfig())
    )
  },
  validateFeishu() {
    return action('feishu-settings/validate')
  },
  listResourcePools() {
    return readList(apiClient.get(`${endpoint}/resource-pools/`))
  },
  createResourcePool(body) {
    return read(
      apiClient.post(`${endpoint}/resource-pools/`, body, mutationConfig())
    )
  },
  updateResourcePool(poolId, body) {
    return read(
      apiClient.patch(
        `${endpoint}/resource-pools/${poolId}/`,
        body,
        mutationConfig()
      )
    )
  },
  validateResourcePool(poolId) {
    return action(`resource-pools/${poolId}/validate`)
  },
  listUserQuotas() {
    return readList(apiClient.get(`${endpoint}/user-quotas/`))
  },
  getUserQuota(userId) {
    return read(apiClient.get(`${endpoint}/user-quotas/${userId}/`))
  },
  updateUserQuota(userId, body) {
    return read(
      apiClient.patch(
        `${endpoint}/user-quotas/${userId}/`,
        body,
        mutationConfig()
      )
    )
  },
  listCloudIdentities() {
    return readList(apiClient.get(`${endpoint}/cloud-identities/`))
  },
  getCloudIdentity(identityId) {
    return read(apiClient.get(`${endpoint}/cloud-identities/${identityId}/`))
  },
  listBuckets() {
    return readList(apiClient.get(`${endpoint}/buckets/`))
  },
  getBucket(bucketId) {
    return read(apiClient.get(`${endpoint}/buckets/${bucketId}/`))
  },
  releaseBucket(bucketId, body) {
    return action(`buckets/${bucketId}/release`, body)
  },
  recoverBucket(bucketId, body) {
    return action(`buckets/${bucketId}/recover`, body)
  },
  deleteBucket(bucketId, body) {
    return action(`buckets/${bucketId}/delete`, body)
  },
  retryDeleteBucket(bucketId, body) {
    return action(`buckets/${bucketId}/retry-delete`, body)
  },
  updateBucketConfiguration(bucketId, body) {
    return read(
      apiClient.patch(
        `${endpoint}/buckets/${bucketId}/configuration/`,
        body,
        mutationConfig()
      )
    )
  },
  retryBucketConfiguration(bucketId, body) {
    return action(`buckets/${bucketId}/configuration/retry`, body)
  },
  observeBucketUncertainty(bucketId, body) {
    return action(`buckets/${bucketId}/uncertainty/observe`, body)
  },
  acknowledgeBucketUncertainty(bucketId, body) {
    return action(`buckets/${bucketId}/uncertainty/acknowledge`, body)
  },
  listAccessKeys() {
    return readList(apiClient.get(`${endpoint}/access-keys/`))
  },
  getAccessKey(keyId) {
    return read(apiClient.get(`${endpoint}/access-keys/${keyId}/`))
  },
  disableAccessKey(keyId, body) {
    return action(`access-keys/${keyId}/disable`, body)
  },
  enableAccessKey(keyId, body) {
    return action(`access-keys/${keyId}/enable`, body)
  },
  rotateAccessKey(keyId, body) {
    return action(`access-keys/${keyId}/rotate`, body)
  },
  revokeAccessKey(keyId, body) {
    return action(`access-keys/${keyId}/revoke`, body)
  },
  revealAccessKey(keyId, reason) {
    return action(`access-keys/${keyId}/reveal`, { reason }, { noStore: true })
  },
  listApplications() {
    return readList(apiClient.get(`${endpoint}/applications/`))
  },
  getApplication(applicationId) {
    return read(apiClient.get(`${endpoint}/applications/${applicationId}/`))
  },
  retryApplication(applicationId, reason) {
    return action(`applications/${applicationId}/retry`, { reason })
  },
  listAuditEvents(params = {}) {
    return readList(apiClient.get(`${endpoint}/audit-events/`, { params }))
  },
  getAuditEvent(eventId) {
    return read(apiClient.get(`${endpoint}/audit-events/${eventId}/`))
  },
  suspendUser(userId, reason) {
    return action(`users/${userId}/suspend`, { reason })
  },
  reactivateUser(userId, reason) {
    return action(`users/${userId}/reactivate`, { reason })
  }
}

export { idempotencyKey as createIdempotencyKey }
export default objectStorageAdminApi
