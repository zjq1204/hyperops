import { getRequestUiLanguage } from './uiLanguage.js'

const MESSAGE_CATALOG = {
  'zh-CN': {
    AUTHENTICATION_REQUIRED: '登录状态已失效，请重新登录',
    PERMISSION_DENIED: '当前账号没有执行此操作的权限',
    NOT_FOUND: '请求的资源不存在或已被删除',
    VALIDATION_ERROR: '请检查填写内容',
    RATE_LIMITED: '操作过于频繁，请稍后重试',
    NETWORK_ERROR: '网络连接失败，请检查网络后重试',
    REQUEST_TIMEOUT: '请求超时，请稍后重试',
    JENKINS_AUTH_FAILED: 'Jenkins 认证失败，请检查用户名或 API Token',
    JENKINS_PERMISSION_DENIED: '当前 Jenkins 账号没有读取 Job 的权限',
    JENKINS_TIMEOUT: 'Jenkins 响应超时，请稍后重试',
    JENKINS_UNAVAILABLE: 'Jenkins 服务暂时无法访问，请检查地址和网络',
    SSH_AUTH_FAILED: 'SSH 认证失败，请检查用户名和密码',
    SSH_KEY_OR_PROTOCOL_FAILED: 'SSH 密钥无效或服务端协议不兼容',
    SSH_TIMEOUT: 'SSH 连接超时，请检查地址、端口和网络',
    SSH_UNREACHABLE: '无法连接 SSH 服务，请检查地址、端口和防火墙',
    SSH_COMMAND_FAILED: 'SSH 已连接，但远程命令执行失败',
    SSH_VERIFICATION_EXPIRED: 'SSH 验证已过期，请重新测试连接',
    SSH_VERIFICATION_MISMATCH: 'SSH 连接参数已变化，请重新测试连接',
    LEGACY_AUTH_FAILED: '认证失败，请检查账号凭据后重试',
    INTERNAL_ERROR: '服务暂时出现异常，请稍后重试',
    REQUEST_FAILED: '请求处理失败，请稍后重试'
  },
  en: {
    AUTHENTICATION_REQUIRED: 'Your session has expired. Please sign in again.',
    PERMISSION_DENIED: 'You do not have permission to perform this action.',
    NOT_FOUND: 'The requested resource no longer exists.',
    VALIDATION_ERROR: 'Please check the entered information.',
    RATE_LIMITED: 'Too many requests. Please try again later.',
    NETWORK_ERROR:
      'Network connection failed. Check your connection and retry.',
    REQUEST_TIMEOUT: 'The request timed out. Please try again.',
    JENKINS_AUTH_FAILED:
      'Jenkins authentication failed. Check the username or API token.',
    JENKINS_PERMISSION_DENIED: 'The Jenkins account cannot read this job.',
    JENKINS_TIMEOUT: 'Jenkins did not respond in time. Please retry.',
    JENKINS_UNAVAILABLE:
      'Jenkins is currently unavailable. Check its address and network.',
    SSH_AUTH_FAILED:
      'SSH authentication failed. Check the username and password.',
    SSH_KEY_OR_PROTOCOL_FAILED:
      'The SSH key is invalid or the server protocol is incompatible.',
    SSH_TIMEOUT:
      'The SSH connection timed out. Check the address, port, and network.',
    SSH_UNREACHABLE:
      'The SSH service is unreachable. Check the address, port, and firewall.',
    SSH_COMMAND_FAILED:
      'SSH connected, but the remote verification command failed.',
    SSH_VERIFICATION_EXPIRED:
      'The SSH verification expired. Test the connection again.',
    SSH_VERIFICATION_MISMATCH:
      'The SSH connection settings changed. Test the connection again.',
    LEGACY_AUTH_FAILED:
      'Authentication failed. Check the credentials and retry.',
    INTERNAL_ERROR: 'The service encountered an error. Please try again later.',
    REQUEST_FAILED: 'The request could not be completed. Please try again.'
  }
}

const GENERIC_MESSAGES = new Set([
  '',
  'failed',
  'failure',
  'error',
  'request failed',
  '请求失败'
])

const UNSAFE_MESSAGE_PATTERN =
  /(https?:\/\/|client error|server error|traceback|unauthorized for url|forbidden for url|requests\.|exception|c_class|\bat\s+\S+\.(?:js|ts|py):\d+)/i

