<template>
  <AdminLayout>
    <PageFrame variant="soft" :title="t('adminPages.monitoring.assetsTitle')">
      <AdminListSection>
        <template #toolbar>
          <div class="flex w-full flex-wrap items-center justify-between gap-3">
            <div class="flex min-w-0 flex-1 flex-wrap items-center gap-2">
              <label class="min-w-[13rem] flex-1 sm:max-w-xs">
                <span class="sr-only">{{
                  t('adminPages.monitoring.assetSearch')
                }}</span>
                <input
                  v-model="filters.query"
                  class="admin-filter-control"
                  :placeholder="
                    t('adminPages.monitoring.assetSearchPlaceholder')
                  "
                />
              </label>
              <label class="min-w-[10rem]">
                <span class="sr-only">{{
                  t('adminPages.monitoring.assetScope')
                }}</span>
                <select v-model="filters.scope" class="admin-filter-control">
                  <option value="all">{{ t('common.all') }}</option>
                  <option value="needs_attention">
                    {{ t('adminPages.monitoring.scopeNeedsAttention') }}
                  </option>
                  <option value="healthy">
                    {{ t('adminPages.monitoring.scopeHealthy') }}
                  </option>
                  <option value="ssh_issue">
                    {{ t('adminPages.monitoring.scopeSshIssue') }}
                  </option>
                  <option value="collection_issue">
                    {{ t('adminPages.monitoring.scopeCollectionIssue') }}
                  </option>
                </select>
              </label>
              <span class="text-xs font-medium text-slate-500">
                {{ assetListSummary }}
              </span>
              <span
                v-if="selectedHostIds.length"
                class="inline-flex items-center gap-2 rounded-md border border-blue-200 bg-blue-50 px-2.5 py-1 text-xs font-semibold text-blue-700"
              >
                {{
                  t('adminPages.monitoring.selectedHostCount', {
                    count: selectedHostIds.length
                  })
                }}
                <button
                  type="button"
                  class="text-blue-500 hover:text-blue-800"
                  @click="clearSelection"
                >
                  {{ t('common.clear') }}
                </button>
              </span>
            </div>
            <div class="flex items-center gap-2">
              <BaseButton
                variant="outline"
                size="sm"
                :loading="loading"
                :aria-label="t('common.refresh')"
                :title="t('common.refresh')"
                @click="load"
              >
                <span aria-hidden="true" class="text-base leading-none">↻</span>
              </BaseButton>
              <BaseButton
                variant="primary"
                size="sm"
                @click="openBulkInstallChooser"
              >
                {{ t('adminPages.monitoring.installCategraf') }}
              </BaseButton>
              <BaseButton variant="outline" size="sm" @click="openCreateHost">
                {{ t('adminPages.monitoring.addHost') }}
              </BaseButton>
            </div>
          </div>
        </template>
        <div
          v-if="error && hosts.length"
          class="mb-3 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800"
        >
          <span>{{ t('adminPages.monitoring.refreshPreservedError') }}</span>
          <BaseButton variant="ghost" size="sm" @click="load">
            {{ t('adminPages.monitoring.retryLoad') }}
          </BaseButton>
        </div>
        <AdminPageState
          :loading="loading && !hosts.length"
          :error="hosts.length ? '' : error"
          :empty="false"
        >
          <section class="grid gap-4">
            <section
              v-if="discoveredAssets.length"
              class="rounded-xl border border-slate-200 bg-white px-4 py-4 shadow-sm"
            >
              <div
                class="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between"
              >
                <div class="min-w-0">
                  <h2 class="text-sm font-semibold text-slate-900">
                    {{ t('adminPages.monitoring.discoveredAssets') }}
                  </h2>
                  <p class="mt-1 text-xs text-slate-500">
                    {{ t('adminPages.monitoring.discoveredAssetsHint') }}
                  </p>
                </div>
                <div class="flex flex-wrap gap-2">
                  <span
                    v-for="item in discoveredAssetStats"
                    :key="item.label"
                    class="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600"
                  >
                    {{ item.label }} {{ item.value }}
                  </span>
                </div>
              </div>

              <div class="mt-4 overflow-x-auto">
                <table class="min-w-full text-left text-sm">
                  <thead>
                    <tr
                      class="border-b border-slate-100 text-xs font-semibold text-slate-500"
                    >
                      <th class="py-2 pr-4">
                        {{ t('adminPages.monitoring.source') }}
                      </th>
                      <th class="py-2 pr-4">
                        {{ t('adminPages.monitoring.hostname') }}
                      </th>
                      <th class="py-2 pr-4">
                        {{ t('adminPages.monitoring.address') }}
                      </th>
                      <th class="py-2 pr-4">{{ t('common.status') }}</th>
                      <th class="py-2 pr-4">{{ t('common.actions') }}</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr
                      v-for="asset in discoveredAssets"
                      :key="`${asset.source}:${asset.key}`"
                      class="border-b border-slate-50 last:border-0"
                    >
                      <td class="py-3 pr-4">
                        <span
                          class="inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold"
                          :class="discoveredSourceClass(asset.source)"
                        >
                          {{ discoveredSourceText(asset.source) }}
                        </span>
                      </td>
                      <td class="py-3 pr-4 font-medium text-slate-900">
                        {{ asset.hostname || t('common.emptyValue') }}
                      </td>
                      <td class="py-3 pr-4 text-slate-600">
                        {{ asset.address || t('common.emptyValue') }}
                        <span v-if="asset.port" class="text-slate-400"
                          >:{{ asset.port }}</span
                        >
                      </td>
                      <td class="py-3 pr-4 text-slate-500">
                        {{ discoveredStatusText(asset) }}
                      </td>
                      <td class="py-3 pr-4">
                        <BaseButton
                          variant="outline"
                          size="sm"
                          :disabled="!asset.can_import"
                          :loading="
                            importingAssetKey === `${asset.source}:${asset.key}`
                          "
                          @click="importDiscoveredAsset(asset)"
                        >
                          {{ t('adminPages.monitoring.importToHyperOps') }}
                        </BaseButton>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </section>

            <AdminTable class="asset-status-table">
              <thead>
                <tr>
                  <th rowspan="2" class="admin-table-head w-10"></th>
                  <th rowspan="2" class="admin-table-head min-w-[10.5rem]">
                    {{ t('adminPages.monitoring.hostIdentity') }}
                  </th>
                  <th rowspan="2" class="admin-table-head min-w-[6.5rem]">
                    {{ t('adminPages.monitoring.connectionStatus') }}
                  </th>
                  <th
                    colspan="2"
                    class="admin-table-head text-center normal-case tracking-normal"
                  >
                    {{ t('adminPages.monitoring.componentCategraf') }}
                  </th>
                  <th
                    rowspan="2"
                    class="admin-table-head min-w-[7.5rem] text-right"
                  >
                    {{ t('common.actions') }}
                  </th>
                </tr>
                <tr>
                  <th class="admin-table-head min-w-[6rem] text-center">
                    {{ t('adminPages.monitoring.installStatus') }}
                  </th>
                  <th class="admin-table-head min-w-[6rem] text-center">
                    {{ t('adminPages.monitoring.serviceStatus') }}
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="!filteredHosts.length" class="admin-table-row">
                  <td class="admin-table-cell text-slate-400" colspan="6">
                    {{ t('common.noData') }}
                  </td>
                </tr>
                <tr
                  v-for="host in filteredHosts"
                  :key="host.id"
                  class="admin-table-row align-middle"
                >
                  <td class="admin-table-cell">
                    <input
                      type="checkbox"
                      :checked="selectedHostIds.includes(host.id)"
                      @change="toggleHost(host.id, $event.target.checked)"
                    />
                  </td>
                  <td class="admin-table-cell">
                    <div
                      class="w-[10rem] max-w-full truncate whitespace-nowrap"
                      :title="`${host.hostname} · ${host.address}`"
                    >
                      <span class="font-semibold text-slate-900">{{
                        host.hostname
                      }}</span>
                      <span class="ml-1 text-xs text-slate-500"
                        >· {{ host.address }}</span
                      >
                    </div>
                  </td>
                  <td
                    class="admin-table-cell"
                    :title="connectionStateTitle(host.ssh_verification)"
                  >
                    <span
                      class="inline-flex w-fit items-center gap-1.5 whitespace-nowrap rounded-md border px-2 py-1 text-xs font-semibold"
                      :class="connectionStateClass(host.ssh_verification)"
                    >
                      <span class="h-1.5 w-1.5 rounded-full bg-current" />
                      {{ connectionStateText(host.ssh_verification) }}
                    </span>
                  </td>
                  <td
                    class="admin-table-cell text-center"
                    :title="componentStateTitle(host.collection_state)"
                  >
                    <span
                      class="inline-flex items-center gap-1.5 whitespace-nowrap rounded-md border px-2 py-1 text-xs font-semibold"
                      :class="componentInstallationClass(host.collection_state)"
                    >
                      <span class="h-1.5 w-1.5 rounded-full bg-current" />
                      {{ componentInstallationText(host.collection_state) }}
                    </span>
                  </td>
                  <td
                    class="admin-table-cell text-center"
                    :title="componentStateTitle(host.collection_state)"
                  >
                    <span
                      v-if="componentRuntimeVisible(host.collection_state)"
                      class="inline-flex items-center gap-1.5 whitespace-nowrap text-xs font-semibold"
                      :class="componentRuntimeClass(host.collection_state)"
                    >
                      <span class="h-1.5 w-1.5 rounded-full bg-current" />
                      {{ componentRuntimeText(host.collection_state) }}
                    </span>
                    <span v-else class="text-xs text-slate-300">—</span>
                  </td>
                  <td class="admin-table-cell text-right">
                    <div
                      class="admin-row-actions flex-nowrap justify-end whitespace-nowrap"
                    >
                      <BaseButton
                        variant="outline"
                        size="sm"
                        @click="editHost(host)"
                      >
                        {{ t('common.edit') }}
                      </BaseButton>
                      <BaseButton
                        variant="ghost"
                        size="sm"
                        @click="deleteHost(host)"
                      >
                        {{ t('common.delete') }}
                      </BaseButton>
                    </div>
                  </td>
                </tr>
              </tbody>
            </AdminTable>
          </section>
        </AdminPageState>
      </AdminListSection>
    </PageFrame>

    <BaseModal
      :show="showHostForm"
      :title="
        form.id
          ? t('adminPages.monitoring.editHost')
          : t('adminPages.monitoring.addHost')
      "
      size="md"
      @close="closeHostForm"
    >
      <form class="grid gap-4" @submit.prevent="saveHost">
        <div class="grid gap-3 sm:grid-cols-2">
          <label class="admin-filter-field">
            <span class="admin-filter-label">{{
              t('adminPages.monitoring.hostname')
            }}</span>
            <input v-model="form.hostname" class="admin-filter-control" />
          </label>
          <label class="admin-filter-field">
            <span class="admin-filter-label">{{
              t('adminPages.monitoring.address')
            }}</span>
            <input v-model="form.address" class="admin-filter-control" />
          </label>
          <label class="admin-filter-field">
            <span class="admin-filter-label">{{
              t('adminPages.monitoring.sshUser')
            }}</span>
            <input v-model="form.sshUser" class="admin-filter-control" />
          </label>
          <label class="admin-filter-field">
            <span class="admin-filter-label">{{
              t('adminPages.monitoring.sshPort')
            }}</span>
            <input v-model.number="form.sshPort" class="admin-filter-control" />
          </label>
        </div>
        <section
          data-host-connection-section
          class="rounded-xl border border-slate-200 bg-slate-50/70 p-4"
        >
          <div class="flex flex-wrap items-center justify-between gap-3">
            <p class="text-sm font-semibold text-slate-900">
              {{ t('adminPages.monitoring.sshAuthMethod') }}
            </p>
            <div
              class="inline-flex rounded-lg border border-slate-200 bg-white p-1"
            >
              <button
                type="button"
                class="rounded-md px-3 py-1.5 text-sm font-semibold transition"
                :class="
                  form.sshAuthType === 'password'
                    ? 'bg-slate-900 text-white shadow-sm'
                    : 'text-slate-500 hover:text-slate-900'
                "
                @click="form.sshAuthType = 'password'"
              >
                {{ t('adminPages.monitoring.sshAuthPassword') }}
              </button>
              <button
                type="button"
                class="rounded-md px-3 py-1.5 text-sm font-semibold transition"
                :class="
                  form.sshAuthType === 'key'
                    ? 'bg-slate-900 text-white shadow-sm'
                    : 'text-slate-500 hover:text-slate-900'
                "
                @click="form.sshAuthType = 'key'"
              >
                {{ t('adminPages.monitoring.sshAuthKey') }}
              </button>
            </div>
          </div>

          <div class="mt-4 grid gap-3">
            <div class="flex items-end gap-2">
              <label class="admin-filter-field min-w-0 flex-1">
                <span class="admin-filter-label">{{
                  t('adminPages.monitoring.savedSshCredential')
                }}</span>
                <select v-model="form.sshKeyId" class="admin-filter-control">
                  <option value="">
                    {{ t('adminPages.monitoring.selectSshCredential') }}
                  </option>
                  <option
                    v-for="credential in credentialsForAuthType"
                    :key="credential.id"
                    :value="credential.id"
                  >
                    {{ credentialOptionText(credential) }}
                  </option>
                </select>
              </label>
              <BaseButton
                variant="outline"
                type="button"
                size="sm"
                :aria-label="t('adminPages.monitoring.manageCredentials')"
                :title="t('adminPages.monitoring.manageCredentials')"
                @click="router.push({ name: 'AdminMonitoringCredentials' })"
              >
                <svg
                  class="h-4 w-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                  aria-hidden="true"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M15 7a4 4 0 11-7.75 1.37L3 12.62V16h3v3h3v-3h2.38l1.25-1.25M17 7h.01"
                  />
                </svg>
              </BaseButton>
            </div>
            <p v-if="credentialSelectionError" class="text-xs text-rose-600">
              {{ credentialSelectionError }}
            </p>
            <dl
              v-if="selectedSshCredential"
              class="grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-1 border-y border-slate-200 py-2 text-xs"
            >
              <dt v-if="form.sshAuthType === 'key'" class="text-slate-500">
                {{ t('monitoringCredentials.algorithm') }}
              </dt>
              <dd
                v-if="form.sshAuthType === 'key'"
                class="truncate font-medium text-slate-700"
              >
                {{ credentialAlgorithmLabel(selectedSshCredential) }}
              </dd>
              <dt v-if="form.sshAuthType === 'key'" class="text-slate-500">
                {{ t('monitoringCredentials.fingerprint') }}
              </dt>
              <dd
                v-if="form.sshAuthType === 'key'"
                class="truncate font-mono text-slate-700"
              >
                {{ credentialFingerprint(selectedSshCredential) }}
              </dd>
              <dt class="text-slate-500">
                {{ t('monitoringCredentials.validation') }}
              </dt>
              <dd class="font-medium text-slate-700">
                {{ selectedCredentialValidationText }}
                <template v-if="form.sshAuthType === 'key'">
                  ·
                  {{
                    credentialHasPassphrase(selectedSshCredential)
                      ? t('adminPages.monitoring.passphraseProtected')
                      : t('adminPages.monitoring.noPassphrase')
                  }}
                </template>
              </dd>
            </dl>
          </div>
        </section>
        <div
          class="flex flex-col gap-3 rounded-lg border px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
          :class="hostConnectionStatusClass"
        >
          <div class="min-w-0">
            <p class="flex items-center gap-2 text-sm font-semibold">
              <span class="h-1.5 w-1.5 shrink-0 rounded-full bg-current" />
              {{ hostConnectionStatusText }}
            </p>
            <p
              v-if="hostConnectionMessage"
              class="mt-1 text-xs leading-5 opacity-80"
            >
              {{ hostConnectionMessage }}
            </p>
          </div>
          <BaseButton
            class="shrink-0"
            variant="outline"
            type="button"
            size="sm"
            :disabled="!canTestHostConnection"
            :loading="testingHostConnection"
            @click="testHostConnection"
          >
            {{ t('adminPages.monitoring.testSshConnection') }}
          </BaseButton>
        </div>
        <div class="flex flex-wrap justify-end gap-2 pt-2">
          <BaseButton variant="outline" type="button" @click="closeHostForm">
            {{ t('common.cancel') }}
          </BaseButton>
          <BaseButton
            variant="primary"
            type="submit"
            :disabled="saving || !isHostConnectionVerified"
            :loading="saving"
          >
            {{ t('common.save') }}
          </BaseButton>
        </div>
      </form>
    </BaseModal>

    <BaseModal
      :show="showBulkInstallChooser"
      :title="t('adminPages.monitoring.installCategraf')"
      size="md"
      @close="closeBulkInstallChooser"
    >
      <div class="grid gap-4">
        <section
          class="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3"
        >
          <div class="flex items-center justify-between gap-3">
            <p class="text-sm font-semibold text-slate-900">
              {{ t('adminPages.monitoring.selectInstallHosts') }}
            </p>
            <span class="text-xs font-semibold text-slate-500">
              {{
                t('adminPages.monitoring.selectedHostsForInstall', {
                  count: selectedHostIds.length
                })
              }}
            </span>
          </div>
          <div class="mt-3 grid max-h-56 gap-2 overflow-y-auto sm:grid-cols-2">
            <label
              v-for="host in hosts"
              :key="`install-host-${host.id}`"
              class="flex cursor-pointer items-center gap-2 rounded-md border border-slate-200 bg-white px-3 py-2 transition hover:border-blue-200 has-[:checked]:border-blue-300 has-[:checked]:bg-blue-50"
            >
              <input
                v-model="selectedHostIds"
                type="checkbox"
                :value="host.id"
              />
              <span
                class="min-w-0 truncate text-xs font-medium text-slate-700"
                :title="`${host.hostname} · ${host.address}`"
              >
                {{ host.hostname }} · {{ host.address }}
              </span>
            </label>
          </div>
          <p v-if="!selectedHostIds.length" class="mt-3 text-xs text-amber-700">
            {{ t('adminPages.monitoring.selectInstallHostHint') }}
          </p>
        </section>
        <div class="grid gap-3">
          <button
            type="button"
            class="rounded-lg border border-slate-200 bg-white p-4 text-left shadow-sm transition enabled:hover:border-blue-300 enabled:hover:bg-blue-50/40 disabled:cursor-not-allowed disabled:opacity-50"
            :disabled="!selectedHostIds.length"
            @click="chooseBulkInstall('categraf')"
          >
            <span class="text-sm font-semibold text-slate-900">
              {{ t('adminPages.monitoring.installCategraf') }}
            </span>
            <span class="mt-2 block text-xs leading-5 text-slate-500">
              {{ t('adminPages.monitoring.installChoiceCategrafHint') }}
            </span>
          </button>
        </div>
        <div class="flex justify-end">
          <BaseButton
            variant="outline"
            type="button"
            @click="closeBulkInstallChooser"
          >
            {{ t('common.cancel') }}
          </BaseButton>
        </div>
      </div>
    </BaseModal>

    <BaseModal
      :show="showCategrafForm"
      :title="categrafModalTitle"
      size="wide"
      @close="closeCategrafInstall"
    >
      <form class="grid gap-5" @submit.prevent="runCategrafInstall">
        <div class="grid gap-5 lg:grid-cols-[16rem_minmax(0,1fr)]">
          <aside class="rounded-xl border border-slate-200 bg-slate-50/80 p-3">
            <button
              v-for="(step, index) in categrafSteps"
              :key="step.key"
              type="button"
              class="flex w-full items-start gap-3 rounded-lg px-3 py-3 text-left transition"
              :class="[
                index === categrafStep
                  ? 'bg-white text-blue-700 shadow-sm ring-1 ring-blue-100'
                  : 'text-slate-600 hover:bg-white/70',
                canEnterCategrafStep(index)
                  ? ''
                  : 'cursor-not-allowed opacity-50 hover:bg-transparent'
              ]"
              :disabled="!canEnterCategrafStep(index)"
              @click="goCategrafStep(index)"
            >
              <span
                class="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold"
                :class="
                  index === categrafStep
                    ? 'bg-blue-600 text-white'
                    : index < categrafStep
                      ? 'bg-emerald-100 text-emerald-700'
                      : 'bg-slate-200 text-slate-500'
                "
              >
                {{ index + 1 }}
              </span>
              <span class="min-w-0">
                <span class="block text-sm font-semibold">{{
                  step.title
                }}</span>
              </span>
            </button>
          </aside>

          <section
            class="min-h-[28rem] rounded-xl border border-slate-200 bg-white p-5"
          >
            <div v-if="categrafStep === 0" class="grid gap-4">
              <div>
                <h3 class="text-base font-semibold text-slate-900">
                  {{ t('adminPages.monitoring.stepHostsTitle') }}
                </h3>
              </div>
              <div class="grid gap-2 sm:grid-cols-2">
                <div
                  v-for="host in selectedHosts"
                  :key="host.id"
                  class="rounded-lg border border-slate-200 bg-slate-50/70 px-3 py-3"
                >
                  <p class="truncate text-sm font-semibold text-slate-900">
                    {{ host.hostname }}
                  </p>
                  <p class="mt-1 truncate text-xs text-slate-500">
                    {{ host.address }} / {{ host.ssh_user || 'root' }}:{{
                      host.ssh_port || 22
                    }}
                  </p>
                </div>
              </div>
            </div>

            <div v-else-if="categrafStep === 1" class="grid gap-4">
              <div>
                <div class="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <h3 class="text-base font-semibold text-slate-900">
                      {{ t('adminPages.monitoring.collectionProfiles') }}
                    </h3>
                  </div>
                  <span
                    class="rounded-full px-3 py-1 text-xs font-semibold"
                    :class="
                      categrafForm.profiles.length
                        ? 'bg-blue-50 text-blue-700'
                        : 'bg-rose-50 text-rose-700'
                    "
                  >
                    {{ profileSelectionSummary }}
                  </span>
                </div>
                <p
                  v-if="capabilityAdjustmentMode && !newCategrafProfiles.length"
                  class="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800"
                >
                  {{ t('adminPages.monitoring.selectNewCapabilityHint') }}
                </p>
                <p
                  v-else-if="!categrafForm.profiles.length"
                  class="mt-3 rounded-lg border border-rose-100 bg-rose-50 px-3 py-2 text-sm text-rose-700"
                >
                  {{ t('adminPages.monitoring.profileRequiredHint') }}
                </p>
              </div>
              <div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                <label
                  v-for="profile in profiles"
                  :key="profile.id"
                  class="group flex min-h-12 cursor-pointer items-center gap-3 rounded-xl border border-slate-200 bg-white p-3 transition hover:border-blue-200 hover:bg-blue-50/40 has-[:checked]:border-blue-300 has-[:checked]:bg-blue-50"
                >
                  <input
                    v-model="categrafForm.profiles"
                    type="checkbox"
                    :value="profile.id"
                    :disabled="
                      capabilityAdjustmentMode &&
                      initialCategrafProfiles.includes(profile.id)
                    "
                  />
                  <span
                    class="flex min-w-0 flex-1 items-center justify-between gap-2"
                  >
                    <span class="block text-sm font-semibold text-slate-900">{{
                      profile.name || profile.id
                    }}</span>
                    <span
                      v-if="
                        capabilityAdjustmentMode &&
                        initialCategrafProfiles.includes(profile.id)
                      "
                      class="shrink-0 rounded-full bg-emerald-50 px-2 py-0.5 text-[0.6875rem] font-semibold text-emerald-700"
                    >
                      {{ t('adminPages.monitoring.existingCapability') }}
                    </span>
                    <span
                      v-else-if="
                        capabilityAdjustmentMode &&
                        categrafForm.profiles.includes(profile.id)
                      "
                      class="shrink-0 rounded-full bg-blue-50 px-2 py-0.5 text-[0.6875rem] font-semibold text-blue-700"
                    >
                      {{ t('adminPages.monitoring.newCapability') }}
                    </span>
                  </span>
                </label>
              </div>
            </div>

            <div v-else-if="categrafStep === 2" class="grid gap-4">
              <div>
                <h3 class="text-base font-semibold text-slate-900">
                  {{ t('adminPages.monitoring.stepParamsTitle') }}
                </h3>
                <p
                  v-if="capabilityAdjustmentMode"
                  class="mt-2 text-xs leading-5 text-slate-500"
                >
                  {{ t('adminPages.monitoring.inheritedParamsNotice') }}
                </p>
                <p
                  v-if="capabilityAdjustmentMode && !newCapabilityParamsValid"
                  class="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800"
                >
                  {{ t('adminPages.monitoring.newCapabilityParamsRequired') }}
                </p>
              </div>
              <section
                class="rounded-xl border border-slate-200 bg-slate-50/70 p-4"
              >
                <h4 class="text-sm font-semibold text-slate-900">
                  {{ t('adminPages.monitoring.installLabels') }}
                </h4>
                <div class="mt-3 grid gap-3 sm:grid-cols-2">
                  <label class="admin-filter-field">
                    <span class="admin-filter-label">{{
                      t('adminPages.monitoring.region')
                    }}</span>
                    <input
                      v-model="categrafForm.region"
                      class="admin-filter-control"
                    />
                  </label>
                  <label class="admin-filter-field">
                    <span class="admin-filter-label">{{
                      t('adminPages.monitoring.env')
                    }}</span>
                    <input
                      v-model="categrafForm.env"
                      class="admin-filter-control"
                    />
                  </label>
                  <label class="admin-filter-field">
                    <span class="admin-filter-label">{{
                      t('adminPages.monitoring.team')
                    }}</span>
                    <input
                      v-model="categrafForm.team"
                      class="admin-filter-control"
                    />
                  </label>
                  <label class="admin-filter-field">
                    <span class="admin-filter-label">{{
                      t('adminPages.monitoring.service')
                    }}</span>
                    <input
                      v-model="categrafForm.service"
                      class="admin-filter-control"
                    />
                  </label>
                </div>
              </section>

              <section v-if="showCategrafProfileSettings" class="grid gap-3">
                <div
                  v-if="needsCategrafMysqlConfig"
                  class="rounded-xl border border-slate-200 bg-white p-4"
                >
                  <h4 class="text-sm font-semibold text-slate-800">
                    {{ t('adminPages.monitoring.mysqlConfig') }}
                  </h4>
                  <div class="mt-3 grid gap-3 sm:grid-cols-2">
                    <label class="admin-filter-field">
                      <span class="admin-filter-label">{{
                        t('adminPages.monitoring.mysqlAddress')
                      }}</span>
                      <input
                        v-model="categrafForm.mysqlAddress"
                        class="admin-filter-control"
                        placeholder="127.0.0.1:3306"
                      />
                    </label>
                    <label class="admin-filter-field">
                      <span class="admin-filter-label">{{
                        t('adminPages.monitoring.mysqlUser')
                      }}</span>
                      <input
                        v-model="categrafForm.mysqlUser"
                        class="admin-filter-control"
                        placeholder="exporter"
                      />
                    </label>
                    <label class="admin-filter-field">
                      <span class="admin-filter-label">{{
                        t('adminPages.monitoring.mysqlPassword')
                      }}</span>
                      <input
                        v-model="categrafForm.mysqlPassword"
                        type="password"
                        class="admin-filter-control"
                      />
                    </label>
                    <label class="admin-filter-field">
                      <span class="admin-filter-label">{{
                        t('adminPages.monitoring.mysqlParameters')
                      }}</span>
                      <input
                        v-model="categrafForm.mysqlParameters"
                        class="admin-filter-control"
                        placeholder="tls=false"
                      />
                    </label>
                  </div>
                </div>
                <div
                  v-if="needsCategrafRedisConfig"
                  class="rounded-xl border border-slate-200 bg-white p-4"
                >
                  <h4 class="text-sm font-semibold text-slate-800">
                    {{ t('adminPages.monitoring.redisConfig') }}
                  </h4>
                  <div class="mt-3 grid gap-3 sm:grid-cols-2">
                    <label class="admin-filter-field">
                      <span class="admin-filter-label">{{
                        t('adminPages.monitoring.redisAddress')
                      }}</span>
                      <input
                        v-model="categrafForm.redisAddress"
                        class="admin-filter-control"
                        placeholder="127.0.0.1:6379"
                      />
                    </label>
                    <label class="admin-filter-field">
                      <span class="admin-filter-label">{{
                        t('adminPages.monitoring.redisUsername')
                      }}</span>
                      <input
                        v-model="categrafForm.redisUsername"
                        class="admin-filter-control"
                        placeholder="default"
                      />
                    </label>
                    <label class="admin-filter-field sm:col-span-2">
                      <span class="admin-filter-label">{{
                        t('adminPages.monitoring.redisPassword')
                      }}</span>
                      <input
                        v-model="categrafForm.redisPassword"
                        type="password"
                        class="admin-filter-control"
                      />
                    </label>
                  </div>
                </div>
                <div
                  v-if="needsCategrafNginxConfig"
                  class="rounded-xl border border-slate-200 bg-white p-4"
                >
                  <h4 class="text-sm font-semibold text-slate-800">
                    {{ t('adminPages.monitoring.nginxConfig') }}
                  </h4>
                  <label class="admin-filter-field mt-3">
                    <span class="admin-filter-label">{{
                      t('adminPages.monitoring.nginxStatusUrl')
                    }}</span>
                    <input
                      v-model="categrafForm.nginxStatusUrl"
                      class="admin-filter-control"
                      placeholder="http://127.0.0.1/nginx_status"
                    />
                  </label>
                </div>
              </section>
              <section
                v-else
                class="rounded-xl border border-dashed border-slate-200 bg-slate-50/70 p-4 text-sm text-slate-500"
              >
                {{ t('adminPages.monitoring.noProfileParams') }}
              </section>
              <section
                class="rounded-xl border border-slate-200 bg-slate-50/70 p-4"
              >
                <div class="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h4 class="text-sm font-semibold text-slate-900">
                      {{ t('adminPages.monitoring.deploymentSettingsTitle') }}
                    </h4>
                    <p
                      v-if="capabilityAdjustmentMode"
                      class="mt-1 text-xs leading-5 text-slate-500"
                    >
                      {{ t('adminPages.monitoring.deploymentSettingsHint') }}
                    </p>
                  </div>
                  <div
                    v-if="capabilityAdjustmentMode"
                    class="flex flex-wrap items-center gap-2"
                  >
                    <span
                      class="inline-flex rounded-md border px-2.5 py-1 text-xs font-semibold"
                      :class="
                        deploymentSettingChanges.length
                          ? 'border-amber-200 bg-amber-50 text-amber-700'
                          : 'border-emerald-200 bg-emerald-50 text-emerald-700'
                      "
                    >
                      {{ deploymentSettingStatus }}
                    </span>
                    <BaseButton
                      v-if="deploymentSettingChanges.length"
                      variant="ghost"
                      size="sm"
                      type="button"
                      @click="resetDeploymentSettings"
                    >
                      {{ t('adminPages.monitoring.restoreDeploymentSettings') }}
                    </BaseButton>
                  </div>
                </div>
                <div class="mt-3 grid gap-3 sm:grid-cols-2">
                  <label class="admin-filter-field sm:col-span-2">
                    <span class="flex items-center justify-between gap-2">
                      <span class="admin-filter-label">{{
                        t('adminPages.monitoring.n9eUrl')
                      }}</span>
                      <span
                        v-if="
                          capabilityAdjustmentMode &&
                          deploymentSettingChanged('n9eUrl')
                        "
                        class="text-xs font-medium text-amber-700"
                      >
                        {{
                          t('adminPages.monitoring.deploymentSettingModified')
                        }}
                      </span>
                    </span>
                    <input
                      v-model="categrafForm.n9eUrl"
                      class="admin-filter-control"
                    />
                  </label>
                  <label class="admin-filter-field">
                    <span class="flex items-center justify-between gap-2">
                      <span class="admin-filter-label">{{
                        t('adminPages.monitoring.installDir')
                      }}</span>
                      <span
                        v-if="
                          capabilityAdjustmentMode &&
                          deploymentSettingChanged('installDir')
                        "
                        class="text-xs font-medium text-amber-700"
                      >
                        {{
                          t('adminPages.monitoring.deploymentSettingModified')
                        }}
                      </span>
                    </span>
                    <input
                      v-model="categrafForm.installDir"
                      class="admin-filter-control"
                    />
                  </label>
                  <label class="admin-filter-field">
                    <span class="flex items-center justify-between gap-2">
                      <span class="admin-filter-label">{{
                        t('adminPages.monitoring.image')
                      }}</span>
                      <span
                        v-if="
                          capabilityAdjustmentMode &&
                          deploymentSettingChanged('image')
                        "
                        class="text-xs font-medium text-amber-700"
                      >
                        {{
                          t('adminPages.monitoring.deploymentSettingModified')
                        }}
                      </span>
                    </span>
                    <input
                      v-model="categrafForm.image"
                      class="admin-filter-control"
                    />
                  </label>
                  <label class="admin-filter-field sm:col-span-2">
                    <span class="flex items-center justify-between gap-2">
                      <span class="admin-filter-label">{{
                        t('adminPages.monitoring.baseUrl')
                      }}</span>
                      <span
                        v-if="
                          capabilityAdjustmentMode &&
                          deploymentSettingChanged('baseUrl')
                        "
                        class="text-xs font-medium text-amber-700"
                      >
                        {{
                          t('adminPages.monitoring.deploymentSettingModified')
                        }}
                      </span>
                    </span>
                    <input
                      v-model="categrafForm.baseUrl"
                      class="admin-filter-control"
                    />
                  </label>
                </div>
                <p
                  v-if="!deploymentSettingsValid"
                  class="mt-3 text-xs font-medium text-amber-700"
                >
                  {{ t('adminPages.monitoring.deploymentSettingsRequired') }}
                </p>
              </section>
            </div>

            <div v-else class="grid gap-4">
              <div>
                <h3 class="text-base font-semibold text-slate-900">
                  {{ t('adminPages.monitoring.stepPreviewTitle') }}
                </h3>
              </div>
              <section
                v-if="capabilityAdjustmentMode"
                class="rounded-xl border border-blue-200 bg-blue-50 px-4 py-3 text-sm leading-6 text-blue-800"
              >
                {{ t('adminPages.monitoring.safeCapabilityUpdateNotice') }}
              </section>
              <section
                v-if="capabilityAdjustmentMode"
                class="rounded-xl border border-slate-200 bg-white p-4"
              >
                <h4 class="text-sm font-semibold text-slate-900">
                  {{
                    t('adminPages.monitoring.deploymentSettingsChangeSummary')
                  }}
                </h4>
                <p
                  v-if="!deploymentSettingChanges.length"
                  class="mt-2 text-sm leading-6 text-slate-600"
                >
                  {{ t('adminPages.monitoring.deploymentSettingsInherited') }}
                </p>
                <dl v-else class="mt-3 grid gap-3">
                  <div
                    v-for="item in deploymentSettingChanges"
                    :key="item.key"
                    class="grid gap-1 rounded-lg bg-amber-50 px-3 py-2.5 sm:grid-cols-[9rem_minmax(0,1fr)] sm:gap-3"
                  >
                    <dt class="text-xs font-semibold text-amber-800">
                      {{ item.label }}
                    </dt>
                    <dd
                      class="min-w-0 break-all text-xs leading-5 text-slate-700"
                    >
                      <span class="text-slate-500">{{ item.previous }}</span>
                      <span class="px-2 text-amber-700" aria-hidden="true"
                        >→</span
                      >
                      <span class="font-medium text-slate-900">{{
                        item.current
                      }}</span>
                    </dd>
                  </div>
                </dl>
              </section>
              <section
                class="grid gap-3 rounded-xl border border-slate-200 bg-white p-4"
              >
                <div class="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <h4 class="text-sm font-semibold text-slate-900">
                      {{ t('adminPages.monitoring.ansiblePreview') }}
                    </h4>
                  </div>
                  <BaseButton
                    variant="outline"
                    type="button"
                    :loading="previewingCategraf"
                    @click="previewCategraf"
                  >
                    {{
                      showAnsiblePreview
                        ? t('adminPages.monitoring.collapsePreview')
                        : t('adminPages.monitoring.previewAnsible')
                    }}
                  </BaseButton>
                </div>
                <pre
                  v-if="showAnsiblePreview && categrafPreviewText"
                  class="max-h-80 overflow-auto whitespace-pre-wrap rounded-lg bg-slate-950 p-3 text-xs leading-6 text-slate-100"
                  >{{ categrafPreviewText }}</pre
                >
              </section>
              <section
                class="grid gap-3 rounded-xl border border-slate-200 bg-white p-4"
              >
                <div class="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <h4 class="text-sm font-semibold text-slate-900">
                      {{ t('adminPages.monitoring.manualCommandPreview') }}
                    </h4>
                  </div>
                  <div class="flex flex-wrap gap-2">
                    <BaseButton
                      variant="outline"
                      type="button"
                      :loading="previewingCategraf"
                      @click="generateCategrafCommands"
                    >
                      {{
                        showManualCommands
                          ? t('adminPages.monitoring.collapsePreview')
                          : t('adminPages.monitoring.generateManualCommands')
                      }}
                    </BaseButton>
                    <BaseButton
                      variant="outline"
                      type="button"
                      :disabled="!manualInstallCommands"
                      @click="copyManualCategrafCommands"
                    >
                      {{
                        manualCommandsCopied
                          ? t('adminPages.monitoring.commandCopied')
                          : t('adminPages.monitoring.copyCommand')
                      }}
                    </BaseButton>
                  </div>
                </div>
                <div
                  v-if="showManualCommands && manualInstallCommands"
                  class="overflow-hidden rounded-xl"
                >
                  <pre
                    class="max-h-72 overflow-auto whitespace-pre-wrap break-words bg-slate-950 p-4 text-xs leading-6 text-slate-100"
                    >{{ manualInstallCommands }}</pre
                  >
                </div>
              </section>
            </div>
          </section>
        </div>

        <div
          class="flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 pt-4"
        >
          <span class="text-xs text-slate-500">
            {{
              t('adminPages.monitoring.stepProgress', {
                current: categrafStep + 1,
                total: categrafSteps.length
              })
            }}
          </span>
          <div class="flex flex-wrap justify-end gap-2">
            <BaseButton
              variant="outline"
              type="button"
              @click="closeCategrafInstall"
            >
              {{ t('common.cancel') }}
            </BaseButton>
            <BaseButton
              variant="outline"
              type="button"
              :disabled="
                categrafStep === 0 ||
                (capabilityAdjustmentMode && categrafStep === 1)
              "
              @click="prevCategrafStep"
            >
              {{ t('adminPages.monitoring.previousStep') }}
            </BaseButton>
            <BaseButton
              v-if="categrafStep < categrafSteps.length - 1"
              variant="primary"
              type="button"
              :disabled="!canGoNextCategraf"
              @click="nextCategrafStep"
            >
              {{ t('adminPages.monitoring.nextStep') }}
            </BaseButton>
            <BaseButton
              v-else
              variant="primary"
              type="submit"
              :disabled="
                capabilityAdjustmentMode && !newCategrafProfiles.length
              "
              :loading="runningCategraf"
            >
              {{
                capabilityAdjustmentMode
                  ? t('adminPages.monitoring.dispatchCapabilityUpdate')
                  : t('adminPages.monitoring.runInstall')
              }}
            </BaseButton>
          </div>
        </div>
      </form>
    </BaseModal>
  </AdminLayout>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import AdminLayout from '@/admin/layout/AdminLayout.vue'
