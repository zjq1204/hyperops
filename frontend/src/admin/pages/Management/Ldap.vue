<template>
  <AdminLayout>
    <PageFrame
      variant="soft"
      :title="t('adminPages.ldap.title')"
      :subtitle="t('adminPages.ldap.subtitle')"
    >
      <template #actions>
        <BaseButton @click="openCreateInstanceModal">
          {{ t('adminPages.ldap.addInstance') }}
        </BaseButton>
      </template>

      <div class="ldap-admin-page">
        <div
          v-if="notice.message"
          :class="[
            'ldap-notice',
            notice.tone === 'success' ? 'ldap-notice--success' : 'ldap-notice--error'
          ]"
        >
          {{ notice.message }}
        </div>

        <AdminPageState :loading="loading" :error="error">
          <div class="ldap-instance-layout">
            <section class="ldap-panel ldap-instance-list-panel">
              <div class="ldap-panel__header ldap-panel__header--spread">
                <div>
                  <h2>{{ t('adminPages.ldap.instancesTitle') }}</h2>
                  <p>{{ t('adminPages.ldap.instancesDescription') }}</p>
                </div>
                <span class="ldap-count-pill">
                  {{ t('adminPages.ldap.instanceCount', { count: ldapInstances.length }) }}
                </span>
              </div>

              <div v-if="ldapInstances.length" class="ldap-instance-list">
                <button
                  v-for="instance in ldapInstances"
                  :key="instance.id"
                  type="button"
                  :class="[
                    'ldap-instance-row',
                    selectedInstanceId === instance.id ? 'ldap-instance-row--active' : ''
                  ]"
                  @click="selectInstance(instance.id)"
                >
                  <span class="ldap-instance-row__icon">
                    <svg
                      class="h-5 w-5"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        stroke-linecap="round"
                        stroke-linejoin="round"
                        stroke-width="1.8"
                        d="M4 7h16M6 7v10a2 2 0 002 2h8a2 2 0 002-2V7M9 11h6M9 15h4M8 4h8"
                      />
                    </svg>
                  </span>
                  <span class="ldap-instance-row__body">
                    <span class="ldap-instance-row__title">
                      {{ instance.name || instance.host || 'LDAP' }}
                    </span>
                    <span class="ldap-instance-row__meta">
                      {{ instance.slug }} · {{ formatEndpoint(instance) }}
                    </span>
                  </span>
                  <span
                    :class="
                      instance.enabled
                        ? 'admin-status-badge admin-status-badge--success'
                        : 'admin-status-badge admin-status-badge--muted'
                    "
                  >
                    {{ instance.enabled ? t('common.enabled') : t('common.disabled') }}
                  </span>
                </button>
              </div>

              <EmptyState
                v-else
                variant="admin"
                :title="t('adminPages.ldap.emptyInstances')"
                :description="t('adminPages.ldap.emptyInstancesDescription')"
              >
                <template #icon>
                  <svg
                    class="h-8 w-8"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M4 7h16M6 7v10a2 2 0 002 2h8a2 2 0 002-2V7M9 11h6M9 15h4M8 4h8"
                    />
                  </svg>
                </template>
                <template #actions>
                  <BaseButton @click="openCreateInstanceModal">
                    {{ t('adminPages.ldap.addInstance') }}
                  </BaseButton>
                </template>
              </EmptyState>
            </section>

            <section class="ldap-panel ldap-instance-detail-panel">
              <template v-if="selectedInstance">
                <div class="ldap-instance-detail-head">
                  <div class="min-w-0">
                    <div class="ldap-instance-detail-head__eyebrow">
                      {{ selectedInstance.slug }}
                    </div>
                    <h2>{{ selectedInstance.name || 'LDAP' }}</h2>
                    <p>{{ formatEndpoint(selectedInstance) }}</p>
                  </div>
                  <div class="ldap-instance-detail-head__actions">
                    <BaseButton
                      variant="outline"
                      size="sm"
                      :loading="testingConnection && testingInstanceId === selectedInstance.id"
                      @click="runConnectionTest(selectedInstance)"
                    >
                      {{ t('adminPages.ldap.testConnection') }}
                    </BaseButton>
                    <BaseButton
                      variant="outline"
                      size="sm"
                      @click="openEditInstanceModal(selectedInstance)"
                    >
                      {{ t('common.edit') }}
                    </BaseButton>
                    <BaseButton
                      variant="danger"
                      size="sm"
                      :loading="deletingInstanceId === selectedInstance.id"
                      @click="deleteInstance(selectedInstance)"
                    >
                      {{ t('common.delete') }}
                    </BaseButton>
                  </div>
                </div>

                <div class="ldap-instance-compact-grid">
                  <div>
                    <span>{{ t('common.status') }}</span>
                    <strong>
                      {{ selectedInstance.enabled ? t('common.enabled') : t('common.disabled') }}
                    </strong>
                  </div>
                  <div>
                    <span>{{ t('adminPages.ldap.loginSource') }}</span>
                    <strong>
                      {{
                        selectedInstance.enabled
                          ? t('adminPages.ldap.visibleOnLogin')
                          : t('adminPages.ldap.hiddenOnLogin')
                      }}
                    </strong>
                  </div>
                  <div>
                    <span>{{ t('adminPages.ldap.bindAccount') }}</span>
                    <strong>{{ selectedInstance.bind_dn || '—' }}</strong>
                  </div>
                </div>

                <div
                  v-if="connectionPreview || testFeedback.type === 'connection'"
                  :class="[
                    'ldap-inline-result',
                    testFeedback.type === 'connection' && testFeedback.tone === 'error'
                      ? 'ldap-inline-result--error'
                      : 'ldap-inline-result--success'
                  ]"
                >
                  <span>
                    {{
                      testFeedback.type === 'connection' && testFeedback.message
                        ? testFeedback.message
                        : t('adminPages.ldap.connectionResult')
                    }}
                  </span>
                  <template v-if="connectionPreview">
                    <strong>
                      {{ t('adminPages.ldap.reachable') }}:
                      {{ connectionPreview.reachable ? t('common.yes') : t('common.no') }}
                    </strong>
                    <strong>
                      {{ t('adminPages.ldap.bindSucceeded') }}:
                      {{ connectionPreview.bind_succeeded ? t('common.yes') : t('common.no') }}
                    </strong>
                  </template>
                </div>

                <div class="ldap-mapping-toolbar">
                  <div>
                    <h3>{{ t('adminPages.ldap.mappingsTitle') }}</h3>
                    <p>
                      {{ t('adminPages.ldap.currentMappingDescription') }}
                    </p>
                  </div>
                  <BaseButton
                    variant="primary"
                    size="sm"
                    @click="openCreateMappingModal"
                  >
                    {{ t('adminPages.ldap.addMapping') }}
                  </BaseButton>
                </div>

                <AdminPageState
                  :loading="mappingsLoading"
                  :empty="!mappings.length"
                  :empty-title="t('adminPages.ldap.emptyMappings')"
                  :empty-description="t('adminPages.ldap.emptyMappingsDescription')"
                >
                  <AdminTable>
                    <thead>
                      <tr>
                        <th class="admin-table-head">
                          {{ t('adminPages.ldap.mappingScope') }}
                        </th>
                        <th class="admin-table-head">
                          {{ t('adminPages.ldap.targetGroup') }}
                        </th>
                        <th class="admin-table-head">
                          {{ t('adminPages.ldap.active') }}
                        </th>
                        <th class="admin-table-head">
                          {{ t('adminPages.ldap.updatedAt') }}
                        </th>
                        <th class="admin-table-head">{{ t('common.actions') }}</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr
                        v-for="mapping in mappings"
                        :key="mapping.id"
                        class="admin-table-row"
                      >
                        <td class="admin-table-cell font-medium text-slate-900">
                          {{ formatMappingScope(mapping) }}
                        </td>
                        <td class="admin-table-cell text-slate-600">
                          {{ mapping.target_group?.name || '—' }}
                        </td>
                        <td class="admin-table-cell">
                          <span
                            :class="
                              mapping.is_active
                                ? 'admin-status-badge admin-status-badge--success'
                                : 'admin-status-badge admin-status-badge--muted'
                            "
                          >
                            {{ mapping.is_active ? t('common.yes') : t('common.no') }}
                          </span>
                        </td>
                        <td class="admin-table-cell text-slate-500">
                          {{ formatDate(mapping.updated_at) }}
                        </td>
                        <td class="admin-table-cell">
                          <div class="flex flex-wrap gap-2">
                            <BaseButton
                              variant="outline"
                              size="sm"
                              @click="openEditMappingModal(mapping)"
                            >
                              {{ t('common.edit') }}
                            </BaseButton>
                            <BaseButton
                              variant="danger"
                              size="sm"
                              :loading="deletingMappingId === mapping.id"
                              @click="removeMapping(mapping)"
                            >
                              {{ t('common.delete') }}
                            </BaseButton>
                          </div>
                        </td>
                      </tr>
                    </tbody>
                  </AdminTable>
                </AdminPageState>
              </template>

              <EmptyState
                v-else
                variant="admin"
                :title="t('adminPages.ldap.selectInstanceTitle')"
                :description="t('adminPages.ldap.selectInstanceDescription')"
              />
            </section>
          </div>
        </AdminPageState>
      </div>

      <BaseModal
        :show="instanceModalOpen"
        :title="
          editingInstanceId
            ? t('adminPages.ldap.editInstance')
            : t('adminPages.ldap.addInstance')
        "
        size="xl"
        @close="closeInstanceModal"
      >
        <form @submit.prevent="saveInstance">
          <div class="admin-modal-stack">
            <label class="admin-jenkins-instance-switch-row">
              <div>
                <p class="text-sm font-medium text-slate-700">
                  {{ t('adminPages.ldap.enabledLabel') }}
                </p>
                <p class="mt-1 text-xs text-slate-500">
                  {{
                    instanceForm.enabled
                      ? t('adminPages.ldap.visibleOnLogin')
                      : t('adminPages.ldap.hiddenOnLogin')
                  }}
                </p>
              </div>

              <span class="admin-jenkins-instance-switch">
                <input
                  v-model="instanceForm.enabled"
                  type="checkbox"
                  class="sr-only peer"
                />
                <span class="admin-jenkins-instance-switch-track"></span>
                <span class="admin-jenkins-instance-switch-thumb"></span>
              </span>
            </label>

            <div class="ldap-modal-section">
              <p class="admin-modal-section-title">
                {{ t('adminPages.ldap.instanceIdentity') }}
              </p>
              <div class="ldap-modal-grid mt-4">
                <div>
                  <label class="mb-2 block text-sm font-medium text-slate-700">
                    {{ t('adminPages.ldap.instanceName') }}
                    <span class="text-rose-500">*</span>
                  </label>
                  <input
                    v-model.trim="instanceForm.name"
                    type="text"
                    required
                    class="input"
                    placeholder="OneProCloud LDAP"
                  />
                </div>

                <div>
                  <label class="mb-2 block text-sm font-medium text-slate-700">
                    {{ t('adminPages.ldap.slug') }}
                    <span class="text-rose-500">*</span>
                  </label>
                  <input
                    v-model.trim="instanceForm.slug"
                    type="text"
                    required
                    class="input"
                    placeholder="oneprocloud"
                  />
                  <p class="mt-2 text-xs text-slate-500">
                    {{ t('adminPages.ldap.slugHint') }}
                  </p>
                </div>
              </div>
            </div>

            <div class="ldap-modal-section">
              <p class="admin-modal-section-title">
                {{ t('adminPages.ldap.connectionTitle') }}
              </p>
              <div class="ldap-modal-grid mt-4">
                <div>
                  <label class="mb-2 block text-sm font-medium text-slate-700">
                    {{ t('adminPages.ldap.host') }}
                    <span class="text-rose-500">*</span>
                  </label>
                  <input
                    v-model.trim="instanceForm.host"
                    type="text"
                    required
                    class="input"
                    placeholder="ldap.example.com"
                  />
                </div>

                <div>
                  <label class="mb-2 block text-sm font-medium text-slate-700">
                    {{ t('adminPages.ldap.port') }}
                    <span class="text-rose-500">*</span>
                  </label>
                  <input
                    v-model.number="instanceForm.port"
                    type="number"
                    min="1"
                    required
                    class="input"
                    placeholder="389"
                  />
                </div>

                <div class="ldap-modal-grid__wide">
                  <label class="mb-2 block text-sm font-medium text-slate-700">
                    {{ t('adminPages.ldap.bindDn') }}
                  </label>
                  <input
                    v-model.trim="instanceForm.bind_dn"
                    type="text"
                    class="input"
                    placeholder="cn=admin,dc=example,dc=com"
                  />
                </div>

                <div class="ldap-modal-grid__wide">
                  <label class="mb-2 block text-sm font-medium text-slate-700">
                    {{ t('adminPages.ldap.bindPassword') }}
                  </label>
                  <input
                    v-model="bindPassword"
                    type="password"
                    class="input"
                    :placeholder="t('adminPages.ldap.bindPasswordHint')"
                  />
                  <p class="mt-2 text-xs text-slate-500">
                    {{
                      hasBindPassword
                        ? t('adminPages.ldap.storedPasswordHint')
                        : t('adminPages.ldap.bindPasswordHint')
                    }}
                  </p>
                </div>
              </div>

              <div class="mt-4 grid gap-3 sm:grid-cols-2">
                <label class="admin-modal-toggle">
                  <input
                    v-model="instanceForm.use_ssl"
                    type="checkbox"
                    class="admin-modal-checkbox"
                  />
                  <span class="text-sm font-medium text-slate-700">
                    {{ t('adminPages.ldap.useSsl') }}
                  </span>
                </label>
                <label class="admin-modal-toggle">
                  <input
                    v-model="instanceForm.start_tls"
                    type="checkbox"
                    class="admin-modal-checkbox"
                  />
                  <span class="text-sm font-medium text-slate-700">
                    {{ t('adminPages.ldap.startTls') }}
                  </span>
                </label>
              </div>
            </div>

            <div class="ldap-modal-section">
              <p class="admin-modal-section-title">
                {{ t('adminPages.ldap.directoryRulesTitle') }}
              </p>
              <div class="ldap-modal-grid mt-4">
                <div class="ldap-modal-grid__wide">
                  <label class="mb-2 block text-sm font-medium text-slate-700">
                    {{ t('adminPages.ldap.userBaseDn') }}
                  </label>
                  <input
                    v-model.trim="instanceForm.user_base_dn"
                    type="text"
                    class="input"
                  />
                </div>

                <div class="ldap-modal-grid__wide">
                  <label class="mb-2 block text-sm font-medium text-slate-700">
                    {{ t('adminPages.ldap.groupBaseDn') }}
                  </label>
                  <input
                    v-model.trim="instanceForm.group_base_dn"
                    type="text"
                    class="input"
                  />
                </div>

                <div class="ldap-modal-grid__wide">
                  <label class="mb-2 block text-sm font-medium text-slate-700">
                    {{ t('adminPages.ldap.userFilterTemplate') }}
                  </label>
                  <input
                    v-model.trim="instanceForm.user_filter_template"
                    type="text"
                    class="input"
                  />
                </div>

                <div class="ldap-modal-grid__wide">
                  <label class="mb-2 block text-sm font-medium text-slate-700">
                    {{ t('adminPages.ldap.groupFilterTemplate') }}
                  </label>
                  <input
                    v-model.trim="instanceForm.group_filter_template"
                    type="text"
                    class="input"
                  />
                </div>
              </div>
            </div>

            <div class="ldap-modal-section">
              <p class="admin-modal-section-title">
                {{ t('adminPages.ldap.attributes') }}
              </p>
              <div class="ldap-modal-grid ldap-modal-grid--four mt-4">
                <div>
                  <label class="mb-2 block text-sm font-medium text-slate-700">
                    {{ t('adminPages.ldap.uidAttr') }}
                  </label>
                  <input
                    v-model.trim="instanceForm.uid_attr"
                    type="text"
                    class="input"
                  />
                </div>

                <div>
                  <label class="mb-2 block text-sm font-medium text-slate-700">
                    {{ t('adminPages.ldap.emailAttr') }}
                  </label>
                  <input
                    v-model.trim="instanceForm.email_attr"
                    type="text"
                    class="input"
                  />
                </div>

                <div>
                  <label class="mb-2 block text-sm font-medium text-slate-700">
                    {{ t('adminPages.ldap.firstNameAttr') }}
                  </label>
                  <input
                    v-model.trim="instanceForm.first_name_attr"
                    type="text"
                    class="input"
                  />
                </div>

                <div>
                  <label class="mb-2 block text-sm font-medium text-slate-700">
                    {{ t('adminPages.ldap.lastNameAttr') }}
                  </label>
                  <input
                    v-model.trim="instanceForm.last_name_attr"
                    type="text"
                    class="input"
                  />
                </div>

                <div class="ldap-modal-grid__wide">
                  <label class="mb-2 block text-sm font-medium text-slate-700">
                    {{ t('adminPages.ldap.displayNameAttr') }}
                  </label>
                  <input
                    v-model.trim="instanceForm.display_name_attr"
                    type="text"
                    class="input"
                  />
                </div>
              </div>
            </div>

            <div class="admin-modal-card-muted">
              <div class="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p class="admin-modal-section-title">
                    {{ t('adminPages.ldap.testToolsTitle') }}
                  </p>
                  <p class="admin-modal-section-copy">
                    {{ t('adminPages.ldap.testToolsDescription') }}
                  </p>
                </div>
                <BaseButton
                  variant="secondary"
                  :loading="testingConnection && testingInstanceId === editingInstanceId"
                  @click="runDraftConnectionTest"
                >
                  {{ t('adminPages.ldap.testConnection') }}
                </BaseButton>
              </div>

              <div class="mt-4 grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto]">
                <input
                  v-model.trim="previewUsername"
                  type="text"
                  class="input"
                  :placeholder="t('adminPages.ldap.previewUsernamePlaceholder')"
                />
                <BaseButton
                  variant="primary"
                  :loading="testingUser"
                  @click="runUserPreview"
                >
                  {{ t('adminPages.ldap.testUser') }}
                </BaseButton>
              </div>

              <div
                v-if="connectionPreview || userPreview || testFeedback.message"
                class="ldap-test-results"
              >
                <article
                  v-if="testFeedback.message && !connectionPreview && !userPreview"
                  class="ldap-result-card"
                >
                  <div class="ldap-result-card__title">
                    {{ t('adminPages.ldap.testToolsTitle') }}
                  </div>
                  <p
                    :class="[
                      'ldap-result-card__message',
                      testFeedback.type === 'connection' && testFeedback.tone === 'error'
                        ? 'ldap-result-card__message--error'
                        : 'ldap-result-card__message--success'
                    ]"
                  >
                    {{ testFeedback.message }}
                  </p>
                </article>

                <article v-if="connectionPreview" class="ldap-result-card">
                  <div class="ldap-result-card__title">
                    {{ t('adminPages.ldap.connectionResult') }}
                  </div>
                  <p
                    v-if="testFeedback.type === 'connection' && testFeedback.message"
                    :class="[
                      'ldap-result-card__message',
                      testFeedback.tone === 'error'
                        ? 'ldap-result-card__message--error'
                        : 'ldap-result-card__message--success'
                    ]"
                  >
                    {{ testFeedback.message }}
                  </p>
                  <div class="ldap-result-metrics">
                    <div>
                      <span>{{ t('adminPages.ldap.reachable') }}</span>
                      <strong>
                        {{ connectionPreview.reachable ? t('common.yes') : t('common.no') }}
                      </strong>
                    </div>
                    <div>
                      <span>{{ t('adminPages.ldap.bindSucceeded') }}</span>
                      <strong>
                        {{ connectionPreview.bind_succeeded ? t('common.yes') : t('common.no') }}
                      </strong>
                    </div>
                  </div>
                </article>

                <article v-if="userPreview" class="ldap-result-card">
                  <div class="ldap-result-card__title">
                    {{ t('adminPages.ldap.previewResult') }}
                  </div>
                  <p
                    v-if="testFeedback.type === 'user' && testFeedback.message"
                    :class="[
                      'ldap-result-card__message',
                      testFeedback.tone === 'error'
                        ? 'ldap-result-card__message--error'
                        : 'ldap-result-card__message--success'
                    ]"
                  >
                    {{ testFeedback.message }}
                  </p>
                  <div class="ldap-dn-box">
                    <span>{{ t('adminPages.ldap.ldapDn') }}</span>
                    <strong>{{ userPreview.user?.dn || '—' }}</strong>
                  </div>
                  <dl class="ldap-preview-list">
                    <div>
                      <dt>uid</dt>
                      <dd>{{ userPreview.user?.username || '—' }}</dd>
                    </div>
                    <div>
                      <dt>{{ t('dashboard.email') }}</dt>
                      <dd>{{ userPreview.user?.email || '—' }}</dd>
                    </div>
                    <div>
                      <dt>{{ t('management.displayName') }}</dt>
                      <dd>{{ userPreview.user?.display_name || '—' }}</dd>
                    </div>
                  </dl>
                </article>
              </div>
            </div>
          </div>
        </form>

        <template #footer>
          <div class="flex w-full justify-end gap-3">
            <BaseButton variant="secondary" @click="closeInstanceModal">
              {{ t('common.cancel') }}
            </BaseButton>
            <BaseButton :loading="saving" @click="saveInstance">
              {{ t('common.save') }}
            </BaseButton>
          </div>
        </template>
      </BaseModal>

      <BaseModal
        :show="mappingModalOpen"
        :title="
          editingMappingId
            ? t('adminPages.ldap.editMapping')
            : t('adminPages.ldap.addMapping')
        "
        @close="closeMappingModal"
      >
        <form class="admin-modal-stack" @submit.prevent="submitMapping">
          <p v-if="mappingError" class="text-sm text-red-600">
            {{ mappingError }}
          </p>

          <div class="ldap-mapping-instance-note">
            <span>{{ t('adminPages.ldap.mappingInstance') }}</span>
            <strong>{{ selectedInstance?.name || '—' }}</strong>
          </div>

          <label class="admin-filter-field">
            <span class="admin-filter-label">
              {{ t('adminPages.ldap.mappingScope') }}
            </span>
            <select
              v-model="mappingForm.mapping_scope"
              class="admin-filter-control w-full bg-white"
            >
              <option value="all">
                {{ t('adminPages.ldap.mappingScopeAll') }}
              </option>
              <option value="group">
                {{ t('adminPages.ldap.mappingScopeGroup') }}
              </option>
            </select>
          </label>

          <label v-if="mappingForm.mapping_scope === 'group'" class="admin-filter-field">
            <span class="admin-filter-label">
              {{ t('adminPages.ldap.ldapGroupDn') }}
            </span>
            <input
              v-model.trim="mappingForm.ldap_group_dn"
              type="text"
              class="admin-filter-control w-full"
            />
          </label>

          <label class="admin-filter-field">
            <span class="admin-filter-label">
              {{ t('adminPages.ldap.targetGroup') }}
            </span>
            <select
              v-model="mappingForm.target_group"
              class="admin-filter-control w-full bg-white"
            >
              <option :value="null">
                {{ t('adminPages.ldap.selectGroupPlaceholder') }}
              </option>
              <option
                v-for="group in groupOptions"
                :key="group.id"
                :value="group.id"
              >
                {{ group.name }}
              </option>
            </select>
          </label>

          <label
            class="flex items-center gap-3 rounded-[1rem] border border-slate-200 bg-white px-4 py-3"
          >
            <input
              v-model="mappingForm.is_active"
              type="checkbox"
              class="h-4 w-4 rounded border-slate-300 text-sky-600 focus:ring-sky-500"
            />
            <span class="text-sm font-medium text-slate-700">
              {{ t('adminPages.ldap.active') }}
            </span>
          </label>
        </form>

        <template #footer>
          <div class="flex flex-row-reverse gap-2">
            <BaseButton
              variant="primary"
              :loading="mappingSaving"
              @click="submitMapping"
            >
              {{ t('common.confirm') }}
            </BaseButton>
            <BaseButton variant="secondary" @click="closeMappingModal">
              {{ t('common.cancel') }}
            </BaseButton>
          </div>
        </template>
      </BaseModal>

      <ConfirmDialog
        :show="confirmDialog.show"
        :title="confirmDialog.title"
        :message="confirmDialog.message"
        :confirm-text="confirmDialog.confirmText"
        :variant="confirmDialog.variant"
        :loading="confirmDialog.loading"
        @close="closeConfirmDialog"
        @confirm="runConfirmedAction"
      />
    </PageFrame>
  </AdminLayout>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { managementApi } from '@/admin/api/management'
