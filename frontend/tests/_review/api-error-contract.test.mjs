import { strict as assert } from 'node:assert'
import { dirname, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const repoRoot = resolve(here, '..', '..')
const errorModule = await import(
  pathToFileURL(resolve(repoRoot, 'src/utils/apiError.js')).href
)

const safeError = errorModule.normalizeApiError({
  response: {
    status: 422,
    data: {
      code: 422,
      message: 'failed',
      data: {
        error_code: 'JENKINS_AUTH_FAILED',
        detail: 'Jenkins 认证失败，请检查用户名或 API Token',
        request_id: 'req-test-123'
      }
    }
  }
})

assert.equal(safeError.code, 'JENKINS_AUTH_FAILED')
assert.equal(safeError.status, 422)
assert.equal(safeError.requestId, 'req-test-123')
assert.equal(safeError.message, 'Jenkins 认证失败，请检查用户名或 API Token')

const legacyRawError = errorModule.normalizeApiError({
  response: {
    status: 400,
    data: {
      message:
        '失败: 401 Client Error: Unauthorized for url: http://192.168.10.250:8080/api/json?tree=jobs'
    }
  }
})

assert.equal(
  legacyRawError.message,
  '认证失败，请检查账号凭据后重试',
  'legacy upstream 401 text must be replaced instead of exposed'
)
assert.equal(
  legacyRawError.message.includes('192.168.10.250'),
  false,
  'internal service URLs must never reach the UI'
)

const validationError = errorModule.normalizeApiError({
  response: {
    status: 400,
    data: {
      data: {
        error_code: 'VALIDATION_ERROR',
        detail: '请检查填写内容',
        field_errors: {
          username: ['该字段不能为空']
        }
      }
    }
  }
})

assert.deepEqual(validationError.fieldErrors, {
  username: ['该字段不能为空']
})
assert.equal(validationError.retryable, false)

const networkError = errorModule.normalizeApiError(
  new TypeError('Failed to fetch')
)
assert.equal(networkError.code, 'NETWORK_ERROR')
assert.equal(networkError.retryable, true)
assert.equal(networkError.message, '网络连接失败，请检查网络后重试')

const sshError = errorModule.normalizeApiError({
  response: {
    status: 400,
    data: {
      data: {
        error_code: 'SSH_AUTH_FAILED',
        detail: 'SSH connection test failed'
      }
    }
  }
})

assert.equal(
  sshError.message,
  'SSH 认证失败，请检查用户名和密码',
  'SSH error codes must use localized UI copy instead of backend detail text'
)

const expiredSshReceipt = errorModule.normalizeApiError({
  response: {
    status: 400,
    data: {
      data: {
        error_code: 'SSH_VERIFICATION_EXPIRED',
        detail: 'SSH verification receipt expired'
      }
    }
  }
})

assert.equal(
  expiredSshReceipt.message,
  'SSH 验证已过期，请重新测试连接',
  'expired SSH receipts must produce actionable localized copy'
)
