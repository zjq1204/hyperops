import axios from 'axios'
import apiConfig from '@/config/api'

const TOKEN_REFRESH_PATH = '/v1/auth/token/refresh'
const TOKEN_REFRESH_SKEW_SECONDS = 5 * 60

let refreshPromise = null

export function isTokenRefreshUrl(url = '') {
  return String(url).includes('/token/refresh')
}

export function clearAuthTokens() {
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
}

export function redirectToLogin() {
  if (window.location.pathname !== '/login') {
    window.location.href = '/login'
  }
}

function decodeJwtPayload(token) {
  try {
    const [, payload] = String(token || '').split('.')
    if (!payload) return null
    const normalized = payload.replace(/-/g, '+').replace(/_/g, '/')
    const padded = normalized.padEnd(
      normalized.length + ((4 - (normalized.length % 4)) % 4),
      '='
    )
    return JSON.parse(window.atob(padded))
  } catch {
    return null
  }
}

function shouldRefreshAccessToken(token, skewSeconds = TOKEN_REFRESH_SKEW_SECONDS) {
  const payload = decodeJwtPayload(token)
  if (!payload?.exp) return true
  const expiresAtMs = Number(payload.exp) * 1000
  return expiresAtMs - Date.now() <= skewSeconds * 1000
}

async function updateStoreToken(accessToken, refreshToken = null) {
  try {
    const { useUserStore } = await import('@/store/user')
    const userStore = useUserStore()
    userStore.setToken(accessToken, refreshToken)
  } catch (storeError) {
    console.warn('Failed to update store token:', storeError)
  }
}

export async function refreshAccessToken({ redirectOnFailure = true } = {}) {
  const refreshToken = localStorage.getItem('refresh_token')
  if (!refreshToken) {
    clearAuthTokens()
    if (redirectOnFailure) redirectToLogin()
    throw new Error('No refresh token available')
  }

  if (!refreshPromise) {
    const refreshApi = axios.create({
      baseURL: apiConfig.apiBaseUrl,
      timeout: apiConfig.timeout,
      headers: {
        'Content-Type': 'application/json'
      },
      withCredentials: true
    })

    refreshPromise = refreshApi
      .post(TOKEN_REFRESH_PATH, { refresh: refreshToken })
      .then(async (response) => {
        const responseData = response.data.data || response.data
        const newAccessToken = responseData.access
        const newRefreshToken = responseData.refresh || null
        if (!newAccessToken) {
          throw new Error('No access token in refresh response')
        }
        localStorage.setItem('access_token', newAccessToken)
        if (newRefreshToken) {
          localStorage.setItem('refresh_token', newRefreshToken)
        }
        await updateStoreToken(newAccessToken, newRefreshToken)
        return newAccessToken
      })
      .catch((error) => {
        clearAuthTokens()
        if (redirectOnFailure) redirectToLogin()
        throw error
      })
      .finally(() => {
        refreshPromise = null
      })
  }

  return refreshPromise
}

export async function getValidAccessToken(options = {}) {
  const {
    forceRefresh = false,
    redirectOnFailure = true,
    skewSeconds = TOKEN_REFRESH_SKEW_SECONDS
  } = options
  const accessToken = localStorage.getItem('access_token')
  const refreshToken = localStorage.getItem('refresh_token')

  if (!refreshToken) return accessToken || ''
  if (!forceRefresh && accessToken && !shouldRefreshAccessToken(accessToken, skewSeconds)) {
    return accessToken
  }

  return refreshAccessToken({ redirectOnFailure })
}