import AdminListSection from '@/admin/components/AdminListSection.vue'
import AdminPageState from '@/admin/components/AdminPageState.vue'
import AdminTable from '@/admin/components/AdminTable.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseModal from '@/components/ui/BaseModal.vue'
import PageFrame from '@/components/ui/PageFrame.vue'
import { useToast } from '@/composables/useToast'
import { monitoringStackApi } from '@/admin/api/monitoringStack'
import {
  attentionCount,
  componentStatePresentation,
  connectionStatePresentation,
  filterHosts
} from '@/admin/pages/Monitoring/assets/hostListState'
import { getApiErrorMessage } from '@/utils/apiError'
import {
  credentialAlgorithmLabel,
  credentialFingerprint,
  credentialHasPassphrase,
  credentialTypeKey,
  credentialValidationKey,
  shortFingerprint
} from '@/admin/pages/Monitoring/credentials/credentialState'

const { locale, t } = useI18n()
const route = useRoute()
const router = useRouter()
const { showSuccess } = useToast()
const loading = ref(false)
const saving = ref(false)
const previewingCategraf = ref(false)
const runningCategraf = ref(false)
const error = ref('')
const profiles = ref([])
const hosts = ref([])
const sshCredentials = ref([])
const assetReconciliation = ref({})
const selectedHostIds = ref([])
const importingAssetKey = ref('')
const testingHostConnection = ref(false)
const hostConnectionStatus = ref('idle')
const attemptedHostConnectionSignature = ref('')
const testedHostConnectionSignature = ref('')
const hostConnectionMessage = ref('')
const hostVerificationReceipt = ref('')
const filters = reactive({
  query: '',
  scope: 'all'
})
const categrafStep = ref(0)
const categrafPreviewData = ref(null)
const categrafPreviewSignature = ref('')
const categrafPreviewText = ref('')
const showAnsiblePreview = ref(false)
const showManualCommands = ref(false)
const manualCommandsCopied = ref(false)
const showHostForm = ref(false)
const showBulkInstallChooser = ref(false)
const showCategrafForm = ref(false)
const capabilityAdjustmentMode = ref(false)
const initialCategrafProfiles = ref([])
const capabilityBaseJobId = ref(null)
const deploymentSettingsBaseline = reactive({
  baseUrl: '',
  n9eUrl: '',
  installDir: '',
  image: ''
})
const form = reactive(defaultHostForm())
const hostConnectionSignature = computed(() =>
  JSON.stringify({
    hostId: form.id || '',
    address: String(form.address || '').trim(),
    sshUser: String(form.sshUser || '').trim(),
    sshPort: Number(form.sshPort || 22),
    sshAuthType: form.sshAuthType,
    sshKeyId: String(form.sshKeyId || '')
  })
)
const isHostConnectionVerified = computed(
  () =>
    hostConnectionStatus.value === 'success' &&
    testedHostConnectionSignature.value === hostConnectionSignature.value
)
const canTestHostConnection = computed(() => {
  if (
    !String(form.address || '').trim() ||
    !String(form.sshUser || '').trim() ||
    !Number(form.sshPort)
  )
    return false
  return Boolean(form.sshKeyId)
})
const credentialsForAuthType = computed(() => {
  const expected = form.sshAuthType === 'password' ? 'password' : 'private_key'
  return sshCredentials.value.filter(
    (credential) => credentialTypeKey(credential) === expected
  )
})
const selectedSshCredential = computed(() =>
  sshCredentials.value.find(
    (credential) => String(credential.id) === String(form.sshKeyId)
  )
)
watch(
  () => form.sshAuthType,
  () => {
    if (
      selectedSshCredential.value &&
      !credentialsForAuthType.value.some(
        (credential) =>
          String(credential.id) === String(selectedSshCredential.value.id)
      )
    ) {
      form.sshKeyId = ''
    }
    resetHostConnectionTest()
  }
)
const credentialSelectionError = computed(() =>
  !form.sshKeyId ? t('adminPages.monitoring.credentialRequired') : ''
)
const selectedCredentialValidationText = computed(() =>
  selectedSshCredential.value
    ? t(
        `monitoringCredentials.validationStates.${credentialValidationKey(selectedSshCredential.value)}`
      )
    : ''
)
const hostConnectionStatusText = computed(() => {
  const keys = {
    idle: 'sshConnectionRequired',
    testing: 'sshConnectionTesting',
    success: 'sshConnectionSuccess',
    error: 'sshConnectionFailed'
  }
  return t(`adminPages.monitoring.${keys[hostConnectionStatus.value]}`)
})
const hostConnectionStatusClass = computed(() => {
  if (hostConnectionStatus.value === 'success')
    return 'border-emerald-200 bg-emerald-50 text-emerald-800'
  if (hostConnectionStatus.value === 'error')
    return 'border-rose-200 bg-rose-50 text-rose-800'
  if (hostConnectionStatus.value === 'testing')
    return 'border-sky-200 bg-sky-50 text-sky-800'
  return 'border-slate-200 bg-slate-50 text-slate-600'
})
const needsCategrafMysqlConfig = computed(
  () =>
    categrafForm.profiles.includes('mysql-rds') ||
    categrafForm.profiles.includes('mysql')
)
const needsCategrafRedisConfig = computed(() =>
  categrafForm.profiles.includes('redis')
)
const needsCategrafNginxConfig = computed(() =>
  categrafForm.profiles.includes('nginx')
)
const showCategrafProfileSettings = computed(
  () =>
    needsCategrafMysqlConfig.value ||
    needsCategrafRedisConfig.value ||
    needsCategrafNginxConfig.value
)
const newCategrafProfiles = computed(() =>
  categrafForm.profiles.filter(
    (profile) => !initialCategrafProfiles.value.includes(profile)
  )
)
const newCapabilityParamsValid = computed(() => {
  if (
    newCategrafProfiles.value.some((profile) =>
      ['mysql-rds', 'mysql'].includes(profile)
    ) &&
    (!categrafForm.mysqlAddress.trim() || !categrafForm.mysqlUser.trim())
  )
    return false
  if (
    newCategrafProfiles.value.some((profile) =>
      ['redis', 'redis-cloud'].includes(profile)
    ) &&
    !categrafForm.redisAddress.trim()
  )
    return false
  if (
    newCategrafProfiles.value.includes('nginx') &&
    !categrafForm.nginxStatusUrl.trim()
  )
    return false
  return true
})
const deploymentSettingChanges = computed(() =>
  [
    {
      key: 'installDir',
      label: t('adminPages.monitoring.installDir')
    },
    {
      key: 'image',
      label: t('adminPages.monitoring.image')
    },
    {
      key: 'n9eUrl',
      label: t('adminPages.monitoring.n9eUrl')
    },
    {
      key: 'baseUrl',
      label: t('adminPages.monitoring.baseUrl')
    }
  ]
    .filter(({ key }) => deploymentSettingChanged(key))
    .map(({ key, label }) => ({
      key,
      label,
      previous: deploymentSettingsBaseline[key],
      current: categrafForm[key]
    }))
)
const deploymentSettingStatus = computed(() =>
  t(
    deploymentSettingChanges.value.length
      ? 'adminPages.monitoring.deploymentSettingsModified'
      : 'adminPages.monitoring.deploymentSettingsInheritedStatus'
  )
)
const deploymentSettingsValid = computed(() =>
  ['baseUrl', 'n9eUrl', 'installDir', 'image'].every((key) =>
    String(categrafForm[key] || '').trim()
  )
)
const categrafModalTitle = computed(() =>
  capabilityAdjustmentMode.value
    ? t('adminPages.monitoring.adjustCapabilitiesTitle')
    : t('adminPages.monitoring.installCategraf')
)
const profileSelectionSummary = computed(() =>
  capabilityAdjustmentMode.value
    ? t('adminPages.monitoring.newCapabilityCount', {
        count: newCategrafProfiles.value.length
      })
    : t('adminPages.monitoring.selectedProfileCount', {
        count: categrafForm.profiles.length
      })
)
const filteredHosts = computed(() => filterHosts(hosts.value, filters))
const hostAttentionCount = computed(() => attentionCount(hosts.value))
const assetListSummary = computed(() =>
  t('adminPages.monitoring.assetListSummary', {
    total: hosts.value.length,
    attention: hostAttentionCount.value
  })
)
const selectedHosts = computed(() =>
  selectedHostIds.value
    .map((id) => hosts.value.find((host) => host.id === id))
    .filter(Boolean)
)
const discoveredAssets = computed(
  () => assetReconciliation.value?.results || []
)
const discoveredAssetStats = computed(() => [
  {
    label: t('adminPages.monitoring.n9eOnlyAssets'),
    value: assetReconciliation.value?.summary?.n9e_only || 0
  },
  {
    label: t('adminPages.monitoring.prometheusOnlyAssets'),
    value: assetReconciliation.value?.summary?.prometheus_only || 0
  }
])
const categrafSteps = computed(() => [
  {
    key: 'hosts',
    title: t('adminPages.monitoring.stepHosts')
  },
  {
    key: 'profiles',
    title: t('adminPages.monitoring.stepProfiles')
  },
  {
    key: 'params',
    title: t('adminPages.monitoring.stepParams')
  },
  {
    key: 'preview',
    title: t('adminPages.monitoring.stepPreview')
  }
])
const canGoNextCategraf = computed(() => {
  if (categrafStep.value === 0) return selectedHostIds.value.length > 0
  if (categrafStep.value === 1) {
    if (capabilityAdjustmentMode.value)
      return newCategrafProfiles.value.length > 0
    return categrafForm.profiles.length > 0
  }
  if (categrafStep.value === 2) {
    if (!deploymentSettingsValid.value) return false
    if (capabilityAdjustmentMode.value) return newCapabilityParamsValid.value
  }
  return true
})
const currentCategrafSignature = computed(() =>
  JSON.stringify(categrafJobPayload())
)
const isCategrafPreviewCurrent = computed(() =>
  Boolean(
    categrafPreviewData.value &&
    categrafPreviewSignature.value === currentCategrafSignature.value
  )
)
const manualInstallCommands = computed(() => {
  if (!isCategrafPreviewCurrent.value) return ''
  const commands = categrafPreviewData.value?.vars?.hosts
    ?.map((host) => {
      const label = host.hostname || host.address || `host-${host.id}`
      return [`# ${label}`, host.install_command].filter(Boolean).join('\n')
    })
    .filter(Boolean)
  if (!commands?.length) return ''
  return commands.join('\n\n')
})
const categrafForm = reactive({
  baseUrl: '',
  n9eUrl: '',
  installDir: '/opt/categraf',
  image: 'flashcatcloud/categraf:latest',
  profiles: ['linux-basic'],
  region: 'center',
  env: 'prod',
  team: 'ops',
  service: 'infra',
  mysqlAddress: '',
  mysqlUser: '',
  mysqlPassword: '',
  mysqlParameters: 'tls=false',
  redisAddress: '',
  redisUsername: '',
  redisPassword: '',
  nginxStatusUrl: ''
})
function defaultHostForm() {
  return {
    id: '',
    hostname: '',
    address: '',
    sshUser: 'root',
    sshPort: 22,
    sshAuthType: 'password',
    sshKeyId: ''
  }
}

