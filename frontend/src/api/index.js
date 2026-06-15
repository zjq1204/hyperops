import axios from 'axios'
import apiConfig from '@/config/api'
import {
  clearAuthTokens,
  getValidAccessToken,
  isTokenRefreshUrl,
  redirectToLogin,
  refreshAccessToken
} from '@/api/token'

function getCookie(name) {
  const value = `; ${document.cookie}`
  const parts = value.split(`; ${name}=`)
  if (parts.length === 2) return parts.pop().split(';').shift()
  return null
}

const api = axios.create({
  baseURL: apiConfig.apiBaseUrl,
  timeout: apiConfig.timeout,
  headers: {
    'Content-Type': 'application/json'
  },
  withCredentials: true
})

api.interceptors.request.use(
  async (config) => {
    if (!isTokenRefreshUrl(config.url)) {
      const token = await getValidAccessToken({ redirectOnFailure: true })
      if (token) {
        config.headers.Authorization = `Bearer ${token}`
      }
    }

    const csrfToken = getCookie('csrftoken')
    if (csrfToken) {
      config.headers['X-CSRFToken'] = csrfToken
    }

    const uiLanguage = localStorage.getItem('userLanguage') || 'en'
    config.headers['Accept-Language'] = uiLanguage

    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor
api.interceptors.response.use(
  (response) => {
    return response
  },
  async (error) => {
    const originalRequest = error.config

    // Handle 401 Unauthorized errors
    if (error.response?.status === 401 && !originalRequest._retry) {
      // If refresh endpoint returns 401, token is invalid, redirect to login
      if (isTokenRefreshUrl(originalRequest.url)) {
        clearAuthTokens()
        redirectToLogin()
        return Promise.reject(error)
      }

      originalRequest._retry = true

      try {
        const newAccessToken = await refreshAccessToken({
          redirectOnFailure: true
        })
        originalRequest.headers.Authorization = `Bearer ${newAccessToken}`
        return api(originalRequest)
      } catch (refreshError) {
        return Promise.reject(refreshError)
      }
    }

    return Promise.reject(error)
  }
)

export default api