import AdminPageState from '@/admin/components/AdminPageState.vue'
import AdminTable from '@/admin/components/AdminTable.vue'
import AdminLayout from '@/admin/layout/AdminLayout.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseModal from '@/components/ui/BaseModal.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import PageFrame from '@/components/ui/PageFrame.vue'
import { useConfirmDialog } from '@/composables/useConfirmDialog'

const { t } = useI18n()
const {
  confirmDialog,
  requestConfirm,
  closeConfirmDialog,
  runConfirmedAction
} = useConfirmDialog()

const loading = ref(false)
const mappingsLoading = ref(false)
const saving = ref(false)
const testingConnection = ref(false)
const testingInstanceId = ref(null)
const testingUser = ref(false)
const deletingInstanceId = ref(null)
const deletingMappingId = ref(null)
const error = ref('')
const notice = reactive({
  tone: 'success',
  message: ''
})

const ldapInstances = ref([])
const selectedInstanceId = ref(null)
const groupOptions = ref([])
const mappings = ref([])
const connectionPreview = ref(null)
const userPreview = ref(null)
const previewUsername = ref('')
const testFeedback = reactive({
  tone: 'success',
  message: '',
  type: ''
})

const instanceModalOpen = ref(false)
const editingInstanceId = ref(null)
const bindPassword = ref('')
const hasBindPassword = ref(false)
const instanceForm = reactive(createEmptyInstanceForm())

