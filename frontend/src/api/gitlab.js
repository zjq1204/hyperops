import api from '@/config/api'
import { getValidAccessToken, refreshAccessToken } from '@/api/token'

const GITLAB_API_BASE = `${api.apiBaseUrl}/v1/gitlab`

async function getHeaders(options = {}) {
  const accessToken = await getValidAccessToken(options)
  return {
    'Content-Type': 'application/json',
    Authorization: accessToken ? `Bearer ${accessToken}` : ''
  }
}

function normalizePayload(payload) {
  if (payload == null) return null
  if (Object.prototype.hasOwnProperty.call(payload, 'data')) {
    const data = payload.data
    if (data == null) {
      return {
        code: payload.code,
        message: payload.message
      }
    }
    if (Array.isArray(data)) return data
    if (typeof data === 'object') {
      return data.message == null
        ? { ...data, message: payload.message, code: payload.code }
        : data
    }
    return data
  }
  return payload
}

function normalizeCollection(payload) {
  if (Array.isArray(payload)) return payload
  if (payload && Array.isArray(payload.results)) return payload.results
  return []
}

function buildUrl(path, params = {}) {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      query.set(key, value)
    }
  })
  return `${GITLAB_API_BASE}/${path}/${query.toString() ? `?${query.toString()}` : ''}`
}

function extractErrorMessage(payload, response) {
  if (payload?.data?.detail) return payload.data.detail
  if (payload?.data?.message) return payload.data.message
  if (payload?.message) return payload.message

  if (payload && typeof payload === 'object') {
    const firstValue = Object.values(payload)[0]
    if (Array.isArray(firstValue) && firstValue.length > 0) {
      return String(firstValue[0])
    }
    if (typeof firstValue === 'string' && firstValue) {
      return firstValue
    }
  }

  return `HTTP ${response.status}: ${response.statusText}`
}

async function request(url, options = {}) {
  const { _retry, ...fetchOptions } = options
  const response = await fetch(url, {
    ...fetchOptions,
    headers: {
      ...(await getHeaders()),
      ...fetchOptions.headers
    }
  })

  if (response.status === 401 && !_retry) {
    const accessToken = await refreshAccessToken({ redirectOnFailure: true })
    return request(url, {
      ...fetchOptions,
      _retry: true,
      headers: {
        ...fetchOptions.headers,
        Authorization: `Bearer ${accessToken}`
      }
    })
  }

  const rawText = await response.text()
  const payload = rawText ? JSON.parse(rawText) : null

  if (!response.ok) {
    const message = extractErrorMessage(payload, response)
    throw new Error(message)
  }

  return normalizePayload(payload)
}

