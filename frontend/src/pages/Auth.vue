<template>
  <div class="auth-page">
    <div class="auth-page__ambient auth-page__ambient--sky"></div>
    <div class="auth-page__ambient auth-page__ambient--violet"></div>
    <div class="auth-page__ambient auth-page__ambient--orange"></div>

    <div class="auth-shell">
      <AuthShowcase
        class="auth-shell__showcase"
        :active="loading"
        :password-focused="passwordFocused"
      />

      <section
        data-testid="auth-login-card"
        class="auth-card surface-panel-strong"
      >
        <header class="auth-card__header">
          <div class="auth-brand">
            <div data-testid="auth-brand-mark" class="auth-brand__mark">
              <img
                src="/logo-mark.svg"
                alt="HyperOps"
                width="36"
                height="36"
              />
            </div>
            <div class="auth-brand__copy">
              <h2 class="auth-brand__title">{{ t('auth.loginTitle') }}</h2>
              <p class="auth-brand__subtitle">{{ t('auth.loginSubtitle') }}</p>
            </div>
          </div>

          <div data-testid="auth-language-switch" class="auth-card__lang">
            <LanguageSwitcher />
          </div>
        </header>

        <form class="auth-form" novalidate @submit.prevent="handleLogin">
          <div v-if="ldapProviders.length" class="auth-source-panel">
            <div class="auth-source-panel__copy">
              <span class="auth-source-panel__title">
                {{ t('auth.loginAutoMode') }}
              </span>
              <span class="auth-source-panel__hint">
                {{ t('auth.loginAutoHint') }}
              </span>
            </div>
            <button
              class="auth-source-panel__toggle"
              type="button"
              :disabled="loading"
              @click="manualLoginSource = !manualLoginSource"
            >
              {{
                manualLoginSource
                  ? t('auth.hideManualLoginSource')
                  : t('auth.manualLoginSource')
              }}
            </button>
          </div>

          <div v-if="ldapProviders.length && manualLoginSource" class="auth-form__field">
            <label class="auth-form__label" for="login-source">
              {{ t('auth.loginSource') }}
            </label>
            <select
              id="login-source"
              v-model="selectedLoginSource"
              class="auth-source-select"
              :disabled="loading"
            >
              <option value="local">{{ t('auth.localAccount') }}</option>
              <option
                v-for="provider in ldapProviders"
                :key="provider.id"
                :value="String(provider.id)"
              >
                {{ provider.name }}
              </option>
            </select>
            <p class="auth-form__subhint">{{ t('auth.loginManualHint') }}</p>
          </div>

          <div class="auth-form__field">
            <label class="auth-form__label" for="login-username">
              {{ t('auth.username') }}
            </label>
            <BaseInput
              id="login-username"
              v-model="formData.username"
              type="text"
              name="username"
              autocomplete="username"
              :placeholder="t('auth.username')"
              required
              :error="errors.username"
              :disabled="loading"
              size="lg"
            />
          </div>

          <div class="auth-form__field">
            <label class="auth-form__label" for="login-password">
              {{ t('auth.password') }}
            </label>
            <BaseInput
              id="login-password"
              v-model="formData.password"
              type="password"
              name="password"
              autocomplete="current-password"
              :placeholder="t('auth.password')"
              required
              :error="errors.password"
              :disabled="loading"
              size="lg"
              @focus="passwordFocused = true"
              @blur="passwordFocused = false"
            />
          </div>

          <div class="auth-form__meta">
            <label class="auth-check">
              <input
                id="remember-me"
                v-model="rememberMe"
                type="checkbox"
                name="remember-me"
                class="auth-check__input"
              />
              <span class="auth-check__label">{{ t('auth.rememberMe') }}</span>
            </label>

            <span class="auth-security-chip">{{ t('auth.secureAccess') }}</span>
          </div>

          <p class="auth-form__hint">
            {{
              ldapProviders.length
                ? t('auth.loginLdapHint')
                : t('auth.loginLocalOnlyHint')
            }}
          </p>

          <div v-if="errorMessage" class="auth-error">
            <p>{{ errorMessage }}</p>
          </div>

          <BaseButton
            type="submit"
            variant="primary"
            size="lg"
            block
            :loading="loading"
            :disabled="loading"
          >
            {{ loading ? t('auth.signingIn') : t('auth.signIn') }}
          </BaseButton>
        </form>

        <footer class="auth-card__footer">
          <span>{{ t('auth.loginFooterLeft') }}</span>
          <span>{{ t('auth.loginFooterRight') }}</span>
        </footer>
      </section>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { authApi } from '@/api/auth'
