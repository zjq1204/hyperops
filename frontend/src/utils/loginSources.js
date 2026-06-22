const STOP_FALLBACK_CODES = new Set(['ldap_account_conflict'])

export function buildLoginAttempts({ credentials, ldapProviders = [] }) {
  const baseCredentials = {
    username: credentials.username,
    password: credentials.password
  }

  const attempts = [
    {
      label: 'local',
      credentials: {
        ...baseCredentials,
        auth_source: 'local',
        ldap_instance_id: null
      }
    }
  ]

  ldapProviders.forEach((provider) => {
    const providerId = Number(provider?.id)
    if (!Number.isFinite(providerId)) return

    attempts.push({
      label: `ldap:${providerId}`,
      credentials: {
        ...baseCredentials,
        auth_source: 'ldap',
        ldap_instance_id: providerId
      }
    })
  })

  return attempts
}

export function shouldContinueLoginFallback({ code, hasNextAttempt }) {
  if (!hasNextAttempt) return false
  if (STOP_FALLBACK_CODES.has(code)) return false
  return true
}