const mappingModalOpen = ref(false)
const editingMappingId = ref(null)
const mappingSaving = ref(false)
const mappingError = ref('')
const mappingForm = reactive({
  mapping_scope: 'group',
  ldap_group_dn: '',
  target_group: null,
  is_active: true
})

const selectedInstance = computed(() =>
  ldapInstances.value.find((item) => item.id === selectedInstanceId.value)
)

const mappingPayload = computed(() => ({
  ldap_config: selectedInstanceId.value,
  mapping_scope: mappingForm.mapping_scope || 'group',
  ldap_group_dn:
    mappingForm.mapping_scope === 'all'
      ? ''
      : (mappingForm.ldap_group_dn || '').trim(),
  target_group: mappingForm.target_group,
  is_active: !!mappingForm.is_active
}))

watch(
  () => selectedInstanceId.value,
  (nextId) => {
    connectionPreview.value = null
    userPreview.value = null
    clearTestFeedback()
    if (nextId) {
      loadMappings()
    } else {
      mappings.value = []
    }
  }
)

function createEmptyInstanceForm() {
  return {
    enabled: false,
    name: '',
    slug: '',
    is_default: false,
    host: '',
    port: 389,
    use_ssl: false,
    start_tls: false,
    bind_dn: '',
    user_base_dn: '',
    user_filter_template: '(&(objectClass=person)(uid={username}))',
    group_base_dn: '',
    group_filter_template: '(&(objectClass=groupOfNames)(member={user_dn}))',
    uid_attr: 'uid',
    email_attr: 'mail',
    first_name_attr: 'givenName',
    last_name_attr: 'sn',
    display_name_attr: 'displayName'
  }
}