function normalizeList(data) {
  return data?.results || data || []
}

function credentialOptionText(credential) {
  return [
    credential.name,
    credentialAlgorithmLabel(credential),
    shortFingerprint(credential)
  ]
    .filter(Boolean)
    .join(' · ')
}

function discoveredSourceText(source) {
  if (source === 'n9e') return 'n9e'
  if (source === 'prometheus') return 'Prometheus'
  return source || t('common.emptyValue')
}

function discoveredSourceClass(source) {
  if (source === 'n9e') return 'border-blue-200 bg-blue-50 text-blue-700'
  if (source === 'prometheus')
    return 'border-emerald-200 bg-emerald-50 text-emerald-700'
  return 'border-slate-200 bg-slate-50 text-slate-500'
}

function discoveredStatusText(asset) {
  if (asset.source === 'prometheus') {
    if (asset.health === 'up') return t('adminPages.monitoring.statusUp')
    if (asset.health) return t('adminPages.monitoring.statusDown')
  }
  return t('adminPages.monitoring.unmanagedAsset')
}

function componentInstallationText(state) {
  const { installation } = componentStatePresentation(state)
  const keys = {
    installed: 'componentInstalled',
    not_installed: 'componentNotInstalled',
    installing: 'componentInstalling',
    failed: 'componentInstallationFailed',
    unknown: 'componentInstallationUnknown',
    not_applicable: 'componentNotEnabled'
  }
  return t(
    `adminPages.monitoring.${keys[installation] || 'componentInstallationUnknown'}`
  )
}

