import apiClient from '@/api/index'
import { extractResponseData } from '@/utils/api'

const managementEndpoint = '/v1/object-storage/management'

function normalizeList(payload) {
  if (Array.isArray(payload)) return payload
  if (payload && Array.isArray(payload.results)) return payload.results
  return []
}

function createIdempotencyKey() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID()
  return `admin-${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`
}

function mutationConfig() {
  return { headers: { 'Idempotency-Key': createIdempotencyKey() } }
}

function read(request) {
  return request.then(extractResponseData)
}

function readList(request) {
  return read(request).then(normalizeList)
}

export const objectStorageAdminApi = {
  listTenants() {
    return readList(apiClient.get(`${managementEndpoint}/tenants/`))
  },
  createTenant(body) {
    return read(
      apiClient.post(`${managementEndpoint}/tenants/`, body, mutationConfig())
    )
  },
  updateTenant(tenantId, body) {
    return read(
      apiClient.patch(
        `${managementEndpoint}/tenants/${tenantId}/`,
        body,
        mutationConfig()
      )
    )
  },
  getFeishu(tenantId) {
    return read(
      apiClient.get(`${managementEndpoint}/tenants/${tenantId}/feishu/`)
    )
  },
  saveFeishu(tenantId, body) {
    return read(
      apiClient.put(
        `${managementEndpoint}/tenants/${tenantId}/feishu/`,
        body,
        mutationConfig()
      )
    )
  },
  validateFeishu(tenantId) {
    return read(
      apiClient.post(
        `${managementEndpoint}/tenants/${tenantId}/feishu/validate/`,
        {},
        mutationConfig()
      )
    )
  },
  listResourcePools(tenantId) {
    return readList(
      apiClient.get(`${managementEndpoint}/tenants/${tenantId}/resource-pools/`)
    )
  },
  createResourcePool(tenantId, body) {
    return read(
      apiClient.post(
        `${managementEndpoint}/tenants/${tenantId}/resource-pools/`,
        body,
        mutationConfig()
      )
    )
  },
  updateResourcePool(poolId, body) {
    return read(
      apiClient.patch(
        `${managementEndpoint}/resource-pools/${poolId}/`,
        body,
        mutationConfig()
      )
    )
  },
  validateResourcePool(poolId) {
    return read(
      apiClient.post(
        `${managementEndpoint}/resource-pools/${poolId}/validate/`,
        {},
        mutationConfig()
      )
    )
  },
  listMembers(tenantId) {
    return readList(
      apiClient.get(`${managementEndpoint}/members/`, {
        params: { tenant_id: tenantId }
      })
    )
  },
  listCloudIdentities(tenantId) {
    return readList(
      apiClient.get(`${managementEndpoint}/cloud-identities/`, {
        params: { tenant_id: tenantId }
      })
    )
  },
  listBuckets(tenantId) {
    return readList(
      apiClient.get(`${managementEndpoint}/buckets/`, {
        params: { tenant_id: tenantId }
      })
    )
  },
  listAccessKeys(tenantId) {
    return readList(
      apiClient.get(`${managementEndpoint}/access-keys/`, {
        params: { tenant_id: tenantId }
      })
    )
  },
  listApplications(tenantId) {
    return readList(
      apiClient.get(`${managementEndpoint}/applications/`, {
        params: { tenant_id: tenantId }
      })
    )
  },
  getApplication(applicationId) {
    return read(
      apiClient.get(`${managementEndpoint}/applications/${applicationId}/`)
    )
  },
  retryApplication(applicationId, reason) {
    return read(
      apiClient.post(
        `${managementEndpoint}/applications/${applicationId}/retry/`,
        { reason },
        mutationConfig()
      )
    )
  },
  resolveApplication(applicationId, reason) {
    return read(
      apiClient.post(
        `${managementEndpoint}/applications/${applicationId}/resolve/`,
        { reason },
        mutationConfig()
      )
    )
  },
  revealAccessKey(keyId, reason) {
    const config = mutationConfig()
    config.headers['Cache-Control'] = 'no-store'
    return read(
      apiClient.post(
        `${managementEndpoint}/access-keys/${keyId}/reveal/`,
        { reason },
        config
      )
    )
  },
  suspendMember(memberId, reason) {
    return read(
      apiClient.post(
        `${managementEndpoint}/members/${memberId}/suspend/`,
        { reason },
        mutationConfig()
      )
    )
  },
  reactivateMember(memberId, reason) {
    return read(
      apiClient.post(
        `${managementEndpoint}/members/${memberId}/reactivate/`,
        { reason },
        mutationConfig()
      )
    )
  },
  listAuditEvents(params = {}) {
    return readList(
      apiClient.get(`${managementEndpoint}/audit-events/`, { params })
    )
  }
}

export { createIdempotencyKey }
export default objectStorageAdminApi