function setNotice(message, tone = 'success') {
  notice.message = message
  notice.tone = tone
}

function clearNotice() {
  notice.message = ''
  notice.tone = 'success'
}

function setTestFeedback(message, tone = 'success', type = 'general') {
  testFeedback.message = message
  testFeedback.tone = tone
  testFeedback.type = type
}

function clearTestFeedback() {
  testFeedback.message = ''
  testFeedback.tone = 'success'
  testFeedback.type = ''
}

function normalizeCollection(data) {
  return Array.isArray(data) ? data : (data?.results ?? [])
}

function slugifyValue(value) {
  return String(value || '')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

function applyInstanceForm(data = {}) {
  const defaults = createEmptyInstanceForm()
  Object.keys(defaults).forEach((key) => {
    instanceForm[key] = data[key] ?? defaults[key]
  })
  instanceForm.enabled = !!data.enabled
  instanceForm.is_default = !!data.is_default
  instanceForm.port = Number(data.port || 389)
  bindPassword.value = ''
  hasBindPassword.value = !!data.has_bind_password
}

function buildConfigPayload(extra = {}) {
  const payload = {
    enabled: !!instanceForm.enabled,
    name: (instanceForm.name || '').trim(),
    slug: slugifyValue(instanceForm.slug || instanceForm.name || instanceForm.host),
    is_default: !!instanceForm.is_default,
    host: (instanceForm.host || '').trim(),
    port: Number(instanceForm.port || 389),
    use_ssl: !!instanceForm.use_ssl,
    start_tls: !!instanceForm.start_tls,
    bind_dn: (instanceForm.bind_dn || '').trim(),
    user_base_dn: (instanceForm.user_base_dn || '').trim(),
    user_filter_template: (instanceForm.user_filter_template || '').trim(),
    group_base_dn: (instanceForm.group_base_dn || '').trim(),
    group_filter_template: (instanceForm.group_filter_template || '').trim(),
    uid_attr: (instanceForm.uid_attr || '').trim(),
    email_attr: (instanceForm.email_attr || '').trim(),
    first_name_attr: (instanceForm.first_name_attr || '').trim(),
    last_name_attr: (instanceForm.last_name_attr || '').trim(),
    display_name_attr: (instanceForm.display_name_attr || '').trim(),
    ...extra
  }

  if (bindPassword.value) {
    payload.bind_password = bindPassword.value
  }

  if (editingInstanceId.value) {
    payload.ldap_config = editingInstanceId.value
  }

  return payload
}

function formatEndpoint(instance) {
  if (!instance?.host) return '—'
  return `${instance.use_ssl ? 'ldaps' : 'ldap'}://${instance.host}:${instance.port || 389}`
}

function formatDate(value) {
  if (!value) return '—'
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString()
}

function formatMappingScope(mapping) {
  if (mapping?.mapping_scope === 'all') {
    return t('adminPages.ldap.mappingScopeAll')
  }
  return mapping?.ldap_group_dn || '—'
}

function resetMappingForm() {
  mappingForm.mapping_scope = 'group'
  mappingForm.ldap_group_dn = ''
  mappingForm.target_group = null
  mappingForm.is_active = true
}

function selectInstance(instanceId) {
  selectedInstanceId.value = instanceId
}

async function loadGroups() {
  const groupsData = await managementApi.getGroups({ page: 1, page_size: 200 })
  groupOptions.value = normalizeCollection(groupsData)
}

async function loadInstances() {
  const data = await managementApi.getLdapInstances({ page: 1, page_size: 200 })
  const instances = normalizeCollection(data)
  ldapInstances.value = instances

  if (!instances.length) {
    selectedInstanceId.value = null
    return
  }

  const stillSelected = instances.some((item) => item.id === selectedInstanceId.value)
  if (!stillSelected) {
    selectedInstanceId.value = instances[0].id
  }
}

async function loadMappings() {
  if (!selectedInstanceId.value) return
  mappingsLoading.value = true
  try {
    const mappingsData = await managementApi.getLdapGroupMappings({
      ldap_config: selectedInstanceId.value,
      page: 1,
      page_size: 200
    })
    mappings.value = normalizeCollection(mappingsData)
  } finally {
    mappingsLoading.value = false
  }
}

async function loadPage() {
  loading.value = true
  error.value = ''
  clearNotice()

  try {
    await Promise.all([loadInstances(), loadGroups()])
    if (selectedInstanceId.value) {
      await loadMappings()
    }
  } catch (requestError) {
    error.value =
      requestError?.response?.data?.detail ||
      requestError?.message ||
      t('adminPages.ldap.loadFailed')
  } finally {
    loading.value = false
  }
}

function openCreateInstanceModal() {
  editingInstanceId.value = null
  applyInstanceForm({ enabled: true })
  connectionPreview.value = null
  userPreview.value = null
  clearTestFeedback()
  previewUsername.value = ''
  instanceModalOpen.value = true
}

function openEditInstanceModal(instance) {
  editingInstanceId.value = instance.id
  applyInstanceForm(instance)
  connectionPreview.value = null
  userPreview.value = null
  clearTestFeedback()
  previewUsername.value = ''
  instanceModalOpen.value = true
}

function closeInstanceModal() {
  instanceModalOpen.value = false
  editingInstanceId.value = null
  bindPassword.value = ''
  hasBindPassword.value = false
  connectionPreview.value = null
  userPreview.value = null
  clearTestFeedback()
  previewUsername.value = ''
}

async function saveInstance() {
  saving.value = true
  clearNotice()
  try {
    const payload = buildConfigPayload()
    const saved = editingInstanceId.value
      ? await managementApi.updateLdapInstance(editingInstanceId.value, payload)
      : await managementApi.createLdapInstance(payload)

    selectedInstanceId.value = saved.id
    await loadInstances()
    await loadMappings()
    closeInstanceModal()
    setNotice(t('adminPages.ldap.saveSucceeded'))
  } catch (requestError) {
    setNotice(
      requestError?.response?.data?.detail ||
        requestError?.message ||
        t('adminPages.ldap.saveFailed'),
      'error'
    )
  } finally {
    saving.value = false
  }
}

async function deleteInstance(instance) {
  requestConfirm({
    title: t('common.delete'),
    message: t('adminPages.ldap.deleteInstanceConfirm'),
    confirmText: t('common.delete'),
    onConfirm: async () => {
      deletingInstanceId.value = instance.id
      clearNotice()
      try {
        await managementApi.deleteLdapInstance(instance.id)
        if (selectedInstanceId.value === instance.id) {
          selectedInstanceId.value = null
        }
        await loadInstances()
        if (selectedInstanceId.value) {
          await loadMappings()
        }
        setNotice(t('adminPages.ldap.instanceDeleted'))
      } catch (requestError) {
        setNotice(
          requestError?.response?.data?.detail ||
            requestError?.message ||
            t('common.error'),
          'error'
        )
      } finally {
        deletingInstanceId.value = null
      }
    }
  })
}

async function runConnectionTest(instance) {
  testingConnection.value = true
  testingInstanceId.value = instance?.id ?? null
  clearNotice()
  clearTestFeedback()
  try {
    const result = await managementApi.testLdapConnection({
      ldap_config: instance.id
    })
    connectionPreview.value = result
    if (result?.reachable && result?.bind_succeeded) {
      setTestFeedback(t('adminPages.ldap.connectionSucceeded'), 'success', 'connection')
    } else {
      setTestFeedback(
        result?.detail || t('adminPages.ldap.testFailed'),
        'error',
        'connection'
      )
    }
  } catch (requestError) {
    connectionPreview.value = null
    setTestFeedback(
      requestError?.response?.data?.detail ||
        requestError?.message ||
        t('adminPages.ldap.testFailed'),
      'error',
      'connection'
    )
  } finally {
    testingConnection.value = false
    testingInstanceId.value = null
  }
}

async function runDraftConnectionTest() {
  testingConnection.value = true
  testingInstanceId.value = editingInstanceId.value
  clearNotice()
  clearTestFeedback()
  try {
    const result = await managementApi.testLdapConnection(buildConfigPayload())
    connectionPreview.value = result
    if (result?.reachable && result?.bind_succeeded) {
      setTestFeedback(t('adminPages.ldap.connectionSucceeded'), 'success', 'connection')
    } else {
      setTestFeedback(
        result?.detail || t('adminPages.ldap.testFailed'),
        'error',
        'connection'
      )
    }
  } catch (requestError) {
    connectionPreview.value = null
    setTestFeedback(
      requestError?.response?.data?.detail ||
        requestError?.message ||
        t('adminPages.ldap.testFailed'),
      'error',
      'connection'
    )
  } finally {
    testingConnection.value = false
    testingInstanceId.value = null
  }
}

async function runUserPreview() {
  const username = (previewUsername.value || '').trim()
  if (!username) {
    setTestFeedback(t('adminPages.ldap.previewUsernameRequired'), 'error', 'user')
    return
  }

  testingUser.value = true
  clearNotice()
  clearTestFeedback()
  userPreview.value = null
  try {
    userPreview.value = await managementApi.testLdapUser(
      buildConfigPayload({ username })
    )
    setTestFeedback(t('adminPages.ldap.previewSucceeded'), 'success', 'user')
  } catch (requestError) {
    userPreview.value = null
    setTestFeedback(
      requestError?.response?.data?.detail ||
        requestError?.message ||
        t('adminPages.ldap.testFailed'),
      'error',
      'user'
    )
  } finally {
    testingUser.value = false
  }
}

function openCreateMappingModal() {
  if (!selectedInstanceId.value) {
    setNotice(t('adminPages.ldap.selectInstanceDescription'), 'error')
    return
  }
  editingMappingId.value = null
  mappingError.value = ''
  resetMappingForm()
  mappingModalOpen.value = true
}

function openEditMappingModal(mapping) {
  editingMappingId.value = mapping.id
  mappingError.value = ''
  mappingForm.mapping_scope = mapping.mapping_scope || 'group'
  mappingForm.ldap_group_dn = mapping.ldap_group_dn || ''
  mappingForm.target_group = mapping.target_group?.id ?? null
  mappingForm.is_active = mapping.is_active !== false
  mappingModalOpen.value = true
}

function closeMappingModal() {
  mappingModalOpen.value = false
  mappingSaving.value = false
  editingMappingId.value = null
  mappingError.value = ''
  resetMappingForm()
}

async function submitMapping() {
  if (!mappingPayload.value.ldap_config) {
    mappingError.value = t('adminPages.ldap.selectInstanceDescription')
    return
  }
  if (
    mappingPayload.value.mapping_scope === 'group' &&
    !mappingPayload.value.ldap_group_dn
  ) {
    mappingError.value = t('adminPages.ldap.ldapGroupDn')
    return
  }
  if (!mappingPayload.value.target_group) {
    mappingError.value = t('adminPages.ldap.selectGroupPlaceholder')
    return
  }

  mappingSaving.value = true
  mappingError.value = ''
  clearNotice()

  try {
    if (editingMappingId.value) {
      await managementApi.updateLdapGroupMapping(
        editingMappingId.value,
        mappingPayload.value
      )
      setNotice(t('adminPages.ldap.mappingUpdated'))
    } else {
      await managementApi.createLdapGroupMapping(mappingPayload.value)
      setNotice(t('adminPages.ldap.mappingCreated'))
    }
    await loadMappings()
    closeMappingModal()
  } catch (requestError) {
    mappingError.value =
      requestError?.response?.data?.detail ||
      requestError?.message ||
      t('common.error')
  } finally {
    mappingSaving.value = false
  }
}

async function removeMapping(mapping) {
  requestConfirm({
    title: t('common.delete'),
    message: t('adminPages.ldap.deleteConfirm'),
    confirmText: t('common.delete'),
    onConfirm: async () => {
      deletingMappingId.value = mapping.id
      clearNotice()
      try {
        await managementApi.deleteLdapGroupMapping(mapping.id)
        await loadMappings()
        setNotice(t('adminPages.ldap.mappingDeleted'))
      } catch (requestError) {
        setNotice(
          requestError?.response?.data?.detail ||
            requestError?.message ||
            t('common.error'),
          'error'
        )
      } finally {
        deletingMappingId.value = null
      }
    }
  })
}

onMounted(loadPage)
</script>