const FORCE_LOCALIZED_CODES = new Set([
  'NETWORK_ERROR',
  'REQUEST_TIMEOUT',
  'LEGACY_AUTH_FAILED',
  'SSH_AUTH_FAILED',
  'SSH_KEY_OR_PROTOCOL_FAILED',
  'SSH_TIMEOUT',
  'SSH_UNREACHABLE',
  'SSH_COMMAND_FAILED',
  'SSH_VERIFICATION_EXPIRED',
  'SSH_VERIFICATION_MISMATCH'
])

function isObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
}

function localizedMessage(code, locale = getRequestUiLanguage()) {
  const catalog = MESSAGE_CATALOG[locale] || MESSAGE_CATALOG['zh-CN']
  return catalog[code] || catalog.REQUEST_FAILED
}

function extractPayload(error) {
  return error?.response?.data || error?.payload || error?.data || null
}

function extractHeaders(error) {
  return error?.response?.headers || error?.headers || null
}

function extractRequestId(error, payload, body) {
  const headers = extractHeaders(error)
  return (
    body?.request_id ||
    payload?.request_id ||
    headers?.['x-request-id'] ||
    headers?.get?.('x-request-id') ||
    ''
  )
}

function inferErrorCode(error, status, rawMessage) {
  const errorCode = String(error?.code || '').toUpperCase()
  if (
    error instanceof TypeError ||
    errorCode === 'ERR_NETWORK' ||
    /failed to fetch|network error/i.test(rawMessage)
  ) {
    return 'NETWORK_ERROR'
  }
  if (
    errorCode === 'ECONNABORTED' ||
    errorCode === 'ETIMEDOUT' ||
    /timeout|timed out/i.test(rawMessage)
  ) {
    return 'REQUEST_TIMEOUT'
  }
  if (/\b401\b|unauthorized/i.test(rawMessage)) return 'LEGACY_AUTH_FAILED'
  if (status === 401) return 'AUTHENTICATION_REQUIRED'
  if (status === 403) return 'PERMISSION_DENIED'
  if (status === 404) return 'NOT_FOUND'
  if (status === 429) return 'RATE_LIMITED'
  if (status >= 500) return 'INTERNAL_ERROR'
  return 'REQUEST_FAILED'
}

function isSafeDetail(detail) {
  const message = String(detail || '').trim()
  return (
    message &&
    !GENERIC_MESSAGES.has(message.toLowerCase()) &&
    !UNSAFE_MESSAGE_PATTERN.test(message)
  )
}

export class AppError extends Error {
  constructor(message, options = {}) {
    super(message)
    this.name = 'AppError'
    this.code = options.code || 'REQUEST_FAILED'
    this.status = options.status || 0
    this.requestId = options.requestId || ''
    this.fieldErrors = options.fieldErrors || {}
    this.retryable = Boolean(options.retryable)
    this.cause = options.cause
    this.response = options.cause?.response
  }
}

export function normalizeApiError(error, options = {}) {
  if (error instanceof AppError) return error

  const payload = extractPayload(error)
  const body = isObject(payload?.data) ? payload.data : payload
  const status = Number(error?.response?.status || error?.status || 0)
  const rawMessage = String(
    body?.detail ||
      body?.message ||
      payload?.detail ||
      payload?.message ||
      error?.message ||
      ''
  ).trim()
  const explicitCode = body?.error_code || payload?.error_code
  const code = explicitCode || inferErrorCode(error, status, rawMessage)
  const locale = options.locale || getRequestUiLanguage()
  const fallbackMessage =
    options.fallbackMessage || localizedMessage(code, locale)
  const message =
    !FORCE_LOCALIZED_CODES.has(code) && isSafeDetail(rawMessage)
      ? rawMessage
      : fallbackMessage
  const fieldErrors = body?.field_errors || payload?.field_errors || {}
  const retryable =
    options.retryable ??
    [
      'NETWORK_ERROR',
      'REQUEST_TIMEOUT',
      'RATE_LIMITED',
      'INTERNAL_ERROR',
      'JENKINS_TIMEOUT',
      'JENKINS_UNAVAILABLE',
      'SSH_TIMEOUT',
      'SSH_UNREACHABLE'
    ].includes(code)

  return new AppError(message, {
    code,
    status,
    requestId: extractRequestId(error, payload, body),
    fieldErrors,
    retryable,
    cause: error
  })
}

export function getApiErrorMessage(error, fallbackMessage = '') {
  return normalizeApiError(error, { fallbackMessage }).message
}
