import { strict as assert } from 'node:assert'
import {
  buildLoginAttempts,
  shouldContinueLoginFallback
} from '../../src/utils/loginSources.js'

const baseCredentials = {
  username: 'zhangjiaqi',
  password: 'secret'
}

const attempts = buildLoginAttempts({
  credentials: baseCredentials,
  ldapProviders: [
    { id: 9, name: 'Beijing LDAP' },
    { id: 12, name: 'Shanghai LDAP' }
  ]
})

assert.deepEqual(
  attempts,
  [
    {
      label: 'local',
      credentials: {
        username: 'zhangjiaqi',
        password: 'secret',
        auth_source: 'local',
        ldap_instance_id: null
      }
    },
    {
      label: 'ldap:9',
      credentials: {
        username: 'zhangjiaqi',
        password: 'secret',
        auth_source: 'ldap',
        ldap_instance_id: 9
      }
    },
    {
      label: 'ldap:12',
      credentials: {
        username: 'zhangjiaqi',
        password: 'secret',
        auth_source: 'ldap',
        ldap_instance_id: 12
      }
    }
  ],
  'auto login should try local first, then every enabled LDAP provider'
)

assert.deepEqual(
  buildLoginAttempts({
    credentials: baseCredentials,
    ldapProviders: [{ id: '21', name: 'String ID LDAP' }]
  })[1].credentials,
  {
    username: 'zhangjiaqi',
    password: 'secret',
    auth_source: 'ldap',
    ldap_instance_id: 21
  },
  'LDAP provider ids should be normalized to numbers for the backend'
)

assert.equal(
  shouldContinueLoginFallback({
    code: 'local_auth_failed',
    hasNextAttempt: true
  }),
  true,
  'invalid local credentials should allow LDAP fallback'
)

assert.equal(
  shouldContinueLoginFallback({
    code: 'ldap_account_conflict',
    hasNextAttempt: true
  }),
  false,
  'account conflict should stop fallback and show the specific error'
)

assert.equal(
  shouldContinueLoginFallback({
    code: 'ldap_auth_failed',
    hasNextAttempt: false
  }),
  false,
  'final attempt failure should not continue'
)

console.log('login-source-auto-fallback.test.mjs: OK')
