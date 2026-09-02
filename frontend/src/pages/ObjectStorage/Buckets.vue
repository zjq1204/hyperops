<template>
  <AppLayout>
    <PageFrame
      class="object-storage-page"
      :eyebrow="t('objectStorage.buckets.eyebrow')"
      :title="t('objectStorage.buckets.title')"
      :subtitle="t('objectStorage.buckets.subtitle')"
    >
      <template #actions>
        <BaseButton variant="secondary" :loading="loading" @click="loadBuckets">
          {{ t('common.refresh') }}
        </BaseButton>
        <BaseButton v-if="!notConfigured" @click="toggleCreateForm">
          {{
            showCreateForm
              ? t('common.close')
              : t('objectStorage.actions.addBucket')
          }}
        </BaseButton>
      </template>

      <section
        v-if="showCreateForm"
        class="mb-5 workspace-panel workspace-panel--padded"
      >
        <div class="section-heading">
          <div>
            <h2 class="section-title">
              {{ t('objectStorage.buckets.create.title') }}
            </h2>
            <p class="section-copy">
              {{ t('objectStorage.buckets.create.subtitle') }}
            </p>
          </div>
        </div>

        <form class="mt-5 grid gap-5" @submit.prevent="submitApplication">
          <div class="grid gap-4 md:grid-cols-2">
            <label class="space-y-2">
              <span class="admin-filter-label">{{
                t('objectStorage.fields.project')
              }}</span>
              <input
                v-model.trim="createForm.project"
                class="admin-filter-control"
                maxlength="80"
                required
                :placeholder="
                  t('objectStorage.buckets.create.projectPlaceholder')
                "
              />
            </label>
            <label class="space-y-2">
              <span class="admin-filter-label">{{
                t('objectStorage.fields.environment')
              }}</span>
              <select
                v-model="createForm.environment"
                class="admin-filter-control"
                required
              >
                <option value="development">
                  {{ t('objectStorage.environments.development') }}
                </option>
                <option value="test">
                  {{ t('objectStorage.environments.test') }}
                </option>
                <option value="production">
                  {{ t('objectStorage.environments.production') }}
                </option>
              </select>
            </label>
          </div>
          <label class="space-y-2">
            <span class="admin-filter-label">{{
              t('objectStorage.fields.purpose')
            }}</span>
            <input
              v-model.trim="createForm.purpose"
              class="admin-filter-control"
              maxlength="255"
              required
              :placeholder="
                t('objectStorage.buckets.create.purposePlaceholder')
              "
            />
          </label>
          <label class="space-y-2">
            <span class="admin-filter-label">{{
              t('objectStorage.fields.notes')
            }}</span>
            <textarea
              v-model.trim="createForm.notes"
              class="admin-filter-control min-h-24 resize-y"
              maxlength="2000"
              :placeholder="t('objectStorage.buckets.create.notesPlaceholder')"
            />
          </label>

          <InlineAlert
            variant="info"
            :title="t('objectStorage.buckets.create.namingTitle')"
            :message="t('objectStorage.buckets.create.namingMessage')"
          />

          <div
            class="flex flex-col-reverse gap-3 border-t border-slate-200 pt-4 sm:flex-row sm:justify-end"
          >
            <BaseButton variant="secondary" @click="closeCreateForm">
              {{ t('common.cancel') }}
            </BaseButton>
            <BaseButton type="submit" :loading="submitting">
              {{ t('objectStorage.buckets.create.submit') }}
            </BaseButton>
          </div>
        </form>
      </section>

      <InlineAlert
        v-if="submittedApplication"
        class="mb-5"
        variant="info"
        :title="t('objectStorage.applications.submittedTitle')"
        :message="
          t('objectStorage.applications.submittedMessage', {
            id: submittedApplication.id
          })
        "
      >
        <template #actions>
          <router-link
            class="text-sm font-semibold text-sky-700 hover:text-sky-900"
            :to="{ name: 'ObjectStorageApplications' }"
          >
            {{ t('objectStorage.actions.viewApplications') }}
          </router-link>
        </template>
      </InlineAlert>

      <section class="workspace-panel workspace-panel--padded">
        <div class="section-heading">
          <div>
            <h2 class="section-title">
              {{ t('objectStorage.buckets.ownedTitle') }}
            </h2>
            <p class="section-copy">
              {{ t('objectStorage.buckets.ownedHint') }}
            </p>
          </div>
          <span class="text-sm font-medium tabular-nums text-slate-500">
            {{ t('objectStorage.buckets.count', { count: buckets.length }) }}
          </span>
        </div>

        <div v-if="loading" class="py-12 text-center text-sm text-slate-500">
          {{ t('common.loading') }}
        </div>

        <PageErrorState
          v-else-if="loadError && !notConfigured"
          :message="t('objectStorage.errors.loadBuckets')"
          @retry="loadBuckets"
        />

        <EmptyState
          v-else-if="notConfigured"
          :title="t('objectStorage.notConfigured')"
          :description="t('objectStorage.notConfiguredHint')"
        />

        <div
          v-else-if="buckets.length"
          class="mt-4 divide-y divide-slate-200 border-y border-slate-200"
        >
          <article v-for="bucket in buckets" :key="bucket.id" class="py-4">
            <div
              class="grid gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(10rem,0.5fr)_minmax(8rem,0.35fr)_auto] lg:items-center"
            >
              <div class="min-w-0">
                <p class="break-all text-sm font-semibold text-slate-950">
                  {{ bucket.name }}
                </p>
                <p class="mt-1 line-clamp-2 text-xs leading-5 text-slate-500">
                  {{ bucket.purpose }}
                </p>
              </div>
              <div>
                <p class="text-xs font-medium text-slate-400">
                  {{ t('objectStorage.fields.project') }}
                </p>
                <p class="mt-1 text-sm text-slate-700">{{ bucket.project }}</p>
              </div>
              <div>
                <p class="text-xs font-medium text-slate-400">
                  {{ t('objectStorage.fields.environment') }}
                </p>
                <p class="mt-1 text-sm text-slate-700">
                  {{ environmentText(bucket.environment) }}
                </p>
              </div>
              <div class="flex items-center gap-2 lg:justify-end">
                <StatusBadge :status="bucketStatus(bucket.state)" />
                <BaseButton
                  v-if="canRelease(bucket)"
                  size="sm"
                  variant="ghost"
                  @click="openRelease(bucket)"
                >
                  {{ t('objectStorage.buckets.release.action') }}
                </BaseButton>
              </div>
            </div>

            <form
              v-if="releaseBucketId === bucket.id"
              class="mt-4 border-l-2 border-rose-300 bg-rose-50/60 px-4 py-4"
              @submit.prevent="submitRelease(bucket)"
            >
              <h3 class="text-sm font-semibold text-slate-950">
                {{ t('objectStorage.buckets.release.title') }}
              </h3>
              <p class="mt-1 text-sm leading-6 text-slate-600">
                {{ t('objectStorage.buckets.release.warning') }}
              </p>
              <div class="mt-4 grid gap-4 md:grid-cols-2">
                <label class="space-y-2">
                  <span class="admin-filter-label">
                    {{
                      t('objectStorage.buckets.release.confirmLabel', {
                        name: bucket.name
                      })
                    }}
                  </span>
                  <input
                    v-model="releaseForm.bucketName"
                    class="admin-filter-control"
                    autocomplete="off"
                    :placeholder="bucket.name"
                    required
                  />
                </label>
                <label class="space-y-2">
                  <span class="admin-filter-label">{{
                    t('objectStorage.buckets.release.reasonLabel')
                  }}</span>
                  <input
                    v-model.trim="releaseForm.reason"
                    class="admin-filter-control"
                    maxlength="500"
                    :placeholder="
                      t('objectStorage.buckets.release.reasonPlaceholder')
                    "
                  />
                </label>
              </div>
              <p
                v-if="
                  releaseForm.bucketName &&
                  releaseForm.bucketName !== bucket.name
                "
                class="mt-2 text-xs font-medium text-rose-700"
              >
                {{ t('objectStorage.buckets.release.nameMismatch') }}
              </p>
              <div
                class="mt-4 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end"
              >
                <BaseButton size="sm" variant="secondary" @click="closeRelease">
                  {{ t('common.cancel') }}
                </BaseButton>
                <BaseButton
                  size="sm"
                  variant="danger"
                  type="submit"
                  :loading="releasing"
                  :disabled="releaseForm.bucketName !== bucket.name"
                >
                  {{ t('objectStorage.buckets.release.confirmAction') }}
                </BaseButton>
              </div>
            </form>
          </article>
        </div>

        <EmptyState
          v-else
          :title="t('objectStorage.buckets.emptyTitle')"
          :description="t('objectStorage.buckets.emptyHint')"
        >
          <template #actions>
            <BaseButton size="sm" @click="openCreateForm">
              {{ t('objectStorage.actions.addFirstBucket') }}
            </BaseButton>
          </template>
        </EmptyState>
      </section>
    </PageFrame>
  </AppLayout>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import objectStorageApi, {
  isObjectStorageNotConfigured
} from '@/api/objectStorage'
import AppLayout from '@/components/layout/AppLayout.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import InlineAlert from '@/components/ui/InlineAlert.vue'
import PageFrame from '@/components/ui/PageFrame.vue'
import PageErrorState from '@/components/ui/PageErrorState.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import { useToast } from '@/composables/useToast'

