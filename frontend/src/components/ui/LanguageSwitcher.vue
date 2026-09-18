<template>
  <div
    ref="dropdownRef"
    class="language-switcher"
    :class="{ 'language-switcher--dark': variant === 'dark' }"
  >
    <button
      ref="triggerRef"
      type="button"
      class="language-switcher__trigger"
      :class="{ 'language-switcher__trigger--open': showDropdown }"
      :title="triggerLabel"
      :aria-label="triggerLabel"
      aria-haspopup="menu"
      :aria-expanded="showDropdown"
      @click="toggleDropdown"
    >
      <svg
        class="language-switcher__icon"
        aria-hidden="true"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="1.8"
          d="M3 5h12M9 3v2m1.05 9.5A18 18 0 0 1 6.41 9m6.09 9h7M11 21l5-10 5 10M12.75 5C11.78 10.77 8.07 15.61 3 18.13"
        />
      </svg>
    </button>

    <Transition name="language-menu">
      <div
        v-if="showDropdown"
        class="language-switcher__menu"
        role="menu"
        :aria-label="t('common.language')"
      >
        <button
          v-for="lang in languages"
          :key="lang.value"
          type="button"
          class="language-switcher__option"
          :class="{
            'language-switcher__option--selected': isSelected(lang.value)
          }"
          role="menuitemradio"
          :aria-checked="isSelected(lang.value)"
          @click="selectLanguage(lang.value)"
        >
          <span class="language-switcher__label">{{ lang.label }}</span>
          <svg
            v-if="isSelected(lang.value)"
            class="language-switcher__check"
            aria-hidden="true"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2.2"
              d="m5 12 4 4L19 6"
            />
          </svg>
        </button>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { usePreferencesStore } from '@/store/preferences'

defineProps({
  variant: {
    type: String,
    default: 'default',
    validator: (value) => ['default', 'dark'].includes(value)
  }
})

const { t, locale } = useI18n()
const preferencesStore = usePreferencesStore()

const showDropdown = ref(false)
const dropdownRef = ref(null)
const triggerRef = ref(null)

const languages = [
  { value: 'en', label: 'English' },
  { value: 'zh-CN', label: '简体中文' }
]

const currentLanguage = computed(
  () =>
    languages.find((language) => language.value === locale.value) ||
    languages[0]
)
const triggerLabel = computed(
  () => `${t('common.language')}: ${currentLanguage.value.label}`
)

const isSelected = (language) => locale.value === language

const toggleDropdown = () => {
  showDropdown.value = !showDropdown.value
}

const selectLanguage = async (language) => {
  await preferencesStore.setLanguage(language, false)
  locale.value = language
  showDropdown.value = false
  await nextTick()
  triggerRef.value?.focus()
}

const handleClickOutside = (event) => {
  if (dropdownRef.value && !dropdownRef.value.contains(event.target)) {
    showDropdown.value = false
  }
}

const handleKeydown = async (event) => {
  if (event.key !== 'Escape' || !showDropdown.value) return

  showDropdown.value = false
  await nextTick()
  triggerRef.value?.focus()
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
  document.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
  document.removeEventListener('keydown', handleKeydown)
})
</script>

<style scoped>
.language-switcher {
  position: relative;
}

.language-switcher__trigger {
  display: inline-flex;
  width: 2.75rem;
  height: 2.75rem;
  align-items: center;
  justify-content: center;
  border: 1px solid transparent;
  border-radius: 0.5rem;
  background: transparent;
  padding: 0;
  color: #64748b;
  transition:
    border-color 160ms ease,
    background-color 160ms ease,
    color 160ms ease;
}

.language-switcher__trigger:hover {
  border-color: #e2e8f0;
  background: #f8fafc;
  color: #334155;
}

.language-switcher__trigger--open,
.language-switcher__trigger--open:hover {
  border-color: #bfdbfe;
  background: #eff6ff;
  color: #245fd4;
}

.language-switcher__trigger:focus-visible,
.language-switcher__option:focus-visible {
  outline: none;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.16);
}

.language-switcher__icon {
  width: 1.125rem;
  height: 1.125rem;
  flex: 0 0 auto;
}

.language-switcher__menu {
  position: absolute;
  z-index: 50;
  top: calc(100% + 0.375rem);
  right: 0;
  width: 11rem;
  border: 1px solid #e2e8f0;
  border-radius: 0.375rem;
  background: #ffffff;
  padding: 0.375rem;
  box-shadow: 0 6px 12px rgba(15, 23, 42, 0.09);
}

.language-switcher__option {
  display: grid;
  width: 100%;
  min-height: 2.5rem;
  grid-template-columns: minmax(0, 1fr) 1rem;
  align-items: center;
  gap: 0.5rem;
  border: 0;
  border-radius: 0.25rem;
  background: transparent;
  padding: 0.45rem 0.625rem;
  color: #475569;
  font-size: 0.8125rem;
  line-height: 1.2;
  text-align: left;
  transition:
    background-color 140ms ease,
    color 140ms ease;
}

.language-switcher__option:hover {
  background: #f5f7fa;
  color: #1e293b;
}

.language-switcher__option--selected,
.language-switcher__option--selected:hover {
  background: #eef4ff;
  color: #1e55bf;
}

.language-switcher__label {
  overflow: hidden;
  font-weight: 550;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.language-switcher__check {
  width: 0.9rem;
  height: 0.9rem;
  color: #245fd4;
}

.language-switcher--dark .language-switcher__trigger {
  border-color: transparent;
  background: transparent;
  color: #e2e8f0;
}

.language-switcher--dark .language-switcher__trigger:hover {
  border-color: rgba(255, 255, 255, 0.16);
  background: rgba(255, 255, 255, 0.08);
  color: #ffffff;
}

.language-menu-enter-active,
.language-menu-leave-active {
  transition:
    opacity 120ms ease,
    transform 120ms ease;
  transform-origin: top right;
}

.language-menu-enter-from,
.language-menu-leave-to {
  opacity: 0;
  transform: translateY(-0.2rem);
}

@media (prefers-reduced-motion: reduce) {
  .language-switcher__trigger,
  .language-switcher__option,
  .language-menu-enter-active,
  .language-menu-leave-active {
    transition-duration: 0.01ms;
  }
}
</style>