function connectionStateText(verification) {
  const keys = {
    connected: 'assetConnectionReachable',
    failed: 'assetConnectionFailed',
    unverified: 'assetConnectionUnverified'
  }
  return t(
    `adminPages.monitoring.${keys[connectionStatePresentation(verification)]}`
  )
}

function connectionStateClass(verification) {
  const state = connectionStatePresentation(verification)
  if (state === 'connected')
    return 'border-emerald-200 bg-emerald-50 text-emerald-700'
  if (state === 'failed') return 'border-rose-200 bg-rose-50 text-rose-700'
  return 'border-slate-200 bg-slate-50 text-slate-500'
}

function connectionCheckedAt(verification) {
  if (!verification?.checked_at) return ''
  const value = new Date(verification.checked_at)
  if (Number.isNaN(value.getTime())) return ''
  const time = new Intl.DateTimeFormat(locale.value || undefined, {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  }).format(value)
  return t('adminPages.monitoring.assetConnectionCheckedAt', { time })
}

function connectionStateTitle(verification) {
  const checkedAt = connectionCheckedAt(verification)
  if (!checkedAt) return connectionStateText(verification)
  return `${connectionStateText(verification)} · ${checkedAt}`
}

function componentInstallationClass(state) {
  const { installation } = componentStatePresentation(state)
  if (installation === 'installed')
    return 'border-emerald-200 bg-emerald-50 text-emerald-700'
  if (installation === 'failed')
    return 'border-rose-200 bg-rose-50 text-rose-700'
  if (installation === 'installing')
    return 'border-sky-200 bg-sky-50 text-sky-700'
  if (installation === 'not_installed')
    return 'border-amber-200 bg-amber-50 text-amber-700'
  return 'border-slate-200 bg-slate-50 text-slate-500'
}