const { t } = useI18n()
const { showSuccess, showError } = useToast()
const buckets = ref([])
const loading = ref(false)
const loadError = ref(false)
const notConfigured = ref(false)
const showCreateForm = ref(false)
const submitting = ref(false)
const submittedApplication = ref(null)
const releaseBucketId = ref(null)
const releasing = ref(false)

const createForm = reactive({
  project: '',
  environment: 'development',
  purpose: '',
  notes: ''
})
const releaseForm = reactive({ bucketName: '', reason: '' })

function environmentText(environment) {
  return t(`objectStorage.environments.${environment}`, environment)
}

function bucketStatus(state) {
  if (state === 'active') return 'enabled'
  if (state === 'failed') return 'failed'
  if (state === 'released') return 'disabled'
  return 'processing'
}

function canRelease(bucket) {
  return ['active', 'failed'].includes(bucket.state)
}

function resetCreateForm() {
  Object.assign(createForm, {
    project: '',
    environment: 'development',
    purpose: '',
    notes: ''
  })
}

function openCreateForm() {
  showCreateForm.value = true
  closeRelease()
}

function closeCreateForm() {
  showCreateForm.value = false
}

function toggleCreateForm() {
  showCreateForm.value ? closeCreateForm() : openCreateForm()
}

function openRelease(bucket) {
  releaseBucketId.value = bucket.id
  releaseForm.bucketName = ''
  releaseForm.reason = ''
  showCreateForm.value = false
}

