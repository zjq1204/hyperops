import api from '@/config/api'
import { getValidAccessToken, refreshAccessToken } from '@/api/token'
import { normalizeApiError } from '@/utils/apiError'

const JENKINS_API_BASE = `${api.apiBaseUrl}/v1/jenkins`

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
    throw normalizeApiError({
      response: {
        status: response.status,
        data: payload,
        headers: response.headers
      }
    })
  }

  return normalizePayload(payload)
}

// Jenkins Instances
export const jenkinsApi = {
  // Instances
  listInstances: async () =>
    normalizeCollection(await request(`${JENKINS_API_BASE}/instances/`)),

  createInstance: (data) =>
    request(`${JENKINS_API_BASE}/instances/`, {
      method: 'POST',
      body: JSON.stringify(data)
    }),

  updateInstance: (id, data) =>
    request(`${JENKINS_API_BASE}/instances/${id}/`, {
      method: 'PATCH',
      body: JSON.stringify(data)
    }),

  deleteInstance: (id) =>
    request(`${JENKINS_API_BASE}/instances/${id}/`, {
      method: 'DELETE'
    }),

  testConnection: (id) =>
    request(`${JENKINS_API_BASE}/instances/${id}/test_connection/`, {
      method: 'POST'
    }),

  validateConnection: (data) =>
    request(`${JENKINS_API_BASE}/instances/validate_connection/`, {
      method: 'POST',
      body: JSON.stringify(data)
    }),

  listJobs: async (id, options = {}) => {
    const query = new URLSearchParams()
    if (options.forceRefresh) {
      query.set('force_refresh', 'true')
    }
    const suffix = query.toString() ? `?${query.toString()}` : ''
    return request(`${JENKINS_API_BASE}/instances/${id}/jobs/${suffix}`)
  },

  fetchParams: (id, jobName) =>
    request(`${JENKINS_API_BASE}/instances/${id}/fetch_params/`, {
      method: 'POST',
      body: JSON.stringify({ job_name: jobName })
    }),

  // Trigger Entries
  listEntries: async () =>
    normalizeCollection(await request(`${JENKINS_API_BASE}/entries/`)),

  createEntry: (data) =>
    request(`${JENKINS_API_BASE}/entries/`, {
      method: 'POST',
      body: JSON.stringify(data)
    }),

  updateEntry: (id, data) =>
    request(`${JENKINS_API_BASE}/entries/${id}/`, {
      method: 'PATCH',
      body: JSON.stringify(data)
    }),

  deleteEntry: (id) =>
    request(`${JENKINS_API_BASE}/entries/${id}/`, {
      method: 'DELETE'
    }),

  getEntryParams: (id) => request(`${JENKINS_API_BASE}/entries/${id}/params/`),

  getEntryAdminParams: (id) =>
    request(`${JENKINS_API_BASE}/entries/${id}/admin_params/`),

  // Records
  listRecords: (params = {}) => {
    const query = new URLSearchParams(params).toString()
    return request(`${JENKINS_API_BASE}/records/${query ? `?${query}` : ''}`)
  },

  triggerBuild: (entryId, params = {}) =>
    request(`${JENKINS_API_BASE}/records/trigger/`, {
      method: 'POST',
      body: JSON.stringify({ entry_id: entryId, params })
    }),

  refreshStatus: (recordId) =>
    request(`${JENKINS_API_BASE}/records/${recordId}/refresh_status/`, {
      method: 'POST'
    }),

  // User entries
  getUserEntries: async () =>
    normalizeCollection(await request(`${JENKINS_API_BASE}/user/entries/`)),

  getUserNotificationPreferences: async () =>
    normalizeCollection(
      await request(`${JENKINS_API_BASE}/user/notification-preferences/`)
    ),

  saveUserNotificationPreferences: (preferences) =>
    request(`${JENKINS_API_BASE}/user/notification-preferences/`, {
      method: 'PUT',
      body: JSON.stringify({ preferences })
    }),

  // Resource labels (CRUD)
  listResourceLabels: async () =>
    normalizeCollection(await request(`${JENKINS_API_BASE}/resource-labels/`)),

  createResourceLabel: (data) =>
    request(`${JENKINS_API_BASE}/resource-labels/`, {
      method: 'POST',
      body: JSON.stringify(data)
    }),

  updateResourceLabel: (id, data) =>
    request(`${JENKINS_API_BASE}/resource-labels/${id}/`, {
      method: 'PATCH',
      body: JSON.stringify(data)
    }),

  deleteResourceLabel: (id) =>
    request(`${JENKINS_API_BASE}/resource-labels/${id}/`, {
      method: 'DELETE'
    }),

  // Per-job label assignment
  assignJobLabels: (instanceId, fullName, labelIds) => {
    const encoded = encodeURIComponent(fullName)
    return request(
      `${JENKINS_API_BASE}/instances/${instanceId}/jobs/${encoded}/labels/`,
      {
        method: 'PUT',
        body: JSON.stringify({ label_ids: labelIds })
      }
    )
  },

  bulkAddJobLabel: (instanceId, labelId, fullNames) =>
    request(
      `${JENKINS_API_BASE}/instances/${instanceId}/jobs/bulk-add-label/`,
      {
        method: 'POST',
        body: JSON.stringify({
          label_id: labelId,
          full_names: fullNames
        })
      }
    )
}

export default jenkinsApi