function componentRuntimeVisible(state) {
  return componentStatePresentation(state).showRuntime
}

function componentRuntimeText(state) {
  const { runtime } = componentStatePresentation(state)
  const keys = {
    online: 'componentRuntimeOnline',
    abnormal: 'componentRuntimeAbnormal',
    unknown: 'componentRuntimeUnknown'
  }
  return t(
    `adminPages.monitoring.${keys[runtime] || 'componentRuntimeUnknown'}`
  )
}

function componentRuntimeClass(state) {
  const { runtime } = componentStatePresentation(state)
  if (runtime === 'online') return 'text-emerald-700'
  if (runtime === 'abnormal') return 'text-rose-700'
  return 'text-amber-700'
}

function componentStateTitle(state) {
  if (state?.reason) return state.reason
  const installation = componentInstallationText(state)
  if (!componentRuntimeVisible(state)) return installation
  return `${installation} · ${componentRuntimeText(state)}`
}

function resetHostForm() {
  Object.assign(form, defaultHostForm())
  resetHostConnectionTest()
}

function resetHostConnectionTest() {
  hostConnectionStatus.value = 'idle'
  testedHostConnectionSignature.value = ''
  attemptedHostConnectionSignature.value = ''
  hostConnectionMessage.value = ''
  hostVerificationReceipt.value = ''
}

