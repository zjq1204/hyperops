<template>
  <AdminLayout>
    <PageFrame
      variant="soft"
      :title="t('adminPages.monitoring.assetsTitle')"
    >
      <AdminListSection>
        <template #filterFields>
          <label class="admin-filter-field min-w-[11.5rem]">
            <span class="admin-filter-label">{{ t('adminPages.monitoring.alignmentStatus') }}</span>
            <select v-model="filters.alignmentStatus" class="admin-filter-control">
              <option value="all">{{ t('common.all') }}</option>
              <option value="n9e_missing">{{ t('adminPages.monitoring.n9eNotVisible') }}</option>
              <option value="categraf_missing">{{ t('adminPages.monitoring.categoryCategrafNotInstalled') }}</option>
              <option value="prometheus_missing">{{ t('adminPages.monitoring.categoryHostNotScrapedByPrometheus') }}</option>
            </select>
          </label>
          <label class="admin-filter-field min-w-[11.5rem]">
            <span class="admin-filter-label">{{ t('adminPages.monitoring.categrafStatus') }}</span>
            <select v-model="filters.categrafStatus" class="admin-filter-control">
              <option value="all">{{ t('common.all') }}</option>
              <option value="unknown">{{ t('adminPages.monitoring.installStatusNotInstalled') }}</option>
              <option value="installing">{{ t('adminPages.monitoring.statusInstalling') }}</option>
              <option value="success">{{ t('adminPages.monitoring.statusSuccess') }}</option>
              <option value="failed">{{ t('adminPages.monitoring.statusFailed') }}</option>
            </select>
          </label>
          <label class="admin-filter-field min-w-[11.5rem]">
            <span class="admin-filter-label">{{ t('adminPages.monitoring.blackboxStatus') }}</span>
            <select v-model="filters.blackboxStatus" class="admin-filter-control">
              <option value="all">{{ t('common.all') }}</option>
              <option value="unknown">{{ t('adminPages.monitoring.installStatusNotInstalled') }}</option>
              <option value="installing">{{ t('adminPages.monitoring.statusInstalling') }}</option>
              <option value="success">{{ t('adminPages.monitoring.statusSuccess') }}</option>
              <option value="failed">{{ t('adminPages.monitoring.statusFailed') }}</option>
            </select>
          </label>
        </template>
        <template #toolbarEnd>
          <BaseButton variant="outline" size="sm" :loading="loading" @click="load">
            {{ t('common.refresh') }}
          </BaseButton>
          <span class="inline-flex min-h-9 items-center rounded-full bg-slate-100 px-3 text-xs font-semibold text-slate-600">
            {{ t('adminPages.monitoring.selectedHostCount', { count: selectedHostIds.length }) }}
          </span>
          <BaseButton
            variant="outline"
            size="sm"
            :disabled="!selectedHostIds.length"
            @click="openBulkInstallChooser"
          >
            {{ t('adminPages.monitoring.installComponents') }}
          </BaseButton>
          <BaseButton variant="primary" size="sm" @click="openCreateHost">
            {{ t('adminPages.monitoring.addHost') }}
          </BaseButton>
        </template>
        <AdminPageState :loading="loading" :error="error" :empty="false">
          <section class="grid gap-4">
            <section
              v-if="discoveredAssets.length"
              class="rounded-xl border border-slate-200 bg-white px-4 py-4 shadow-sm"
            >
              <div class="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
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
                    <tr class="border-b border-slate-100 text-xs font-semibold text-slate-500">
                      <th class="py-2 pr-4">{{ t('adminPages.monitoring.source') }}</th>
                      <th class="py-2 pr-4">{{ t('adminPages.monitoring.hostname') }}</th>
                      <th class="py-2 pr-4">{{ t('adminPages.monitoring.address') }}</th>
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
                        <span v-if="asset.port" class="text-slate-400">:{{ asset.port }}</span>
                      </td>
                      <td class="py-3 pr-4 text-slate-500">
                        {{ discoveredStatusText(asset) }}
                      </td>
                      <td class="py-3 pr-4">
                        <BaseButton
                          variant="outline"
                          size="sm"
                          :disabled="!asset.can_import"
                          :loading="importingAssetKey === `${asset.source}:${asset.key}`"
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

            <AdminTable>
              <thead>
                <tr>
                  <th class="admin-table-head"></th>
                  <th class="admin-table-head">{{ t('adminPages.monitoring.hostname') }}</th>
                  <th class="admin-table-head">{{ t('adminPages.monitoring.address') }}</th>
                  <th class="admin-table-head">{{ t('adminPages.monitoring.componentCategraf') }}</th>
                  <th class="admin-table-head">{{ t('adminPages.monitoring.componentBlackbox') }}</th>
                  <th class="admin-table-head">{{ t('common.actions') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="!filteredHosts.length" class="admin-table-row">
                  <td class="admin-table-cell text-slate-400" colspan="6">
                    {{ t('common.noData') }}
                  </td>
                </tr>
                <tr v-for="host in filteredHosts" :key="host.id" class="admin-table-row align-top">
                  <td class="admin-table-cell">
                    <input
                      type="checkbox"
                      :checked="selectedHostIds.includes(host.id)"
                      @change="toggleHost(host.id, $event.target.checked)"
                    />
                  </td>
                  <td class="admin-table-cell font-medium text-slate-900">{{ host.hostname }}</td>
                  <td class="admin-table-cell text-slate-600">
                    {{ host.address }}
                    <p class="mt-1 text-xs text-slate-400">
                      {{ host.ssh_user || 'root' }}:{{ host.ssh_port || 22 }}
                      <span> / {{ sshAuthText(host) }}</span>
                    </p>
                  </td>
                  <td class="admin-table-cell">
                    <div class="grid gap-1.5">
                      <span
                        v-for="finding in hostComponentFindings(host, 'categraf')"
                        :key="finding.id"
                        class="inline-flex w-fit rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-700"
                      >
                        {{ hostComponentFindingLabel(finding, 'categraf') }}
                      </span>
                      <span
                        v-if="shouldShowComponentStatus(host, 'categraf')"
                        class="inline-flex w-fit rounded-full border px-2.5 py-1 text-xs font-semibold"
                        :class="componentDisplayClass(host, 'categraf')"
                        :title="componentDisplayTitle(host, 'categraf')"
                      >
                        {{ componentDisplayText(host, 'categraf') }}
                      </span>
                      <router-link
                        v-if="statusFor(host, 'categraf').last_job_id"
                        class="text-xs font-medium text-slate-500 hover:text-slate-900"
                        to="/management/monitoring/jobs"
                      >
                        #{{ statusFor(host, 'categraf').last_job_id }}
                      </router-link>
                    </div>
                  </td>
                  <td class="admin-table-cell">
                    <div class="grid gap-1.5">
                      <span
                        v-for="finding in hostComponentFindings(host, 'blackbox')"
                        :key="finding.id"
                        class="inline-flex w-fit rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-700"
                      >
                        {{ hostComponentFindingLabel(finding, 'blackbox') }}
                      </span>
                      <span
                        v-if="shouldShowComponentStatus(host, 'blackbox')"
                        class="inline-flex w-fit rounded-full border px-2.5 py-1 text-xs font-semibold"
                        :class="componentDisplayClass(host, 'blackbox')"
                        :title="componentDisplayTitle(host, 'blackbox')"
                      >
                        {{ componentDisplayText(host, 'blackbox') }}
                      </span>
                      <router-link
                        v-if="statusFor(host, 'blackbox').last_job_id"
                        class="text-xs font-medium text-slate-500 hover:text-slate-900"
                        to="/management/monitoring/jobs"
                      >
                        #{{ statusFor(host, 'blackbox').last_job_id }}
                      </router-link>
                    </div>
                  </td>
                  <td class="admin-table-cell">
                    <div class="admin-row-actions">
                      <BaseButton variant="outline" size="sm" @click="editHost(host)">
                        {{ t('common.edit') }}
                      </BaseButton>
                      <BaseButton variant="ghost" size="sm" @click="deleteHost(host)">
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
      :title="form.id ? t('adminPages.monitoring.editHost') : t('adminPages.monitoring.addHost')"
      size="md"
      @close="closeHostForm"
    >
      <form class="grid gap-4" @submit.prevent="saveHost">
        <div class="grid gap-3 sm:grid-cols-2">
          <label class="admin-filter-field">
            <span class="admin-filter-label">{{ t('adminPages.monitoring.hostname') }}</span>
            <input v-model="form.hostname" class="admin-filter-control" />
          </label>
          <label class="admin-filter-field">
            <span class="admin-filter-label">{{ t('adminPages.monitoring.address') }}</span>
            <input v-model="form.address" class="admin-filter-control" />
          </label>
          <label class="admin-filter-field">
            <span class="admin-filter-label">{{ t('adminPages.monitoring.sshUser') }}</span>
            <input v-model="form.sshUser" class="admin-filter-control" />
          </label>
          <label class="admin-filter-field">
            <span class="admin-filter-label">{{ t('adminPages.monitoring.sshPort') }}</span>
            <input v-model.number="form.sshPort" class="admin-filter-control" />
          </label>
        </div>
        <section class="rounded-xl border border-slate-200 bg-slate-50/70 p-4">
          <div class="flex flex-wrap items-center justify-between gap-3">
            <p class="text-sm font-semibold text-slate-900">
              {{ t('adminPages.monitoring.sshAuthMethod') }}
            </p>
            <div class="inline-flex rounded-lg border border-slate-200 bg-white p-1">
              <button
                type="button"
                class="rounded-md px-3 py-1.5 text-sm font-semibold transition"
                :class="form.sshAuthType === 'password' ? 'bg-slate-900 text-white shadow-sm' : 'text-slate-500 hover:text-slate-900'"
                @click="form.sshAuthType = 'password'"
              >
                {{ t('adminPages.monitoring.sshAuthPassword') }}
              </button>
              <button
                type="button"
                class="rounded-md px-3 py-1.5 text-sm font-semibold transition"
                :class="form.sshAuthType === 'key' ? 'bg-slate-900 text-white shadow-sm' : 'text-slate-500 hover:text-slate-900'"
                @click="form.sshAuthType = 'key'"
              >
                {{ t('adminPages.monitoring.sshAuthKey') }}
              </button>
            </div>
          </div>

          <div v-if="form.sshAuthType === 'password'" class="mt-4">
            <label class="admin-filter-field">
              <span class="admin-filter-label">
                {{ t('adminPages.monitoring.sshPassword') }}
                <span v-if="form.id && form.hasSshPassword" class="ml-2 text-xs font-normal text-emerald-600">
                  {{ t('adminPages.monitoring.passwordConfigured') }}
                </span>
              </span>
              <input
                v-model="form.sshPassword"
                type="password"
                class="admin-filter-control"
                :placeholder="form.id && form.hasSshPassword ? t('adminPages.monitoring.passwordKeepHint') : ''"
              />
            </label>
          </div>

          <div v-else class="mt-4 grid gap-4">
            <label class="admin-filter-field">
              <span class="admin-filter-label">{{ t('adminPages.monitoring.savedSshKey') }}</span>
              <select v-model="form.sshKeyId" class="admin-filter-control">
                <option value="">{{ t('adminPages.monitoring.selectSshKey') }}</option>
                <option v-for="key in sshKeys" :key="key.id" :value="key.id">
                  {{ key.name }}
                </option>
              </select>
            </label>
            <div class="rounded-lg border border-dashed border-slate-300 bg-white px-4 py-3">
              <div class="grid gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
                <label class="admin-filter-field">
                  <span class="admin-filter-label">{{ t('adminPages.monitoring.sshKeyName') }}</span>
                  <input v-model="form.sshKeyUploadName" class="admin-filter-control" />
                </label>
                <label class="admin-filter-field">
                  <span class="admin-filter-label">{{ t('adminPages.monitoring.uploadSshKey') }}</span>
                  <input
                    type="file"
                    class="admin-filter-control"
                    accept=".pem,.key,.txt"
                    @change="handleSshKeyFile"
                  />
                </label>
              </div>
              <div class="mt-3 flex flex-wrap items-center justify-between gap-3">
                <p class="text-xs text-slate-500">
                  {{ t('adminPages.monitoring.sshKeyUploadHint') }}
                </p>
                <BaseButton
                  variant="outline"
                  type="button"
                  size="sm"
                  :disabled="!form.sshKeyUploadName || !form.sshKeyUploadContent"
                  :loading="uploadingSshKey"
                  @click="uploadSshKey"
                >
                  {{ t('adminPages.monitoring.saveSshKey') }}
                </BaseButton>
              </div>
            </div>
          </div>
        </section>
        <div class="flex flex-wrap justify-end gap-2 pt-2">
          <BaseButton variant="outline" type="button" @click="closeHostForm">
            {{ t('common.cancel') }}
          </BaseButton>
          <BaseButton variant="primary" type="submit" :loading="saving">
            {{ t('common.save') }}
          </BaseButton>
        </div>
      </form>
    </BaseModal>

    <BaseModal
      :show="showBulkInstallChooser"
      :title="t('adminPages.monitoring.bulkInstall')"
      size="md"
      @close="closeBulkInstallChooser"
    >
      <div class="grid gap-4">
        <div class="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3">
          <p class="text-sm font-semibold text-slate-900">
            {{ t('adminPages.monitoring.selectedHostsForInstall', { count: selectedHostIds.length }) }}
          </p>
          <p class="mt-1 text-xs text-slate-500">
            {{ selectedHostSummary }}
          </p>
        </div>
        <div class="grid gap-3 sm:grid-cols-2">
          <button
            type="button"
            class="rounded-xl border border-slate-200 bg-white p-4 text-left shadow-sm transition hover:border-slate-300 hover:bg-slate-50"
            @click="chooseBulkInstall('categraf')"
          >
            <span class="text-sm font-semibold text-slate-900">
              {{ t('adminPages.monitoring.installCategraf') }}
            </span>
            <span class="mt-2 block text-xs leading-5 text-slate-500">
              {{ t('adminPages.monitoring.installChoiceCategrafHint') }}
            </span>
          </button>
          <button
            type="button"
            class="rounded-xl border border-slate-200 bg-white p-4 text-left shadow-sm transition hover:border-slate-300 hover:bg-slate-50"
            @click="chooseBulkInstall('blackbox')"
          >
            <span class="text-sm font-semibold text-slate-900">
              {{ t('adminPages.monitoring.installBlackbox') }}
            </span>
            <span class="mt-2 block text-xs leading-5 text-slate-500">
              {{ t('adminPages.monitoring.installChoiceBlackboxHint') }}
            </span>
          </button>
        </div>
        <div class="flex justify-end">
          <BaseButton variant="outline" type="button" @click="closeBulkInstallChooser">
            {{ t('common.cancel') }}
          </BaseButton>
        </div>
      </div>
    </BaseModal>

    <BaseModal
      :show="showCategrafForm"
      :title="t('adminPages.monitoring.installCategraf')"
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
                index === categrafStep ? 'bg-white text-blue-700 shadow-sm ring-1 ring-blue-100' : 'text-slate-600 hover:bg-white/70',
                canEnterCategrafStep(index) ? '' : 'cursor-not-allowed opacity-50 hover:bg-transparent'
              ]"
              :disabled="!canEnterCategrafStep(index)"
              @click="goCategrafStep(index)"
            >
              <span
                class="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold"
                :class="index === categrafStep ? 'bg-blue-600 text-white' : index < categrafStep ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-200 text-slate-500'"
              >
                {{ index + 1 }}
              </span>
              <span class="min-w-0">
                <span class="block text-sm font-semibold">{{ step.title }}</span>
              </span>
            </button>
          </aside>

          <section class="min-h-[28rem] rounded-xl border border-slate-200 bg-white p-5">
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
                  <p class="truncate text-sm font-semibold text-slate-900">{{ host.hostname }}</p>
                  <p class="mt-1 truncate text-xs text-slate-500">
                    {{ host.address }} / {{ host.ssh_user || 'root' }}:{{ host.ssh_port || 22 }}
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
                    :class="categrafForm.profiles.length ? 'bg-blue-50 text-blue-700' : 'bg-rose-50 text-rose-700'"
                  >
                    {{ t('adminPages.monitoring.selectedProfileCount', { count: categrafForm.profiles.length }) }}
                  </span>
                </div>
                <p v-if="!categrafForm.profiles.length" class="mt-3 rounded-lg border border-rose-100 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                  {{ t('adminPages.monitoring.profileRequiredHint') }}
                </p>
              </div>
              <div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                <label
                  v-for="profile in profiles"
                  :key="profile.id"
                  class="group flex min-h-12 cursor-pointer items-center gap-3 rounded-xl border border-slate-200 bg-white p-3 transition hover:border-blue-200 hover:bg-blue-50/40 has-[:checked]:border-blue-300 has-[:checked]:bg-blue-50"
                >
                  <input v-model="categrafForm.profiles" type="checkbox" :value="profile.id" />
                  <span class="min-w-0">
                    <span class="block text-sm font-semibold text-slate-900">{{ profile.name || profile.id }}</span>
                  </span>
                </label>
              </div>
            </div>

            <div v-else-if="categrafStep === 2" class="grid gap-4">
              <div>
                <h3 class="text-base font-semibold text-slate-900">
                  {{ t('adminPages.monitoring.stepParamsTitle') }}
                </h3>
              </div>
              <section class="rounded-xl border border-slate-200 bg-slate-50/70 p-4">
                <h4 class="text-sm font-semibold text-slate-900">
                  {{ t('adminPages.monitoring.installLabels') }}
                </h4>
                <div class="mt-3 grid gap-3 sm:grid-cols-2">
                  <label class="admin-filter-field">
                    <span class="admin-filter-label">{{ t('adminPages.monitoring.region') }}</span>
                    <input v-model="categrafForm.region" class="admin-filter-control" />
                  </label>
                  <label class="admin-filter-field">
                    <span class="admin-filter-label">{{ t('adminPages.monitoring.env') }}</span>
                    <input v-model="categrafForm.env" class="admin-filter-control" />
                  </label>
                  <label class="admin-filter-field">
                    <span class="admin-filter-label">{{ t('adminPages.monitoring.team') }}</span>
                    <input v-model="categrafForm.team" class="admin-filter-control" />
                  </label>
                  <label class="admin-filter-field">
                    <span class="admin-filter-label">{{ t('adminPages.monitoring.service') }}</span>
                    <input v-model="categrafForm.service" class="admin-filter-control" />
                  </label>
                </div>
              </section>

              <section v-if="showCategrafProfileSettings" class="grid gap-3">
                <div v-if="needsCategrafMysqlConfig" class="rounded-xl border border-slate-200 bg-white p-4">
                  <h4 class="text-sm font-semibold text-slate-800">
                    {{ t('adminPages.monitoring.mysqlConfig') }}
                  </h4>
                  <div class="mt-3 grid gap-3 sm:grid-cols-2">
                    <label class="admin-filter-field">
                      <span class="admin-filter-label">{{ t('adminPages.monitoring.mysqlAddress') }}</span>
                      <input v-model="categrafForm.mysqlAddress" class="admin-filter-control" placeholder="127.0.0.1:3306" />
                    </label>
                    <label class="admin-filter-field">
                      <span class="admin-filter-label">{{ t('adminPages.monitoring.mysqlUser') }}</span>
                      <input v-model="categrafForm.mysqlUser" class="admin-filter-control" placeholder="exporter" />
                    </label>
                    <label class="admin-filter-field">
                      <span class="admin-filter-label">{{ t('adminPages.monitoring.mysqlPassword') }}</span>
                      <input v-model="categrafForm.mysqlPassword" type="password" class="admin-filter-control" />
                    </label>
                    <label class="admin-filter-field">
                      <span class="admin-filter-label">{{ t('adminPages.monitoring.mysqlParameters') }}</span>
                      <input v-model="categrafForm.mysqlParameters" class="admin-filter-control" placeholder="tls=false" />
                    </label>
                  </div>
                </div>
                <div v-if="needsCategrafRedisConfig" class="rounded-xl border border-slate-200 bg-white p-4">
                  <h4 class="text-sm font-semibold text-slate-800">
                    {{ t('adminPages.monitoring.redisConfig') }}
                  </h4>
                  <div class="mt-3 grid gap-3 sm:grid-cols-2">
                    <label class="admin-filter-field">
                      <span class="admin-filter-label">{{ t('adminPages.monitoring.redisAddress') }}</span>
                      <input v-model="categrafForm.redisAddress" class="admin-filter-control" placeholder="127.0.0.1:6379" />
                    </label>
                    <label class="admin-filter-field">
                      <span class="admin-filter-label">{{ t('adminPages.monitoring.redisUsername') }}</span>
                      <input v-model="categrafForm.redisUsername" class="admin-filter-control" placeholder="default" />
                    </label>
                    <label class="admin-filter-field sm:col-span-2">
                      <span class="admin-filter-label">{{ t('adminPages.monitoring.redisPassword') }}</span>
                      <input v-model="categrafForm.redisPassword" type="password" class="admin-filter-control" />
                    </label>
                  </div>
                </div>
                <div v-if="needsCategrafNginxConfig" class="rounded-xl border border-slate-200 bg-white p-4">
                  <h4 class="text-sm font-semibold text-slate-800">
                    {{ t('adminPages.monitoring.nginxConfig') }}
                  </h4>
                  <label class="admin-filter-field mt-3">
                    <span class="admin-filter-label">{{ t('adminPages.monitoring.nginxStatusUrl') }}</span>
                    <input v-model="categrafForm.nginxStatusUrl" class="admin-filter-control" placeholder="http://127.0.0.1/nginx_status" />
                  </label>
                </div>
              </section>
              <section v-else class="rounded-xl border border-dashed border-slate-200 bg-slate-50/70 p-4 text-sm text-slate-500">
                {{ t('adminPages.monitoring.noProfileParams') }}
              </section>
              <section class="rounded-xl border border-slate-200 bg-slate-50/70 p-4">
                <h4 class="text-sm font-semibold text-slate-900">
                  {{ t('adminPages.monitoring.deploySettings') }}
                </h4>
                <div class="mt-3 grid gap-3 sm:grid-cols-2">
                  <label class="admin-filter-field sm:col-span-2">
                    <span class="admin-filter-label">{{ t('adminPages.monitoring.n9eUrl') }}</span>
                    <input v-model="categrafForm.n9eUrl" class="admin-filter-control" />
                  </label>
                  <label class="admin-filter-field">
                    <span class="admin-filter-label">{{ t('adminPages.monitoring.installDir') }}</span>
                    <input v-model="categrafForm.installDir" class="admin-filter-control" />
                  </label>
                  <label class="admin-filter-field">
                    <span class="admin-filter-label">{{ t('adminPages.monitoring.image') }}</span>
                    <input v-model="categrafForm.image" class="admin-filter-control" />
                  </label>
                  <label class="admin-filter-field sm:col-span-2">
                    <span class="admin-filter-label">{{ t('adminPages.monitoring.baseUrl') }}</span>
                    <input v-model="categrafForm.baseUrl" class="admin-filter-control" />
                  </label>
                </div>
              </section>
            </div>

            <div v-else class="grid gap-4">
              <div>
                <h3 class="text-base font-semibold text-slate-900">
                  {{ t('adminPages.monitoring.stepPreviewTitle') }}
                </h3>
              </div>
              <section class="grid gap-3 rounded-xl border border-slate-200 bg-white p-4">
                <div class="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <h4 class="text-sm font-semibold text-slate-900">
                      {{ t('adminPages.monitoring.ansiblePreview') }}
                    </h4>
                  </div>
                  <BaseButton variant="outline" type="button" :loading="previewingCategraf" @click="previewCategraf">
                    {{ showAnsiblePreview ? t('adminPages.monitoring.collapsePreview') : t('adminPages.monitoring.previewAnsible') }}
                  </BaseButton>
                </div>
                <pre v-if="showAnsiblePreview && categrafPreviewText" class="max-h-80 overflow-auto whitespace-pre-wrap rounded-lg bg-slate-950 p-3 text-xs leading-6 text-slate-100">{{ categrafPreviewText }}</pre>
              </section>
              <section class="grid gap-3 rounded-xl border border-slate-200 bg-white p-4">
                <div class="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <h4 class="text-sm font-semibold text-slate-900">
                      {{ t('adminPages.monitoring.manualCommandPreview') }}
                    </h4>
                  </div>
                  <div class="flex flex-wrap gap-2">
                    <BaseButton variant="outline" type="button" :loading="previewingCategraf" @click="generateCategrafCommands">
                      {{ showManualCommands ? t('adminPages.monitoring.collapsePreview') : t('adminPages.monitoring.generateManualCommands') }}
                    </BaseButton>
                    <BaseButton variant="outline" type="button" :disabled="!manualInstallCommands" @click="copyManualCategrafCommands">
                      {{ manualCommandsCopied ? t('adminPages.monitoring.commandCopied') : t('adminPages.monitoring.copyCommand') }}
                    </BaseButton>
                  </div>
                </div>
                <div v-if="showManualCommands && manualInstallCommands" class="overflow-hidden rounded-xl">
                  <pre class="max-h-72 overflow-auto whitespace-pre-wrap break-words bg-slate-950 p-4 text-xs leading-6 text-slate-100">{{ manualInstallCommands }}</pre>
                </div>
              </section>
            </div>
          </section>
        </div>

        <div class="flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 pt-4">
          <span class="text-xs text-slate-500">
            {{ t('adminPages.monitoring.stepProgress', { current: categrafStep + 1, total: categrafSteps.length }) }}
          </span>
          <div class="flex flex-wrap justify-end gap-2">
            <BaseButton variant="outline" type="button" @click="closeCategrafInstall">
              {{ t('common.cancel') }}
            </BaseButton>
            <BaseButton variant="outline" type="button" :disabled="categrafStep === 0" @click="prevCategrafStep">
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
            <BaseButton v-else variant="primary" type="submit" :loading="runningCategraf">
              {{ t('adminPages.monitoring.runInstall') }}
            </BaseButton>
          </div>
        </div>
      </form>
    </BaseModal>

    <BaseModal
      :show="showBlackboxForm"
      :title="t('adminPages.monitoring.installBlackbox')"
      size="md"
      @close="closeBlackboxInstall"
    >
      <form class="grid gap-4" @submit.prevent="runBlackboxInstall">
        <label class="admin-filter-field">
          <span class="admin-filter-label">{{ t('adminPages.monitoring.probeName') }}</span>
          <input v-model="blackboxForm.probeName" class="admin-filter-control" />
        </label>
        <div class="grid gap-3 sm:grid-cols-2">
          <label class="admin-filter-field">
            <span class="admin-filter-label">{{ t('adminPages.monitoring.blackboxPort') }}</span>
            <input v-model="blackboxForm.blackboxPort" class="admin-filter-control" />
          </label>
          <label class="admin-filter-field">
            <span class="admin-filter-label">{{ t('adminPages.monitoring.installDir') }}</span>
            <input v-model="blackboxForm.installDir" class="admin-filter-control" />
          </label>
        </div>
        <label class="admin-filter-field">
          <span class="admin-filter-label">{{ t('adminPages.monitoring.image') }}</span>
          <input v-model="blackboxForm.image" class="admin-filter-control" />
        </label>
        <label class="admin-filter-field">
          <span class="admin-filter-label">{{ t('adminPages.monitoring.baseUrl') }}</span>
          <input v-model="blackboxForm.baseUrl" class="admin-filter-control" />
        </label>
        <pre v-if="blackboxPreviewText" class="max-h-80 overflow-auto whitespace-pre-wrap rounded-lg bg-slate-950 p-3 text-xs leading-6 text-slate-100">{{ blackboxPreviewText }}</pre>
        <div class="flex flex-wrap justify-end gap-2 pt-2">
          <BaseButton variant="outline" type="button" @click="closeBlackboxInstall">
            {{ t('common.cancel') }}
          </BaseButton>
          <BaseButton variant="outline" type="button" :loading="previewingBlackbox" @click="previewBlackbox">
            {{ t('adminPages.monitoring.previewAnsible') }}
          </BaseButton>
          <BaseButton variant="primary" type="submit" :loading="runningBlackbox">
            {{ t('adminPages.monitoring.runInstall') }}
          </BaseButton>
        </div>
      </form>
    </BaseModal>
  </AdminLayout>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AdminLayout from '@/admin/layout/AdminLayout.vue'
import AdminListSection from '@/admin/components/AdminListSection.vue'
import AdminPageState from '@/admin/components/AdminPageState.vue'
import AdminTable from '@/admin/components/AdminTable.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseModal from '@/components/ui/BaseModal.vue'
import PageFrame from '@/components/ui/PageFrame.vue'
import { monitoringStackApi } from '@/admin/api/monitoringStack'

const { t } = useI18n()
const loading = ref(false)
const saving = ref(false)
const previewingCategraf = ref(false)
const runningCategraf = ref(false)
const previewingBlackbox = ref(false)
const runningBlackbox = ref(false)
const error = ref('')
const profiles = ref([])
const hosts = ref([])
const sshKeys = ref([])
const hostFindings = ref([])
const assetReconciliation = ref({})
const selectedHostIds = ref([])
const importingAssetKey = ref('')
const uploadingSshKey = ref(false)
const filters = reactive({
  alignmentStatus: 'all',
  categrafStatus: 'all',
  blackboxStatus: 'all'
})
const categrafStep = ref(0)
const categrafPreviewData = ref(null)
const categrafPreviewSignature = ref('')
const categrafPreviewText = ref('')
const showAnsiblePreview = ref(false)
const showManualCommands = ref(false)
const manualCommandsCopied = ref(false)
const blackboxPreviewText = ref('')
const showHostForm = ref(false)
const showBulkInstallChooser = ref(false)
const showCategrafForm = ref(false)
const showBlackboxForm = ref(false)
const form = reactive(defaultHostForm())
const needsCategrafMysqlConfig = computed(() => categrafForm.profiles.includes('mysql-rds') || categrafForm.profiles.includes('mysql'))
const needsCategrafRedisConfig = computed(() => categrafForm.profiles.includes('redis'))
const needsCategrafNginxConfig = computed(() => categrafForm.profiles.includes('nginx'))
const showCategrafProfileSettings = computed(() =>
  needsCategrafMysqlConfig.value || needsCategrafRedisConfig.value || needsCategrafNginxConfig.value
)
const filteredHosts = computed(() =>
  hosts.value.filter((host) => {
    return (
      alignmentMatches(host, filters.alignmentStatus) &&
      statusMatches(componentInstallStatus(host, 'categraf'), filters.categrafStatus) &&
      statusMatches(componentInstallStatus(host, 'blackbox'), filters.blackboxStatus)
    )
  })
)
const selectedHosts = computed(() =>
  selectedHostIds.value
    .map((id) => hosts.value.find((host) => host.id === id))
    .filter(Boolean)
)
const selectedHostSummary = computed(() => {
  if (!selectedHosts.value.length) return t('adminPages.monitoring.noSelectedHosts')
  return selectedHosts.value
    .slice(0, 4)
    .map((host) => `${host.hostname} / ${host.address}`)
    .join('，')
})
const discoveredAssets = computed(() => assetReconciliation.value?.results || [])
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
  if (categrafStep.value === 1) return categrafForm.profiles.length > 0
  return true
})
const currentCategrafSignature = computed(() => JSON.stringify(categrafJobPayload()))
const isCategrafPreviewCurrent = computed(() =>
  Boolean(categrafPreviewData.value && categrafPreviewSignature.value === currentCategrafSignature.value)
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
const blackboxForm = reactive({
  baseUrl: '',
  probeName: 'blackbox-center',
  blackboxPort: '9115',
  installDir: '/opt/blackbox-exporter',
  image: 'prom/blackbox-exporter:latest'
})

function defaultHostForm() {
  return {
    id: '',
    hostname: '',
    address: '',
    sshUser: 'root',
    sshPort: 22,
    sshAuthType: 'password',
    sshPassword: '',
    hasSshPassword: false,
    sshKeyId: '',
    sshKeyUploadName: '',
    sshKeyUploadContent: ''
  }
}

function normalizeList(data) {
  return data?.results || data || []
}

function statusFor(host, component) {
  return (
    (host.component_statuses || []).find((item) => item.component === component) || {
      component,
      status: 'unknown',
      runtime_status: 'unknown',
      runtime_reason: '',
      runtime_endpoint: '',
      runtime_checked_at: '',
      last_job_id: '',
      last_error: ''
    }
  )
}

function componentInstallStatus(host, component) {
  const value = String(statusFor(host, component).status || 'unknown').toLowerCase()
  return value === 'external' ? 'success' : value
}

function statusMatches(actual, expected) {
  return expected === 'all' || actual === expected
}

function alignmentMatches(host, expected) {
  if (expected === 'all') return true
  if (expected === 'n9e_missing') return hostN9eFindings(host).length > 0
  if (expected === 'categraf_missing') {
    return hostFindingsFor(host).some((finding) => finding.category === 'categraf_not_installed')
  }
  if (expected === 'prometheus_missing') {
    return hostFindingsFor(host).some((finding) => finding.category === 'host_not_scraped_by_prometheus')
  }
  return true
}

function hostFindingsFor(host) {
  return hostFindings.value.filter((finding) => {
    const details = finding.details || {}
    return details.host_id === host.id || finding.subject_key === host.hostname || finding.subject_key === host.address
  })
}

function hostFindingLabel(finding) {
  const labels = {
    host_not_in_n9e: t('adminPages.monitoring.categoryHostNotInN9e'),
    host_not_scraped_by_prometheus: t('adminPages.monitoring.categoryHostNotScrapedByPrometheus'),
    categraf_not_installed: t('adminPages.monitoring.categoryCategrafNotInstalled'),
    blackbox_not_installed: t('adminPages.monitoring.categoryBlackboxNotInstalled')
  }
  return labels[finding.category] || finding.title || t('common.emptyValue')
}

function hostComponentFindingLabel(finding, component) {
  if (
    (component === 'categraf' && finding.category === 'categraf_not_installed') ||
    (component === 'blackbox' && finding.category === 'blackbox_not_installed')
  ) {
    return t('adminPages.monitoring.installStatusNotInstalled')
  }

  return hostFindingLabel(finding)
}

function hostN9eFindings(host) {
  return hostFindingsFor(host).filter((finding) => finding.category === 'host_not_in_n9e')
}

function discoveredSourceText(source) {
  if (source === 'n9e') return 'n9e'
  if (source === 'prometheus') return 'Prometheus'
  return source || t('common.emptyValue')
}

function discoveredSourceClass(source) {
  if (source === 'n9e') return 'border-blue-200 bg-blue-50 text-blue-700'
  if (source === 'prometheus') return 'border-emerald-200 bg-emerald-50 text-emerald-700'
  return 'border-slate-200 bg-slate-50 text-slate-500'
}

function discoveredStatusText(asset) {
  if (asset.source === 'prometheus') {
    if (asset.health === 'up') return t('adminPages.monitoring.statusUp')
    if (asset.health) return t('adminPages.monitoring.statusDown')
  }
  return t('adminPages.monitoring.unmanagedAsset')
}

function hostComponentFindings(host, component) {
  const categories = component === 'blackbox'
    ? ['blackbox_not_installed']
    : ['categraf_not_installed']
  return hostFindingsFor(host).filter((finding) => categories.includes(finding.category))
}

function shouldShowComponentStatus(host, component) {
  const status = statusFor(host, component).status
  return status !== 'unknown' || hostComponentFindings(host, component).length === 0
}

function componentStatusText(status) {
  const value = String(status || 'unknown').toLowerCase()
  if (value === 'installing') return t('adminPages.monitoring.statusInstalling')
  if (value === 'success') return t('adminPages.monitoring.statusSuccess')
  if (value === 'failed') return t('adminPages.monitoring.statusFailed')
  return t('adminPages.monitoring.installStatusNotInstalled')
}

function componentStatusClass(status) {
  const value = String(status || 'unknown').toLowerCase()
  if (value === 'success') return 'border-emerald-200 bg-emerald-50 text-emerald-700'
  if (value === 'failed') return 'border-rose-200 bg-rose-50 text-rose-700'
  if (value === 'installing') return 'border-sky-200 bg-sky-50 text-sky-700'
  return 'border-slate-200 bg-slate-50 text-slate-500'
}

function componentDisplayText(host, component) {
  const installStatus = componentInstallStatus(host, component)
  if (installStatus !== 'success') return componentStatusText(installStatus)

  const runtime = String(statusFor(host, component).runtime_status || 'unknown').toLowerCase()
  if (runtime === 'online') return t('adminPages.monitoring.runtimeOnline')
  if (runtime === 'abnormal') return t('adminPages.monitoring.runtimeAbnormal')
  return t('adminPages.monitoring.statusSuccess')
}

function componentDisplayClass(host, component) {
  const installStatus = componentInstallStatus(host, component)
  if (installStatus !== 'success') return componentStatusClass(installStatus)

  const runtime = String(statusFor(host, component).runtime_status || 'unknown').toLowerCase()
  if (runtime === 'abnormal') return 'border-rose-200 bg-rose-50 text-rose-700'
  return 'border-emerald-200 bg-emerald-50 text-emerald-700'
}

function componentDisplayTitle(host, component) {
  const status = statusFor(host, component)
  return status.runtime_reason || status.runtime_endpoint || componentDisplayText(host, component)
}

function sshAuthText(host) {
  if (host.ssh_auth_type === 'password') {
    return host.has_ssh_password
      ? t('adminPages.monitoring.sshAuthPasswordConfigured')
      : t('adminPages.monitoring.sshAuthPassword')
  }
  if (host.ssh_key_name) return `${t('adminPages.monitoring.sshAuthKey')}：${host.ssh_key_name}`
  if (host.ssh_key) return `${t('adminPages.monitoring.sshAuthKey')}：${host.ssh_key}`
  return t('adminPages.monitoring.sshAuthKeyNotSelected')
}

function resetHostForm() {
  Object.assign(form, defaultHostForm())
}

function openCreateHost() {
  resetHostForm()
  showHostForm.value = true
}

function closeHostForm() {
  resetHostForm()
  showHostForm.value = false
}

function editHost(host) {
  Object.assign(form, {
    id: host.id,
    hostname: host.hostname || '',
    address: host.address || '',
    sshUser: host.ssh_user || 'root',
    sshPort: host.ssh_port || 22,
    sshAuthType: host.ssh_auth_type || (host.ssh_key_id || host.ssh_key ? 'key' : 'password'),
    sshPassword: '',
    hasSshPassword: Boolean(host.has_ssh_password),
    sshKeyId: host.ssh_key_id || '',
    sshKeyUploadName: '',
    sshKeyUploadContent: ''
  })
  showHostForm.value = true
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
  if (form.sshAuthType === 'password') {
    if (form.sshPassword || !form.id) payload.ssh_password = form.sshPassword
  } else {
    payload.ssh_key_id = form.sshKeyId ? Number(form.sshKeyId) : null
  }
  return payload
}

async function handleSshKeyFile(event) {
  const file = event.target.files?.[0]
  if (!file) return
  form.sshKeyUploadContent = await file.text()
  if (!form.sshKeyUploadName) {
    form.sshKeyUploadName = file.name.replace(/\.(pem|key|txt)$/i, '')
  }
}

async function uploadSshKey() {
  uploadingSshKey.value = true
  error.value = ''
  try {
    const key = await monitoringStackApi.createSshKey({
      name: form.sshKeyUploadName,
      private_key: form.sshKeyUploadContent
    })
    sshKeys.value = [key, ...sshKeys.value.filter((item) => item.id !== key.id)]
    form.sshKeyId = key.id
    form.sshKeyUploadName = ''
    form.sshKeyUploadContent = ''
  } catch (err) {
    error.value = err?.response?.data?.detail || err.message
  } finally {
    uploadingSshKey.value = false
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

function resetBlackboxForm() {
  blackboxPreviewText.value = ''
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

function openBulkInstallChooser() {
  if (!selectedHostIds.value.length) return
  showBulkInstallChooser.value = true
}

function closeBulkInstallChooser() {
  showBulkInstallChooser.value = false
}

function chooseBulkInstall(component) {
  closeBulkInstallChooser()
  if (component === 'blackbox') {
    openBlackboxInstall()
    return
  }
  openCategrafInstall()
}

function openCategrafInstall() {
  resetCategrafForm()
  showCategrafForm.value = true
}

function closeCategrafInstall() {
  resetCategrafForm()
  showCategrafForm.value = false
}

function canEnterCategrafStep(index) {
  if (index > 0 && !selectedHostIds.value.length) return false
  if (index > 1 && !categrafForm.profiles.length) return false
  return true
}

function goCategrafStep(index) {
  if (!canEnterCategrafStep(index)) return
  categrafStep.value = Math.max(0, Math.min(index, categrafSteps.value.length - 1))
}

function nextCategrafStep() {
  if (!canGoNextCategraf.value) return
  goCategrafStep(categrafStep.value + 1)
}

function prevCategrafStep() {
  goCategrafStep(categrafStep.value - 1)
}

function openBlackboxInstall() {
  resetBlackboxForm()
  showBlackboxForm.value = true
}

function closeBlackboxInstall() {
  resetBlackboxForm()
  showBlackboxForm.value = false
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
  blackboxForm.baseUrl = installerBaseUrl
  blackboxForm.installDir = installer.blackbox_dir || '/opt/blackbox-exporter'
  blackboxForm.image = installer.blackbox_image || 'prom/blackbox-exporter:latest'
  blackboxForm.blackboxPort = installer.blackbox_port || '9115'
  blackboxForm.probeName = installer.options?.probe_names?.[0] || 'blackbox-center'
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [configData, profileData, hostData, sshKeyData, , reconciliationData] = await Promise.all([
      monitoringStackApi.getConfig(),
      monitoringStackApi.getProfiles(),
      monitoringStackApi.getHosts(),
      monitoringStackApi.getSshKeys(),
      monitoringStackApi.getGovernanceOverview(),
      monitoringStackApi.getAssetsReconciliation()
    ])
    const findingData = await monitoringStackApi.getGovernanceFindings({ status: 'open', subject_type: 'host' })
    profiles.value = normalizeList(profileData)
    hosts.value = normalizeList(hostData)
    sshKeys.value = normalizeList(sshKeyData)
    hostFindings.value = normalizeList(findingData)
    assetReconciliation.value = reconciliationData || {}
    selectedHostIds.value = selectedHostIds.value.filter((id) => hosts.value.some((host) => host.id === id))
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
  saving.value = true
  try {
    if (form.id) await monitoringStackApi.updateHost(form.id, hostPayload())
    else await monitoringStackApi.createHost(hostPayload())
    closeHostForm()
    await load()
  } finally {
    saving.value = false
  }
}

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
    image: categrafForm.image
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
    categrafPreviewText.value = ['# inventory', data.inventory, '# vars', JSON.stringify(data.vars, null, 2)].join('\n')
    showAnsiblePreview.value = true
  } finally {
    previewingCategraf.value = false
  }
}

async function generateCategrafCommands() {
  if (showManualCommands.value && isCategrafPreviewCurrent.value && manualInstallCommands.value) {
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
  runningCategraf.value = true
  try {
    const data = await monitoringStackApi.createJob(categrafJobPayload())
    categrafPreviewText.value = JSON.stringify(data, null, 2)
    await load()
  } finally {
    runningCategraf.value = false
  }
}

function blackboxJobPayload() {
  return {
    component: 'blackbox',
    host_ids: selectedHostIds.value,
    profiles: [],
    base_url: blackboxForm.baseUrl,
    n9e_url: '',
    install_dir: blackboxForm.installDir,
    image: blackboxForm.image,
    probe_name: blackboxForm.probeName,
    blackbox_port: blackboxForm.blackboxPort
  }
}

async function previewBlackbox() {
  previewingBlackbox.value = true
  try {
    const data = await monitoringStackApi.previewAnsible(blackboxJobPayload())
    blackboxPreviewText.value = ['# inventory', data.inventory, '# vars', JSON.stringify(data.vars, null, 2)].join('\n')
  } finally {
    previewingBlackbox.value = false
  }
}

async function runBlackboxInstall() {
  runningBlackbox.value = true
  try {
    const data = await monitoringStackApi.createJob(blackboxJobPayload())
    blackboxPreviewText.value = JSON.stringify(data, null, 2)
    await load()
  } finally {
    runningBlackbox.value = false
  }
}

onMounted(load)
</script>