import { useUserStore } from '@/store/user'
import {
  buildLoginAttempts,
  shouldContinueLoginFallback
} from '@/utils/loginSources'
import BaseInput from '@/components/ui/BaseInput.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import LanguageSwitcher from '@/components/ui/LanguageSwitcher.vue'
import AuthShowcase from '@/components/auth/AuthShowcase.vue'

const { t } = useI18n()
const router = useRouter()
const userStore = useUserStore()

const formData = reactive({
  username: '',
  password: ''
})

const errors = reactive({
  username: '',
  password: ''
})

const loading = ref(false)
const errorMessage = ref('')
const rememberMe = ref(false)
const passwordFocused = ref(false)
const ldapProviders = ref([])
const selectedLoginSource = ref('local')
const manualLoginSource = ref(false)

const extractResponseData = (response) => response?.data?.data || response?.data || []

const loadLdapProviders = async () => {
  try {
    const data = extractResponseData(await authApi.getLdapProviders())
    ldapProviders.value = Array.isArray(data) ? data : []
  } catch (error) {
    console.warn('Failed to load LDAP providers:', error)
    ldapProviders.value = []
    selectedLoginSource.value = 'local'
  }
}

const validateLogin = () => {
  errors.username = ''
  errors.password = ''

  if (!formData.username.trim()) {
    errors.username = t('auth.required.username')
    return false
  }

  if (!formData.password) {
    errors.password = t('auth.required.password')
    return false
  }

  return true
}

const resolveLoginErrorMessage = (error) => {
  const code = error?.response?.data?.code
  const detail = error?.response?.data?.detail

  if (code === 'local_auth_failed') return t('auth.loginErrorLocal')
  if (code === 'ldap_auth_failed') return t('auth.loginErrorLdap')
  if (code === 'ldap_account_conflict') return t('auth.loginErrorConflict')
  if (code === 'ldap_config_unavailable') return t('auth.loginErrorUnavailable')
  if (typeof detail === 'string' && detail) return detail
  return t('auth.loginError')
}

const getLoginErrorCode = (error) => error?.response?.data?.code

const buildManualLoginAttempt = () => {
  const selectedProviderId =
    selectedLoginSource.value === 'local'
      ? null
      : Number(selectedLoginSource.value)

  return {
    label: selectedProviderId ? `ldap:${selectedProviderId}` : 'local',
    credentials: {
      username: formData.username,
      password: formData.password,
      auth_source: selectedProviderId ? 'ldap' : 'local',
      ldap_instance_id: selectedProviderId
    }
  }
}

const loginWithFallback = async () => {
  const attempts = manualLoginSource.value
    ? [buildManualLoginAttempt()]
    : buildLoginAttempts({
        credentials: {
          username: formData.username,
          password: formData.password
        },
        ldapProviders: ldapProviders.value
      })

  let lastError = null

  for (let index = 0; index < attempts.length; index += 1) {
    const attempt = attempts[index]

    try {
      await userStore.login(attempt.credentials)
      return
    } catch (error) {
      lastError = error
      const hasNextAttempt = index < attempts.length - 1
      const code = getLoginErrorCode(error)

      if (!shouldContinueLoginFallback({ code, hasNextAttempt })) {
        throw error
      }
    }
  }

  throw lastError
}