function openCreateHost() {
  resetHostForm()
  showHostForm.value = true
}

function closeHostForm() {
  resetHostForm()
  showHostForm.value = false
}

function editHost(host, options = {}) {
  Object.assign(form, {
    id: host.id,
    hostname: host.hostname || '',
    address: host.address || '',
    sshUser: host.ssh_user || 'root',
    sshPort: host.ssh_port || 22,
    sshAuthType:
      host.ssh_auth_type ||
      (host.ssh_key_id || host.ssh_key ? 'key' : 'password'),
    sshKeyId:
      host.ssh_key_id ||
      host.sshKeyId ||
      host.ssh_credential_id ||
      host.sshCredentialId ||
      ''
  })
  resetHostConnectionTest()
  showHostForm.value = true
  if (options.focus === 'ssh') {
    window.setTimeout(() => {
      document
        .querySelector('[data-host-connection-section]')
        ?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }, 0)
  }
}

function hostPayload() {
  const payload = {
    hostname: form.hostname,
    address: form.address,
    ssh_user: form.sshUser,
    ssh_port: Number(form.sshPort || 22),
    ssh_auth_type: form.sshAuthType,
    enabled: true
  }
  payload.ssh_credential_id = form.sshKeyId ? Number(form.sshKeyId) : null
  if (hostVerificationReceipt.value) {
    payload.ssh_verification_receipt = hostVerificationReceipt.value
  }
  return payload
}