function closeRelease() {
  releaseBucketId.value = null
  releaseForm.bucketName = ''
  releaseForm.reason = ''
}

async function loadBuckets() {
  loading.value = true
  loadError.value = false
  notConfigured.value = false
  try {
    buckets.value = await objectStorageApi.listBuckets()
  } catch (error) {
    buckets.value = []
    loadError.value = true
    notConfigured.value = isObjectStorageNotConfigured(error)
    showCreateForm.value = false
  } finally {
    loading.value = false
  }
}

async function submitApplication() {
  submitting.value = true
  try {
    submittedApplication.value = await objectStorageApi.createApplication({
      project: createForm.project,
      environment: createForm.environment,
      purpose: createForm.purpose,
      notes: createForm.notes
    })
    showSuccess(t('objectStorage.buckets.create.success'))
    resetCreateForm()
    closeCreateForm()
  } catch {
    showError(t('objectStorage.errors.submitApplication'))
  } finally {
    submitting.value = false
  }
}

async function submitRelease(bucket) {
  if (releaseForm.bucketName !== bucket.name) return
  releasing.value = true
  try {
    submittedApplication.value = await objectStorageApi.releaseBucket(
      bucket.id,
      {
        bucket_name: releaseForm.bucketName,
        reason: releaseForm.reason
      }
    )
    showSuccess(t('objectStorage.buckets.release.success'))
    closeRelease()
    await loadBuckets()
  } catch {
    showError(t('objectStorage.errors.releaseBucket'))
  } finally {
    releasing.value = false
  }
}

onMounted(loadBuckets)
</script>