export const gitlabApi = {
  // Instances
  listInstances: async () =>
    normalizeCollection(
      await request(buildUrl('instances', { page_size: 10000 }))
    ),

  listInstancesPage: (params = {}) => request(buildUrl('instances', params)),

  createInstance: (data) =>
    request(`${GITLAB_API_BASE}/instances/`, {
      method: 'POST',
      body: JSON.stringify(data)
    }),

  updateInstance: (id, data) =>
    request(`${GITLAB_API_BASE}/instances/${id}/`, {
      method: 'PATCH',
      body: JSON.stringify(data)
    }),

  deleteInstance: (id) =>
    request(`${GITLAB_API_BASE}/instances/${id}/`, {
      method: 'DELETE'
    }),

  testConnection: (id) =>
    request(`${GITLAB_API_BASE}/instances/${id}/test_connection/`, {
      method: 'POST'
    }),

  listGroupsFromGitLab: (id) =>
    request(`${GITLAB_API_BASE}/instances/${id}/list_groups/`),

  // Registered Groups
  listGroups: async () =>
    normalizeCollection(
      await request(buildUrl('groups', { page_size: 10000 }))
    ),

  listGroupsPage: (params = {}) => request(buildUrl('groups', params)),

  createGroup: (data) =>
    request(`${GITLAB_API_BASE}/groups/`, {
      method: 'POST',
      body: JSON.stringify(data)
    }),

  updateGroup: (id, data) =>
    request(`${GITLAB_API_BASE}/groups/${id}/`, {
      method: 'PATCH',
      body: JSON.stringify(data)
    }),

  deleteGroup: (id) =>
    request(`${GITLAB_API_BASE}/groups/${id}/`, {
      method: 'DELETE'
    }),

  listProjectsFromGitLab: (groupId) =>
    request(`${GITLAB_API_BASE}/groups/${groupId}/list_projects/`),

  collectProjects: (groupId) =>
    request(`${GITLAB_API_BASE}/groups/${groupId}/collect_projects/`, {
      method: 'POST'
    }),

  // Registered Projects
  listProjects: async () =>
    normalizeCollection(
      await request(buildUrl('projects', { page_size: 10000 }))
    ),

  listProjectsPage: (params = {}) => request(buildUrl('projects', params)),

  updateProject: (id, data) =>
    request(`${GITLAB_API_BASE}/projects/${id}/`, {
      method: 'PATCH',
      body: JSON.stringify(data)
    }),

  deleteProject: (id) =>
    request(`${GITLAB_API_BASE}/projects/${id}/`, {
      method: 'DELETE'
    }),

  collectProject: (id) =>
    request(`${GITLAB_API_BASE}/projects/${id}/collect/`, {
      method: 'POST'
    }),

  bulkCollectProjects: (data) =>
    request(`${GITLAB_API_BASE}/projects/bulk_collect/`, {
      method: 'POST',
      body: JSON.stringify(data)
    }),

  listCollectionRecords: (params = {}) =>
    request(buildUrl('collection-records', params)),

  listOperationRecords: (params = {}) =>
    request(buildUrl('operation-records', params)),

  // Project Labels
  listProjectLabels: (params = {}) =>
    request(buildUrl('project-labels', params)),

  createProjectLabel: (data) =>
    request(`${GITLAB_API_BASE}/project-labels/`, {
      method: 'POST',
      body: JSON.stringify(data)
    }),

  updateProjectLabel: (id, data) =>
    request(`${GITLAB_API_BASE}/project-labels/${id}/`, {
      method: 'PATCH',
      body: JSON.stringify(data)
    }),

  deleteProjectLabel: (id) =>
    request(`${GITLAB_API_BASE}/project-labels/${id}/`, {
      method: 'DELETE'
    }),

  // Branches
  listBranches: (params = {}) => {
    return request(buildUrl('branches', { page_size: 10000, ...params })).then(
      normalizeCollection
    )
  },

  listBranchesPage: (params = {}) => request(buildUrl('branches', params)),

  bulkCreateBranches: (data) =>
    request(`${GITLAB_API_BASE}/branches/bulk_create/`, {
      method: 'POST',
      body: JSON.stringify(data)
    }),

  bulkApplyBranches: (data) =>
    request(`${GITLAB_API_BASE}/branches/bulk_apply/`, {
      method: 'POST',
      body: JSON.stringify(data)
    }),

  bulkDeleteBranches: (branchIds) =>
    request(`${GITLAB_API_BASE}/branches/bulk_delete/`, {
      method: 'POST',
      body: JSON.stringify({ branch_ids: branchIds })
    }),

  bulkProtectBranches: (branchIds) =>
    request(`${GITLAB_API_BASE}/branches/bulk_protect/`, {
      method: 'POST',
      body: JSON.stringify({ branch_ids: branchIds })
    }),

  bulkUnprotectBranches: (branchIds) =>
    request(`${GITLAB_API_BASE}/branches/bulk_unprotect/`, {
      method: 'POST',
      body: JSON.stringify({ branch_ids: branchIds })
    }),

  // Tags
  listTags: (params = {}) => {
    return request(buildUrl('tags', { page_size: 10000, ...params })).then(
      normalizeCollection
    )
  },

  listTagsPage: (params = {}) => request(buildUrl('tags', params)),

  bulkCreateTags: (data) =>
    request(`${GITLAB_API_BASE}/tags/bulk_create/`, {
      method: 'POST',
      body: JSON.stringify(data)
    }),

  bulkDeleteTags: (tagIds) =>
    request(`${GITLAB_API_BASE}/tags/bulk_delete/`, {
      method: 'POST',
      body: JSON.stringify({ tag_ids: tagIds })
    }),

  // Webhooks
  listWebhooks: (params = {}) => {
    return request(buildUrl('webhooks', { page_size: 10000, ...params })).then(
      normalizeCollection
    )
  },

  listWebhooksPage: (params = {}) => request(buildUrl('webhooks', params)),

  createWebhook: (data) =>
    request(`${GITLAB_API_BASE}/webhooks/`, {
      method: 'POST',
      body: JSON.stringify(data)
    }),

  updateWebhook: (id, data) =>
    request(`${GITLAB_API_BASE}/webhooks/${id}/`, {
      method: 'PATCH',
      body: JSON.stringify(data)
    }),

  deleteWebhook: (id) =>
    request(`${GITLAB_API_BASE}/webhooks/${id}/`, {
      method: 'DELETE'
    })
}

export default gitlabApi