function hostConnectionPayload() {
  return {
    host_id: form.id ? Number(form.id) : null,
    address: String(form.address || '').trim(),
    ssh_user: String(form.sshUser || '').trim() || 'root',
    ssh_port: Number(form.sshPort || 22),
    ssh_auth_type: form.sshAuthType,
    ssh_credential_id: form.sshKeyId ? Number(form.sshKeyId) : null
  }
}

function sshVerificationFieldCode(err) {
  const payload = err?.response?.data
  const body =
    payload?.data && typeof payload.data === 'object' ? payload.data : payload
  const fieldErrors = body?.field_errors || body || {}
  const value = fieldErrors.ssh_verification_receipt
  return String(Array.isArray(value) ? value[0] : value || '')
}

async function testHostConnection() {
  if (!canTestHostConnection.value) return
  const signature = hostConnectionSignature.value
  testingHostConnection.value = true
  attemptedHostConnectionSignature.value = signature
  hostConnectionStatus.value = 'testing'
  hostConnectionMessage.value = ''
  hostVerificationReceipt.value = ''
  try {
    const result = await monitoringStackApi.testHostConnection(
      hostConnectionPayload()
    )
    if (signature !== hostConnectionSignature.value) {
      resetHostConnectionTest()
      return
    }
    testedHostConnectionSignature.value = signature
    hostVerificationReceipt.value = result?.verification_receipt || ''
    hostConnectionStatus.value = 'success'
    hostConnectionMessage.value = t(
      'adminPages.monitoring.sshConnectionSuccessDetail',
      { latency: result?.latency_ms || 0 }
    )
  } catch (err) {
    if (signature !== hostConnectionSignature.value) {
      resetHostConnectionTest()
      return
    }
    testedHostConnectionSignature.value = ''
    hostVerificationReceipt.value = ''
    hostConnectionStatus.value = 'error'
    hostConnectionMessage.value = getApiErrorMessage(
      err,
      t('adminPages.monitoring.sshConnectionFailedDetail')
    )
  } finally {
    testingHostConnection.value = false
  }
}

function toggleHost(id, checked) {
  const next = new Set(selectedHostIds.value)
  if (checked) next.add(id)
  else next.delete(id)
  selectedHostIds.value = [...next]
}

function clearSelection() {
  selectedHostIds.value = []
}

function resetCategrafForm() {
  categrafStep.value = 0
  categrafPreviewData.value = null
  categrafPreviewSignature.value = ''
  categrafPreviewText.value = ''
  showAnsiblePreview.value = false
  showManualCommands.value = false
  manualCommandsCopied.value = false
}

function captureDeploymentSettingsBaseline() {
  Object.keys(deploymentSettingsBaseline).forEach((key) => {
    deploymentSettingsBaseline[key] = categrafForm[key]
  })
}

function deploymentSettingChanged(key) {
  return (
    String(categrafForm[key] || '').trim() !==
    String(deploymentSettingsBaseline[key] || '').trim()
  )
}

function resetDeploymentSettings() {
  Object.keys(deploymentSettingsBaseline).forEach((key) => {
    categrafForm[key] = deploymentSettingsBaseline[key]
  })
}

function openBulkInstallChooser() {
  showBulkInstallChooser.value = true
}

function closeBulkInstallChooser() {
  showBulkInstallChooser.value = false
}

function chooseBulkInstall() {
  if (!selectedHostIds.value.length) return
  closeBulkInstallChooser()
  openCategrafInstall()
}

function openCategrafInstall() {
  capabilityAdjustmentMode.value = false
  initialCategrafProfiles.value = []
  capabilityBaseJobId.value = null
  resetCategrafForm()
  showCategrafForm.value = true
}

function closeCategrafInstall() {
  const clearAdjustmentRoute = capabilityAdjustmentMode.value
  resetCategrafForm()
  showCategrafForm.value = false
  capabilityAdjustmentMode.value = false
  initialCategrafProfiles.value = []
  capabilityBaseJobId.value = null
  if (clearAdjustmentRoute) {
    router.replace({
      query: Object.fromEntries(
        Object.entries(route.query).filter(
          ([key]) => !['adjust', 'host', 'baseJob', 'profiles'].includes(key)
        )
      )
    })
  }
}

function canEnterCategrafStep(index) {
  if (capabilityAdjustmentMode.value && index === 0) return false
  if (index > 0 && !selectedHostIds.value.length) return false
  if (index > 1) {
    if (capabilityAdjustmentMode.value && !newCategrafProfiles.value.length)
      return false
    if (!capabilityAdjustmentMode.value && !categrafForm.profiles.length)
      return false
  }
  if (
    index > 2 &&
    (!deploymentSettingsValid.value ||
      (capabilityAdjustmentMode.value && !newCapabilityParamsValid.value))
  )
    return false
  return true
}

