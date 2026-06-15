/**
 * Management portal API (admin-only): user list, etc.
 */
import apiClient from '@/api/index'

function extractData(res) {
  const body = res?.data
  if (body && typeof body === 'object' && 'data' in body) return body.data
  return body ?? res
}

export const managementApi = {
  getUsers(params = {}) {
    return apiClient.get('/v1/management/users/', { params }).then(extractData)
  },

  createUser(body) {
    return apiClient.post('/v1/management/users/', body).then(extractData)
  },

  updateUser(userId, body) {
    return apiClient
      .patch(`/v1/management/users/${userId}/`, body)
      .then(extractData)
  },

  getGroups(params = {}) {
    return apiClient.get('/v1/management/groups/', { params }).then(extractData)
  },

  createGroup(body) {
    return apiClient.post('/v1/management/groups/', body).then(extractData)
  },

  updateGroup(groupId, body) {
    return apiClient
      .patch(`/v1/management/groups/${groupId}/`, body)
      .then(extractData)
  },

  getRoles(params = {}) {
    return apiClient.get('/v1/management/roles/', { params }).then(extractData)
  },

  createRole(body) {
    return apiClient.post('/v1/management/roles/', body).then(extractData)
  },

  updateRole(roleId, body) {
    return apiClient
      .patch(`/v1/management/roles/${roleId}/`, body)
      .then(extractData)
  },

  getLdapConfig() {
    return apiClient.get('/v1/management/ldap/config/').then(extractData)
  },

  updateLdapConfig(body) {
    return apiClient.put('/v1/management/ldap/config/', body).then(extractData)
  },

  getLdapInstances(params = {}) {
    return apiClient
      .get('/v1/management/ldap/instances/', { params })
      .then(extractData)
  },

  createLdapInstance(body) {
    return apiClient
      .post('/v1/management/ldap/instances/', body)
      .then(extractData)
  },

  updateLdapInstance(instanceId, body) {
    return apiClient
      .patch(`/v1/management/ldap/instances/${instanceId}/`, body)
      .then(extractData)
  },

  deleteLdapInstance(instanceId) {
    return apiClient.delete(`/v1/management/ldap/instances/${instanceId}/`)
  },

  testLdapConnection(body) {
    return apiClient
      .post('/v1/management/ldap/test-connection/', body)
      .then(extractData)
  },

  testLdapUser(body) {
    return apiClient
      .post('/v1/management/ldap/test-user/', body)
      .then(extractData)
  },

  getLdapGroupMappings(params = {}) {
    return apiClient
      .get('/v1/management/ldap/group-mappings/', { params })
      .then(extractData)
  },

  createLdapGroupMapping(body) {
    return apiClient
      .post('/v1/management/ldap/group-mappings/', body)
      .then(extractData)
  },

  updateLdapGroupMapping(mappingId, body) {
    return apiClient
      .patch(`/v1/management/ldap/group-mappings/${mappingId}/`, body)
      .then(extractData)
  },

  deleteLdapGroupMapping(mappingId) {
    return apiClient.delete(`/v1/management/ldap/group-mappings/${mappingId}/`)
  }
}