const handleLogin = async () => {
  if (!validateLogin()) {
    return
  }

  loading.value = true
  errorMessage.value = ''
  passwordFocused.value = false

  try {
    await loginWithFallback()

    try {
      await router.push(userStore.getUserLandingPath())
    } catch (navigationError) {
      console.error('Navigation error:', navigationError)
      loading.value = false
    }
  } catch (error) {
    console.error('Login error:', error)
    errorMessage.value = resolveLoginErrorMessage(error)
    loading.value = false
  }
}

onMounted(loadLdapProviders)
</script>

<style scoped>
.auth-page {
  position: relative;
  min-height: 100vh;
  overflow: hidden;
  background:
    radial-gradient(
      circle at top left,
      rgba(56, 189, 248, 0.18),
      transparent 24%
    ),
    radial-gradient(
      circle at 78% 18%,
      rgba(99, 102, 241, 0.12),
      transparent 22%
    ),
    linear-gradient(180deg, #f8fbff 0%, #eef4ff 50%, #f7f8fb 100%);
  padding: 2rem 1rem;
}

.auth-page__ambient {
  position: absolute;
  border-radius: 999px;
  filter: blur(80px);
  opacity: 0.7;
  pointer-events: none;
}

.auth-page__ambient--sky {
  top: 16%;
  left: 7%;
  height: 22rem;
  width: 22rem;
  background: rgba(125, 211, 252, 0.28);
}

.auth-page__ambient--violet {
  right: 10%;
  top: 24%;
  height: 20rem;
  width: 20rem;
  background: rgba(165, 180, 252, 0.24);
}

.auth-page__ambient--orange {
  bottom: 8%;
  left: 50%;
  height: 18rem;
  width: 18rem;
  transform: translateX(-50%);
  background: rgba(253, 186, 116, 0.2);
}

.auth-shell {
  position: relative;
  z-index: 1;
  margin: 0 auto;
  display: grid;
  min-height: calc(100vh - 4rem);
  width: 100%;
  max-width: 77rem;
  align-items: center;
  gap: 3.25rem;
  grid-template-columns: minmax(0, 1.1fr) minmax(24rem, 0.9fr);
}

.auth-shell__showcase {
  min-width: 0;
}

.auth-card {
  margin: 0 auto;
  width: 100%;
  max-width: 30rem;
  border-radius: 2rem;
  padding: 1.9rem 1.9rem 1.55rem;
  box-shadow: 0 30px 70px rgba(148, 163, 184, 0.22);
}

.auth-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}

.auth-brand {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 0.9rem;
}

.auth-brand__mark {
  display: flex;
  height: 3.2rem;
  width: 3.2rem;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  border: 1px solid rgba(203, 213, 225, 0.72);
  border-radius: 0.75rem;
  background: rgba(255, 255, 255, 0.82);
}

.auth-brand__mark img {
  height: 2.25rem;
  width: 2.25rem;
  object-fit: contain;
}

.auth-brand__copy {
  min-width: 0;
}

.auth-brand__title {
  color: #0f172a;
  font-family: 'Space Grotesk', 'IBM Plex Sans', sans-serif;
  font-size: 1.45rem;
  font-weight: 700;
  letter-spacing: -0.03em;
  line-height: 1.15;
}

.auth-brand__subtitle {
  margin-top: 0.45rem;
  color: #64748b;
  font-size: 0.9rem;
  line-height: 1.55;
}

.auth-card__lang :deep(button) {
  border-radius: 0.85rem;
  border: 1px solid rgba(226, 232, 240, 0.92);
  background: rgba(248, 250, 252, 0.94);
  padding: 0.45rem 0.65rem;
  color: #64748b;
}

.auth-card__lang :deep(button:hover) {
  background: #ffffff;
  color: #334155;
}

.auth-form {
  margin-top: 1.9rem;
  display: grid;
  gap: 1.1rem;
}

.auth-form__field {
  display: grid;
  gap: 0.45rem;
}

.auth-form__label {
  color: #475569;
  font-size: 0.84rem;
  font-weight: 700;
}

.auth-form__meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.9rem;
  padding-top: 0.15rem;
}