async function openCapabilityAdjustmentFromRoute() {
  if (route.query.adjust !== 'categraf') return
  const hostId = Number(route.query.host)
  const baseJobId = Number(route.query.baseJob)
  const host = hosts.value.find((item) => Number(item.id) === hostId)
  if (!host) return

  const availableProfiles = new Set(
    profiles.value.map((profile) => String(profile.id))
  )
  const requestedProfiles = String(route.query.profiles || '')
    .split(',')
    .map((profile) => profile.trim())
    .filter(Boolean)
  const existingProfiles = (
    requestedProfiles.length ? requestedProfiles : ['linux-basic']
  ).filter((profile) => availableProfiles.has(profile))

  resetCategrafForm()
  selectedHostIds.value = [host.id]
  capabilityAdjustmentMode.value = true
  capabilityBaseJobId.value =
    Number.isInteger(baseJobId) && baseJobId > 0 ? baseJobId : null
  if (capabilityBaseJobId.value) {
    try {
      const baseJob = await monitoringStackApi.getJob(capabilityBaseJobId.value)
      categrafForm.baseUrl = baseJob.base_url || categrafForm.baseUrl
      categrafForm.n9eUrl = baseJob.n9e_url || categrafForm.n9eUrl
      categrafForm.installDir = baseJob.install_dir || categrafForm.installDir
      categrafForm.image = baseJob.image || categrafForm.image
    } catch (err) {
      error.value = getApiErrorMessage(
        err,
        t('adminPages.monitoring.deploymentSettingsLoadFailed')
      )
      return
    }
  }
  captureDeploymentSettingsBaseline()
  initialCategrafProfiles.value = existingProfiles
  categrafForm.profiles = [...existingProfiles]
  categrafStep.value = 1
  showCategrafForm.value = true
}

function goCategrafStep(index) {
  if (!canEnterCategrafStep(index)) return
  categrafStep.value = Math.max(
    0,
    Math.min(index, categrafSteps.value.length - 1)
  )
}

function nextCategrafStep() {
  if (!canGoNextCategraf.value) return
  goCategrafStep(categrafStep.value + 1)
}

function prevCategrafStep() {
  goCategrafStep(categrafStep.value - 1)
}

function applyConfig(config) {
  const installer = config?.installer || {}
  const base = installer.base_url || window.location.origin
  const installerBaseUrl = base.endsWith('/api/v1/monitoring/installer')
    ? base
    : `${base.replace(/\/+$/, '')}/api/v1/monitoring/installer`
  categrafForm.baseUrl = installerBaseUrl
  categrafForm.n9eUrl = installer.n9e_url || config?.n9e_url || ''
  categrafForm.installDir = installer.install_dir || '/opt/categraf'
  categrafForm.image = 'flashcatcloud/categraf:latest'
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [
      configData,
      profileData,
      hostData,
      credentialData,
      reconciliationData
    ] = await Promise.all([
      monitoringStackApi.getConfig(),
      monitoringStackApi.getProfiles(),
      monitoringStackApi.getHosts(),
      monitoringStackApi.getCredentials({ status: 'active', assignable: true }),
      monitoringStackApi.getAssetsReconciliation()
    ])
    profiles.value = normalizeList(profileData)
    hosts.value = normalizeList(hostData)
    sshCredentials.value = normalizeList(credentialData)
    assetReconciliation.value = reconciliationData || {}
    selectedHostIds.value = selectedHostIds.value.filter((id) =>
      hosts.value.some((host) => host.id === id)
    )
    applyConfig(configData)
  } catch (err) {
    error.value = err?.response?.data?.detail || err.message
  } finally {
    loading.value = false
  }
}

async function importDiscoveredAsset(asset) {
  if (!asset?.can_import) return
  const key = `${asset.source}:${asset.key}`
  importingAssetKey.value = key
  try {
    await monitoringStackApi.createHost({
      hostname: asset.hostname || asset.address,
      address: asset.address || asset.hostname,
      ssh_user: 'root',
      ssh_port: 22,
      ssh_auth_type: 'password',
      labels: {
        source: asset.source,
        imported_from: 'monitoring_discovery'
      },
      enabled: true
    })
    await load()
  } finally {
    importingAssetKey.value = ''
  }
}

async function saveHost() {
  if (!isHostConnectionVerified.value) return
  saving.value = true
  try {
    if (form.id) await monitoringStackApi.updateHost(form.id, hostPayload())
    else await monitoringStackApi.createHost(hostPayload())
    closeHostForm()
    await load()
  } catch (err) {
    const verificationCode = sshVerificationFieldCode(err)
    if (
      ['SSH_VERIFICATION_EXPIRED', 'SSH_VERIFICATION_MISMATCH'].includes(
        verificationCode
      )
    ) {
      resetHostConnectionTest()
      hostConnectionStatus.value = 'error'
      hostConnectionMessage.value = t(
        verificationCode === 'SSH_VERIFICATION_EXPIRED'
          ? 'adminPages.monitoring.sshVerificationExpired'
          : 'adminPages.monitoring.sshVerificationMismatch'
      )
    } else {
      error.value = getApiErrorMessage(
        err,
        t('adminPages.monitoring.hostSaveFailed')
      )
    }
  } finally {
    saving.value = false
  }
}

watch(hostConnectionSignature, (signature) => {
  if (
    attemptedHostConnectionSignature.value &&
    signature !== attemptedHostConnectionSignature.value
  ) {
    resetHostConnectionTest()
  }
})

async function deleteHost(host) {
  if (!window.confirm(`${t('common.delete')} ${host.hostname}?`)) return
  await monitoringStackApi.deleteHost(host.id)
  selectedHostIds.value = selectedHostIds.value.filter((id) => id !== host.id)
  if (form.id === host.id) closeHostForm()
  await load()
}

function categrafJobPayload() {
  return {
    component: 'categraf',
    host_ids: selectedHostIds.value,
    profiles: categrafForm.profiles,
    labels: {
      region: categrafForm.region,
      env: categrafForm.env,
      team: categrafForm.team,
      service: categrafForm.service
    },
    params: {
      mysql_address: categrafForm.mysqlAddress,
      mysql_user: categrafForm.mysqlUser,
      mysql_password: categrafForm.mysqlPassword,
      mysql_parameters: categrafForm.mysqlParameters,
      redis_address: categrafForm.redisAddress,
      redis_username: categrafForm.redisUsername,
      redis_password: categrafForm.redisPassword,
      nginx_status_url: categrafForm.nginxStatusUrl
    },
    base_url: categrafForm.baseUrl,
    n9e_url: categrafForm.n9eUrl,
    install_dir: categrafForm.installDir,
    image: categrafForm.image,
    base_job_id: capabilityAdjustmentMode.value
      ? capabilityBaseJobId.value
      : undefined
  }
}

async function fetchCategrafPreviewData() {
  if (isCategrafPreviewCurrent.value) return categrafPreviewData.value
  const data = await monitoringStackApi.previewAnsible(categrafJobPayload())
  categrafPreviewData.value = data
  categrafPreviewSignature.value = currentCategrafSignature.value
  return data
}

async function previewCategraf() {
  if (showAnsiblePreview.value && isCategrafPreviewCurrent.value) {
    showAnsiblePreview.value = false
    return
  }
  previewingCategraf.value = true
  try {
    const data = await fetchCategrafPreviewData()
    categrafPreviewText.value = [
      '# inventory',
      data.inventory,
      '# vars',
      JSON.stringify(data.vars, null, 2)
    ].join('\n')
    showAnsiblePreview.value = true
  } finally {
    previewingCategraf.value = false
  }
}

async function generateCategrafCommands() {
  if (
    showManualCommands.value &&
    isCategrafPreviewCurrent.value &&
    manualInstallCommands.value
  ) {
    showManualCommands.value = false
    return
  }
  previewingCategraf.value = true
  try {
    await fetchCategrafPreviewData()
    showManualCommands.value = true
    manualCommandsCopied.value = false
  } finally {
    previewingCategraf.value = false
  }
}

async function copyManualCategrafCommands() {
  if (!manualInstallCommands.value) return
  const copied = await copyText(manualInstallCommands.value)
  if (!copied) return
  manualCommandsCopied.value = true
  window.setTimeout(() => {
    manualCommandsCopied.value = false
  }, 1600)
}

async function copyText(text) {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
      return true
    }
  } catch (err) {
    // Fall back for non-secure origins or clipboard permission denial.
  }

  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.setAttribute('readonly', '')
  textarea.style.position = 'fixed'
  textarea.style.left = '-9999px'
  textarea.style.top = '0'
  document.body.appendChild(textarea)
  textarea.focus()
  textarea.select()
  let copied = false
  try {
    copied = document.execCommand('copy')
  } finally {
    textarea.remove()
  }
  return copied
}

async function runCategrafInstall() {
  if (capabilityAdjustmentMode.value && !newCategrafProfiles.value.length)
    return
  runningCategraf.value = true
  try {
    const data = await monitoringStackApi.createJob(categrafJobPayload())
    closeCategrafInstall()
    notifyJobDispatched(data)
    await load()
  } finally {
    runningCategraf.value = false
  }
}

function notifyJobDispatched(job) {
  showSuccess(t('adminPages.monitoring.jobDispatched', { id: job.id }), 8000, {
    title: t('adminPages.monitoring.jobDispatchedTitle'),
    action: {
      label: t('adminPages.monitoring.viewTaskDetails'),
      onClick: () =>
        router.push({
          path: '/management/monitoring/jobs',
          query: { job: String(job.id) }
        })
    }
  })
}

onMounted(async () => {
  await load()
  await openCapabilityAdjustmentFromRoute()
})
</script>

<style scoped>
.asset-status-table :deep(.admin-table-head),
.asset-status-table :deep(.admin-table-cell) {
  padding-left: 0.5rem;
  padding-right: 0.5rem;
}
</style>