.auth-form__hint {
  margin-top: -0.2rem;
  color: #64748b;
  font-size: 0.88rem;
  line-height: 1.55;
}

.auth-form__subhint {
  color: #64748b;
  font-size: 0.8rem;
  line-height: 1.45;
}

.auth-source-panel {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.9rem;
  border: 1px solid rgba(219, 234, 254, 0.9);
  border-radius: 1.1rem;
  background: rgba(239, 246, 255, 0.68);
  padding: 0.8rem 0.9rem;
}

.auth-source-panel__copy {
  display: grid;
  min-width: 0;
  gap: 0.2rem;
}

.auth-source-panel__title {
  color: #1e3a8a;
  font-size: 0.86rem;
  font-weight: 800;
}

.auth-source-panel__hint {
  color: #64748b;
  font-size: 0.78rem;
  line-height: 1.45;
}

.auth-source-panel__toggle {
  flex: 0 0 auto;
  border: 0;
  border-radius: 999px;
  background: #ffffff;
  color: #2563eb;
  cursor: pointer;
  font-size: 0.78rem;
  font-weight: 800;
  padding: 0.48rem 0.72rem;
  transition:
    background 0.2s ease,
    color 0.2s ease,
    transform 0.2s ease;
}

.auth-source-panel__toggle:hover {
  background: #2563eb;
  color: #ffffff;
  transform: translateY(-1px);
}

.auth-source-panel__toggle:disabled {
  cursor: not-allowed;
  opacity: 0.65;
  transform: none;
}

.auth-source-select {
  width: 100%;
  border-radius: 1rem;
  border: 1px solid rgba(203, 213, 225, 0.92);
  background: rgba(255, 255, 255, 0.96);
  color: #0f172a;
  font-size: 0.95rem;
  font-weight: 600;
  outline: none;
  padding: 0.95rem 1rem;
  transition:
    border-color 0.2s ease,
    box-shadow 0.2s ease;
}

.auth-source-select:focus {
  border-color: rgba(37, 99, 235, 0.48);
  box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.1);
}

.auth-source-select:disabled {
  cursor: not-allowed;
  opacity: 0.72;
}

.auth-check {
  display: inline-flex;
  align-items: center;
  gap: 0.65rem;
  cursor: pointer;
}

.auth-check__input {
  height: 1rem;
  width: 1rem;
  border-radius: 0.35rem;
  accent-color: #4f46e5;
}

.auth-check__label {
  color: #475569;
  font-size: 0.88rem;
}

.auth-security-chip {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  background: #f8fafc;
  color: #64748b;
  font-size: 0.74rem;
  font-weight: 700;
  padding: 0.42rem 0.72rem;
}

.auth-error {
  border: 1px solid rgba(254, 205, 211, 0.9);
  border-radius: 1.15rem;
  background: rgba(255, 241, 242, 0.92);
  color: #be123c;
  font-size: 0.9rem;
  line-height: 1.55;
  padding: 0.9rem 1rem;
}

.auth-card__footer {
  margin-top: 1.35rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  border-top: 1px solid rgba(226, 232, 240, 0.85);
  color: #94a3b8;
  font-size: 0.76rem;
  padding-top: 1.1rem;
}

@media (max-width: 1024px) {
  .auth-shell {
    gap: 1.8rem;
    grid-template-columns: 1fr;
  }

  .auth-shell__showcase {
    display: none;
  }

  .auth-card {
    max-width: 34rem;
  }
}

@media (max-width: 640px) {
  .auth-page {
    padding: 1rem 0.9rem;
  }

  .auth-shell {
    min-height: calc(100vh - 2rem);
  }

  .auth-card {
    border-radius: 1.6rem;
    padding: 1.4rem 1.15rem 1.2rem;
  }

  .auth-card__header {
    flex-direction: column;
  }

  .auth-brand {
    align-items: flex-start;
  }

  .auth-form__meta,
  .auth-source-panel,
  .auth-card__footer {
    flex-direction: column;
    align-items: flex-start;
  }

  .auth-source-panel__toggle {
    width: 100%;
  }
}
</style>
