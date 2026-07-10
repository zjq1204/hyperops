<template>
  <AdminLayout>
    <PageFrame variant="soft" :title="t('adminPages.monitoring.rulesTitle')">
      <AdminListSection>
        <AdminPageState :loading="loading" :error="error" :empty="false">
          <section class="grid gap-4">
            <main class="min-w-0 overflow-hidden rounded-xl border border-slate-200/70 bg-white shadow-sm shadow-slate-200/40">
              <div class="border-b border-slate-100 px-5 py-4">
                <div class="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                  <div class="min-w-0">
                    <router-link class="mb-3 inline-flex text-sm font-semibold text-blue-700 hover:text-blue-800" to="/management/monitoring/rules">
                      返回模板列表
                    </router-link>
                    <p class="text-xs font-semibold text-slate-500">模板详情</p>
                    <div class="mt-1 flex flex-wrap items-center gap-2">
                      <h2 class="min-w-0 text-lg font-semibold leading-7 text-slate-950">
                        {{ selectedRuleTitle }}
                      </h2>
                      <span
                        v-if="pendingSyncRules.has(selectedRule)"
                        class="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-700"
                      >
                        有本地变动
                      </span>
                    </div>
                    <p class="mt-1 break-all text-xs text-slate-500">
                      {{ selectedRule || t('adminPages.monitoring.selectRule') }}
                    </p>
                  </div>
                  <div class="grid grid-cols-3 gap-2 text-center sm:min-w-72">
                    <div class="rounded-lg bg-slate-50 px-3 py-2">
                      <p class="text-lg font-semibold text-slate-950">{{ selectedRuleCount }}</p>
                      <p class="text-xs text-slate-500">规则</p>
                    </div>
                    <div class="rounded-lg bg-slate-50 px-3 py-2">
                      <p class="text-lg font-semibold text-slate-950">{{ selectedRuleGroups.length }}</p>
                      <p class="text-xs text-slate-500">分组</p>
                    </div>
                    <div class="rounded-lg bg-slate-50 px-3 py-2">
                      <p class="text-lg font-semibold" :class="selectedRuleFindings.length ? 'text-amber-700' : 'text-slate-950'">
                        {{ selectedRuleFindings.length }}
                      </p>
                      <p class="text-xs text-slate-500">待处理</p>
                    </div>
                  </div>
                </div>
                <div class="mt-4 flex flex-wrap gap-2">
                  <BaseButton
                    variant="primary"
                    size="sm"
                    :disabled="!selectedRule || !selectedRuleGroups.length"
                    @click="openCreateRule"
                  >
                    新增规则
                  </BaseButton>
                  <BaseButton variant="outline" size="sm" :disabled="!selectedRule" @click="openSyncModal">
                    {{ t('adminPages.monitoring.syncRulesToN9e') }}
                  </BaseButton>
                  <BaseButton variant="ghost" size="sm" :disabled="!selectedRule" @click="openYamlEditor">
                    编辑 YAML
                  </BaseButton>
                  <BaseButton variant="ghost" size="sm" :loading="loading" @click="load">
                    {{ t('common.refresh') }}
                  </BaseButton>
                </div>
              </div>

              <div v-if="selectedRuleFindings.length" class="border-b border-amber-100 bg-amber-50/70 px-5 py-3">
                <div class="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
                  <div class="min-w-0">
                    <p class="text-sm font-semibold text-amber-900">{{ t('adminPages.monitoring.governanceFindingsTitle') }}</p>
                    <p class="mt-0.5 text-xs text-amber-700">{{ selectedRuleFindings.length }} 个规则治理项需要确认</p>
                  </div>
                  <div class="flex flex-wrap gap-2">
                    <BaseButton
                      v-for="finding in selectedRuleFindings.slice(0, 2)"
                      :key="finding.id"
                      variant="ghost"
                      size="sm"
                      :loading="resolvingFindingId === finding.id"
                      @click="finding.recommended_action === 'import_rule_template' ? openImportFromFinding(finding) : ignoreRuleFinding(finding)"
                    >
                      {{ findingStatusLabel(finding) }}
                    </BaseButton>
                  </div>
                </div>
              </div>

              <div class="border-b border-slate-100 bg-slate-50/70 px-5 py-3">
                <div class="grid gap-3 lg:grid-cols-[minmax(0,1fr)_10rem_10rem_auto] lg:items-end">
                  <label class="admin-filter-field">
                    <span class="admin-filter-label">搜索规则</span>
                    <input
                      v-model="ruleFilters.keyword"
                      class="admin-filter-control"
                      placeholder="名称、表达式、描述"
                    />
                  </label>
                  <label class="admin-filter-field">
                    <span class="admin-filter-label">分类</span>
                    <select v-model="ruleFilters.category" class="admin-filter-control">
                      <option value="all">全部</option>
                      <option v-for="item in availableRuleCategories" :key="item" :value="item">
                        {{ ruleCategoryLabel(item) }}
                      </option>
                    </select>
                  </label>
                  <label class="admin-filter-field">
                    <span class="admin-filter-label">级别</span>
                    <select v-model="ruleFilters.severity" class="admin-filter-control">
                      <option value="all">全部</option>
                      <option v-for="item in availableRuleSeverities" :key="item" :value="item">
                        {{ severityLabel(item) }}
                      </option>
                    </select>
                  </label>
                  <button
                    type="button"
                    class="min-h-10 rounded-md px-3 text-sm font-semibold text-slate-600 transition hover:bg-white hover:text-slate-950 disabled:cursor-not-allowed disabled:opacity-40"
                    :disabled="!hasActiveRuleFilter"
                    @click="resetRuleFilters"
                  >
                    清空
                  </button>
                </div>
                <div class="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
                  <span>当前显示 {{ filteredRuleCount }} / {{ selectedRuleCount }} 条</span>
                  <span v-if="pendingSyncRules.has(selectedRule)" class="font-medium text-amber-700">
                    本地模板已保存，执行同步后 n9e 才会生效
                  </span>
                </div>
              </div>

              <div class="max-h-[calc(100dvh-18rem)] overflow-auto px-5 py-4">
                <p v-if="!selectedRuleGroups.length" class="rounded-lg bg-slate-50 px-4 py-10 text-center text-sm text-slate-400">
                  {{ t('adminPages.monitoring.selectRule') }}
                </p>
                <p v-else-if="!filteredRuleCount" class="rounded-lg bg-slate-50 px-4 py-10 text-center text-sm text-slate-400">
                  没有匹配的规则
                </p>

                <div v-else class="grid gap-4">
                  <section
                    v-for="group in filteredRuleGroups"
                    :key="group.index"
                    class="overflow-hidden rounded-lg border border-slate-200/70 bg-white"
                  >
                    <div class="flex items-center justify-between gap-3 border-b border-slate-100 bg-slate-50/80 px-4 py-2.5">
                      <p class="text-sm font-semibold text-slate-800">
                        {{ group.name || `规则组 ${group.index + 1}` }}
                      </p>
                      <span class="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-500">
                        {{ group.rules.length }} 条
                      </span>
                    </div>

                    <div class="divide-y divide-slate-100">
                      <article
                        v-for="rule in group.rules"
                        :key="`${rule.group_index}:${rule.rule_index}`"
                        class="px-4 py-3 transition hover:bg-blue-50/30"
                      >
                        <div class="grid gap-3 xl:grid-cols-[minmax(0,1fr)_12rem] xl:items-start">
                          <div class="min-w-0">
                            <div class="flex flex-wrap items-center gap-2">
                              <p class="min-w-0 break-words text-sm font-semibold text-slate-950">
                                {{ rule.alert || '未命名规则' }}
                              </p>
                              <span class="rounded-full border px-2 py-0.5 text-xs font-semibold" :class="ruleSeverityClass(rule.severity)">
                                {{ severityLabel(rule.severity) }}
                              </span>
                              <span class="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-600">
                                {{ ruleCategoryLabel(rule.category) }}
                              </span>
                              <span class="rounded-full bg-slate-100 px-2 py-0.5 font-mono text-xs font-semibold text-slate-600">
                                {{ rule.for || '-' }}
                              </span>
                            </div>
                            <p v-if="ruleSubtitle(rule)" class="mt-1 text-xs leading-5 text-slate-500">
                              {{ ruleSubtitle(rule) }}
                            </p>
                            <p class="mt-2 break-all rounded-md bg-slate-50 px-3 py-2 font-mono text-xs leading-5 text-slate-700">
                              {{ rule.expr || '-' }}
                            </p>
                          </div>
                          <div class="flex flex-wrap gap-2 xl:justify-end">
                            <BaseButton variant="outline" size="sm" @click="openEditRule(rule)">
                              {{ t('common.edit') }}
                            </BaseButton>
                            <BaseButton variant="ghost" size="sm" @click="openCopyRule(rule)">
                              复制
                            </BaseButton>
                            <BaseButton variant="danger" size="sm" @click="confirmDeleteRule(rule)">
                              {{ t('common.delete') }}
                            </BaseButton>
                          </div>
                        </div>
                      </article>
                    </div>
                  </section>
                </div>

                <div v-if="importResult" class="mt-5 rounded-lg border border-slate-200 bg-white p-4">
                  <p class="text-sm font-semibold text-slate-900">
                    {{ t('adminPages.monitoring.importResult') }}
                  </p>
                  <div class="mt-3 grid gap-3 sm:grid-cols-3">
                    <div v-for="item in importSummaryCards" :key="item.label" class="rounded-md bg-slate-50 px-3 py-3">
                      <p class="text-xs font-medium text-slate-500">{{ item.label }}</p>
                      <p class="mt-1 font-semibold text-slate-950" :class="item.valueClass || 'text-2xl'">{{ item.value }}</p>
                    </div>
                  </div>
                  <details class="mt-3 rounded-lg bg-slate-950">
                    <summary class="cursor-pointer px-4 py-3 text-xs font-semibold text-slate-200">
                      {{ t('adminPages.monitoring.rawResult') }}
                    </summary>
                    <pre class="max-h-72 overflow-auto whitespace-pre-wrap border-t border-slate-800 p-4 text-xs leading-6 text-slate-100">{{ importResult }}</pre>
                  </details>
                </div>
              </div>
            </main>
          </section>
        </AdminPageState>
      </AdminListSection>
    </PageFrame>

    <BaseModal
      :show="showImportModal"
      :title="t('adminPages.monitoring.syncRulesToN9e')"
      size="lg"
      @close="showImportModal = false"
    >
      <div class="grid gap-4">
        <div class="grid gap-3 rounded-xl border border-slate-200/80 bg-slate-50/70 p-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <div class="min-w-0">
            <p class="text-xs font-semibold text-slate-500">同步模板</p>
            <p class="mt-1 break-all text-sm font-semibold text-slate-950">{{ selectedRule || t('common.emptyValue') }}</p>
          </div>
          <div class="min-w-0 md:text-right">
            <p class="text-xs font-semibold text-slate-500">目标 n9e</p>
            <p class="mt-1 break-all text-sm font-semibold text-slate-950">{{ form.n9eUrl || '未配置' }}</p>
          </div>
        </div>

        <section class="rounded-xl border border-slate-200 bg-white p-4">
          <div class="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p class="text-sm font-semibold text-slate-900">变动预览</p>
              <p class="mt-1 text-xs text-slate-500">按当前业务组和数据源读取 n9e 规则后，对比本地模板。</p>
            </div>
            <div class="flex flex-wrap items-center gap-2">
              <span class="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-600">
                {{ baselineSourceLabel }}
              </span>
              <span class="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-600">
                {{ ruleDiffLoading ? '读取中' : `${syncChangePreview.length} 项` }}
              </span>
              <BaseButton variant="outline" size="sm" :loading="ruleDiffLoading" @click="loadRuleDiff">
                刷新对比
              </BaseButton>
            </div>
          </div>

          <div v-if="ruleDiffSummaryCards.length" class="mt-3 grid gap-2 sm:grid-cols-5">
            <div v-for="item in ruleDiffSummaryCards" :key="item.label" class="rounded-lg bg-slate-50 px-3 py-2 text-center">
              <p class="text-xs text-slate-500">{{ item.label }}</p>
              <p class="mt-1 text-lg font-semibold text-slate-900">{{ item.value }}</p>
            </div>
          </div>

          <p v-if="ruleDiff?.baseline_message" class="mt-3 rounded-lg bg-slate-50 px-3 py-2 text-xs leading-5 text-slate-500">
            {{ ruleDiff.baseline_message }}
          </p>
          <p v-if="ruleDiff && !ruleDiff.has_baseline" class="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-700">
            暂无 n9e 规则快照，无法做真实差异对比。本次只能按模板全量同步。
          </p>

          <div class="mt-3 max-h-72 overflow-auto rounded-lg border border-slate-100">
            <div class="divide-y divide-slate-100">
              <div
                v-for="item in syncChangePreview"
                :key="`${item.type}:${item.group}:${item.name}:${item.expr}`"
                class="px-3 py-2.5"
              >
                <div class="flex items-start justify-between gap-3">
                  <div class="min-w-0">
                    <p class="break-words text-sm font-medium text-slate-900">{{ item.name }}</p>
                    <p class="mt-0.5 text-xs leading-5 text-slate-500">
                      {{ item.group || '默认规则组' }}
                      <span v-if="item.severity"> · {{ severityLabel(item.severity) }}</span>
                      <span v-if="item.category"> · {{ ruleCategoryLabel(item.category) }}</span>
                    </p>
                    <p v-if="item.reason" class="mt-1 text-xs leading-5 text-slate-500">
                      {{ item.reason }}
                    </p>
                  </div>
                  <span
                    class="shrink-0 rounded-full px-2 py-0.5 text-xs font-semibold"
                    :class="changeTypeClass(item.type)"
                  >
                    {{ changeTypeLabel(item.type) }}
                  </span>
                </div>
                <div v-if="item.changeLabels?.length" class="mt-2 flex flex-wrap gap-1.5">
                  <span
                    v-for="label in item.changeLabels"
                    :key="label"
                    class="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600"
                  >
                    {{ label }}
                  </span>
                </div>
                <p v-if="item.expr" class="mt-2 break-all rounded-md bg-slate-50 px-2 py-1 font-mono text-xs leading-5 text-slate-600">
                  {{ item.expr }}
                </p>
              </div>
            </div>
          </div>
        </section>

        <section class="rounded-xl border border-slate-200 bg-white p-4">
          <div class="mb-3 flex flex-wrap items-center justify-between gap-3">
            <div>
              <p class="text-sm font-semibold text-slate-900">同步目标</p>
              <p class="mt-1 text-xs text-slate-500">选择 n9e 业务组和 Prometheus 数据源。</p>
            </div>
            <BaseButton variant="outline" size="sm" :loading="discovering" @click="discover">
              {{ t('adminPages.monitoring.refreshN9eOptions') }}
            </BaseButton>
          </div>
          <div class="grid gap-3 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_12rem]">
            <label class="admin-filter-field">
              <span class="admin-filter-label">{{ t('adminPages.monitoring.groupId') }}</span>
              <select v-model="form.groupId" class="admin-filter-control" @change="loadRuleDiff">
                <option value="">{{ t('adminPages.monitoring.selectGroup') }}</option>
                <option v-for="group in groups" :key="group.id" :value="group.id">
                  {{ group.id }}:{{ group.name }}
                </option>
              </select>
            </label>
            <label class="admin-filter-field">
              <span class="admin-filter-label">{{ t('adminPages.monitoring.datasourceId') }}</span>
              <select v-model="form.datasourceId" class="admin-filter-control" @change="loadRuleDiff">
                <option value="">{{ t('adminPages.monitoring.selectDatasource') }}</option>
                <option v-for="source in datasources" :key="source.id" :value="source.id">
                  {{ source.id }}:{{ source.name }}
                </option>
              </select>
            </label>
            <label class="flex min-h-10 items-center gap-2 self-end rounded-md bg-slate-50 px-3 text-sm text-slate-700">
              <input v-model="form.enabled" type="checkbox" />
              {{ t('adminPages.monitoring.enableImportedRules') }}
            </label>
          </div>
        </section>

        <div
          v-if="importResult"
          class="rounded-xl border border-slate-200 bg-slate-50/70 p-4"
        >
          <p class="text-sm font-semibold text-slate-900">
            {{ t('adminPages.monitoring.importResult') }}
          </p>
          <div class="mt-3 grid gap-3 sm:grid-cols-3">
            <div v-for="item in importSummaryCards" :key="item.label" class="rounded-lg bg-white px-3 py-3">
              <p class="text-xs font-medium text-slate-500">{{ item.label }}</p>
              <p class="mt-1 font-semibold text-slate-950" :class="item.valueClass || 'text-2xl'">{{ item.value }}</p>
            </div>
          </div>
        </div>
        <div class="flex justify-end gap-2 pt-2">
          <BaseButton variant="outline" @click="showImportModal = false">
            {{ t('common.cancel') }}
          </BaseButton>
          <BaseButton variant="primary" :loading="importing" @click="importRules">
            {{ t('adminPages.monitoring.syncRulesToN9e') }}
          </BaseButton>
        </div>
      </div>
    </BaseModal>

    <BaseModal
      :show="showRuleEditModal"
      :title="ruleModalTitle"
      size="lg"
      @close="closeEditRule"
    >
      <form class="grid gap-4" @submit.prevent="saveRule">
        <div class="grid gap-3 md:grid-cols-2">
          <label class="admin-filter-field">
            <span class="admin-filter-label">规则组</span>
            <select
              v-model.number="ruleForm.groupIndex"
              class="admin-filter-control"
              :disabled="ruleForm.mode === 'edit'"
            >
              <option
                v-for="group in selectedRuleGroups"
                :key="group.index"
                :value="group.index"
              >
                {{ group.name || `规则组 ${group.index + 1}` }}
              </option>
            </select>
          </label>
          <label class="admin-filter-field">
            <span class="admin-filter-label">规则名称</span>
            <input v-model="ruleForm.alert" class="admin-filter-control" />
          </label>
          <label class="admin-filter-field">
            <span class="admin-filter-label">持续时间</span>
            <input v-model="ruleForm.ruleFor" class="admin-filter-control" placeholder="5m" />
          </label>
          <label class="admin-filter-field">
            <span class="admin-filter-label">告警级别</span>
            <select v-model="ruleForm.severity" class="admin-filter-control">
              <option value="warning">警告</option>
              <option value="critical">严重</option>
              <option value="info">提示</option>
            </select>
          </label>
          <label class="admin-filter-field">
            <span class="admin-filter-label">分类</span>
            <select v-model="ruleForm.category" class="admin-filter-control">
              <option value="host">主机</option>
              <option value="docker">Docker</option>
              <option value="mysql">MySQL</option>
              <option value="redis">Redis</option>
              <option value="nginx">Nginx</option>
              <option value="blackbox">探测</option>
              <option value="platform">平台</option>
            </select>
          </label>
        </div>
        <label class="admin-filter-field">
          <span class="admin-filter-label">PromQL 表达式</span>
          <textarea v-model="ruleForm.expr" class="admin-filter-control min-h-28 font-mono" />
        </label>
        <label class="admin-filter-field">
          <span class="admin-filter-label">摘要</span>
          <input v-model="ruleForm.summary" class="admin-filter-control" />
        </label>
        <label class="admin-filter-field">
          <span class="admin-filter-label">描述</span>
          <textarea v-model="ruleForm.description" class="admin-filter-control min-h-24" />
        </label>
        <div class="flex justify-end gap-2 pt-2">
          <BaseButton variant="outline" type="button" @click="closeEditRule">
            {{ t('common.cancel') }}
          </BaseButton>
          <BaseButton variant="primary" type="submit" :loading="savingRule">
            {{ t('common.save') }}
          </BaseButton>
        </div>
      </form>
    </BaseModal>

    <BaseModal
      :show="showYamlModal"
      title="编辑 YAML"
      size="wide"
      :close-on-backdrop="false"
      @close="closeYamlEditor"
    >
      <div class="grid gap-4">
        <div class="grid gap-3 rounded-xl border border-slate-200/80 bg-slate-50/70 p-4 md:grid-cols-[minmax(0,1fr)_12rem_12rem]">
          <div class="min-w-0">
            <p class="text-xs font-semibold text-slate-500">当前模板</p>
            <p class="mt-1 break-all text-sm font-semibold text-slate-950">{{ selectedRule || t('common.emptyValue') }}</p>
          </div>
          <div>
            <p class="text-xs font-semibold text-slate-500">规则</p>
            <p class="mt-1 text-sm font-semibold text-slate-950">{{ selectedRuleCount }} 条</p>
          </div>
          <div>
            <p class="text-xs font-semibold text-slate-500">分组</p>
            <p class="mt-1 text-sm font-semibold text-slate-950">{{ selectedRuleGroups.length }} 个</p>
          </div>
        </div>

        <p
          v-if="yamlError"
          class="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm leading-5 text-rose-700"
        >
          {{ yamlError }}
        </p>

        <label class="admin-filter-field">
          <span class="admin-filter-label">YAML 内容</span>
          <textarea
            v-model="yamlContent"
            class="admin-filter-control min-h-[58vh] resize-y font-mono text-xs leading-5"
            spellcheck="false"
          />
        </label>
      </div>

      <template #footer>
        <div class="flex w-full flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <p class="text-xs leading-5 text-slate-500">
            保存后会更新 HyperOps 本地模板，需再同步到 n9e 才会影响 n9e 规则。
          </p>
          <div class="flex flex-wrap justify-end gap-2">
            <BaseButton variant="ghost" type="button" @click="copyYamlContent">
              复制内容
            </BaseButton>
            <BaseButton variant="outline" type="button" @click="closeYamlEditor">
              {{ t('common.cancel') }}
            </BaseButton>
            <BaseButton
              variant="primary"
              type="button"
              :loading="savingYaml"
              :disabled="!yamlHasChanges"
              @click="saveYamlContent"
            >
              保存 YAML
            </BaseButton>
          </div>
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
  </AdminLayout>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
import AdminLayout from '@/admin/layout/AdminLayout.vue'
import AdminListSection from '@/admin/components/AdminListSection.vue'
import AdminPageState from '@/admin/components/AdminPageState.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseModal from '@/components/ui/BaseModal.vue'
import PageFrame from '@/components/ui/PageFrame.vue'
import { monitoringStackApi } from '@/admin/api/monitoringStack'
import { useConfirmDialog } from '@/composables/useConfirmDialog'
import { useToast } from '@/composables/useToast'

const { t } = useI18n()
const route = useRoute()
const {
  confirmDialog,
  requestConfirm,
  closeConfirmDialog,
  runConfirmedAction
} = useConfirmDialog()
const { showSuccess, showError } = useToast()
const loading = ref(false)
const discovering = ref(false)
const importing = ref(false)
const savingRule = ref(false)
const savingYaml = ref(false)
const error = ref('')
const rules = ref([])
const ruleFindings = ref([])
const ruleDiff = ref(null)
const ruleDiffLoading = ref(false)
const groups = ref([])
const datasources = ref([])
const selectedRule = ref('')
const selectedContent = ref('')
const selectedRuleGroups = ref([])
const selectedRuleCount = ref(0)
const importResult = ref('')
const importSummary = ref(null)
const showImportModal = ref(false)
const showRuleEditModal = ref(false)
const showYamlModal = ref(false)
const yamlContent = ref('')
const yamlError = ref('')
const n9eConfig = ref({})
const resolvingFindingId = ref(null)
const pendingSyncRules = ref(new Set())
const ruleChangeLog = ref({})
const form = reactive({
  n9eUrl: '',
  groupId: '',
  datasourceId: '',
  enabled: false
})
const ruleForm = reactive({
  mode: 'edit',
  groupIndex: 0,
  ruleIndex: 0,
  alert: '',
  expr: '',
  ruleFor: '',
  severity: 'warning',
  category: 'host',
  summary: '',
  description: ''
})
const ruleFilters = reactive({
  keyword: '',
  category: 'all',
  severity: 'all'
})

const importSummaryCards = computed(() => {
  const summary = importSummary.value || {}
  if (summary.count_available === false) {
    return [
      {
        label: '提交状态',
        value: Number(summary.submitted || 0) > 0 ? '已提交' : '已发送'
      },
      {
        label: 'n9e 返回',
        value: '未提供明细'
      },
      {
        label: '处理说明',
        value: summary.message || '请刷新 n9e 规则列表确认结果',
        valueClass: 'text-sm leading-5'
      }
    ]
  }
  return [
    {
      label: t('adminPages.monitoring.importSuccessCount'),
      value: Number(summary.success || 0)
    },
    {
      label: t('adminPages.monitoring.importSkippedCount'),
      value: Number(summary.skipped || 0)
    },
    {
      label: t('adminPages.monitoring.importFailedCount'),
      value: Number(summary.failed || 0)
    }
  ]
})

const flatSelectedRules = computed(() =>
  selectedRuleGroups.value.flatMap((group) => group.rules || [])
)

const selectedRuleFindings = computed(() =>
  ruleFindings.value.filter((finding) => finding.subject_key === selectedRule.value)
)

const availableRuleCategories = computed(() =>
  [...new Set(flatSelectedRules.value.map((rule) => rule.category).filter(Boolean))].sort()
)

const availableRuleSeverities = computed(() =>
  [...new Set(flatSelectedRules.value.map((rule) => rule.severity).filter(Boolean))].sort()
)

const filteredRuleGroups = computed(() => {
  const keyword = ruleFilters.keyword.trim().toLowerCase()
  return selectedRuleGroups.value
    .map((group) => {
      const rules = (group.rules || []).filter((rule) => {
        if (ruleFilters.category !== 'all' && rule.category !== ruleFilters.category) {
          return false
        }
        if (ruleFilters.severity !== 'all' && rule.severity !== ruleFilters.severity) {
          return false
        }
        if (!keyword) return true
        return [rule.alert, rule.expr, rule.summary, rule.description]
          .filter(Boolean)
          .some((value) => String(value).toLowerCase().includes(keyword))
      })
      return { ...group, rules }
    })
    .filter((group) => group.rules.length)
})

const filteredRuleCount = computed(() =>
  filteredRuleGroups.value.reduce((total, group) => total + group.rules.length, 0)
)

const hasActiveRuleFilter = computed(() =>
  Boolean(ruleFilters.keyword.trim()) ||
  ruleFilters.category !== 'all' ||
  ruleFilters.severity !== 'all'
)

const yamlHasChanges = computed(() =>
  yamlContent.value !== selectedContent.value
)

const ruleModalTitle = computed(() => {
  if (ruleForm.mode === 'create') return '新增规则'
  if (ruleForm.mode === 'copy') return '复制规则'
  return '编辑规则'
})

const selectedRuleTitle = computed(() => {
  const current = rules.value.find((rule) => rule.name === selectedRule.value)
  return current?.title || selectedRule.value || t('adminPages.monitoring.selectRule')
})

const routeTemplateName = computed(() => String(route.params.templateName || ''))

const syncChangePreview = computed(() => {
  const diffItems = ruleDiff.value?.items || []
  if (ruleDiff.value?.has_baseline) {
    const actionable = diffItems
      .filter((item) => item.status !== 'unchanged')
      .map((item) => ({
        type: item.status,
        name: item.name,
        group: diffStatusDescription(item),
        severity: item.local?.severity || item.n9e?.severity || '',
        category: item.local?.category || item.n9e?.category || '',
        expr: item.local?.expr || item.n9e?.expr || '',
        reason: item.reason || '',
        changeLabels: Object.keys(item.changes || {}).map(diffFieldLabel)
      }))
    if (actionable.length) return actionable
    return [
      {
        type: 'unchanged',
        name: '本地模板与 n9e 快照一致',
        group: `${ruleDiff.value.summary?.unchanged || 0} 条规则无变化`,
        expr: ''
      }
    ]
  }
  const items = ruleChangeLog.value[selectedRule.value] || []
  if (items.length) return items
  if (pendingSyncRules.value.has(selectedRule.value)) {
    return [
      {
        type: 'change',
        name: '本地模板有未同步变动',
        group: `${selectedRuleCount.value} 条规则将随模板一起同步`,
        expr: ''
      }
    ]
  }
  return [
    {
      type: 'sync',
      name: '全量同步当前模板',
      group: `${selectedRuleCount.value} 条规则将同步到 n9e`,
      expr: ''
    }
  ]
})

const ruleDiffSummaryCards = computed(() => {
  const summary = ruleDiff.value?.summary
  if (!summary) return []
  return [
    { label: '新增', value: Number(summary.created || 0) },
    { label: '修改', value: Number(summary.updated || 0) },
    { label: 'n9e 独有', value: Number(summary.n9e_only || 0) },
    { label: '无法确认', value: Number(summary.unknown || 0) },
    { label: '无变化', value: Number(summary.unchanged || 0) }
  ]
})

const baselineSourceLabel = computed(() => {
  if (ruleDiffLoading.value) return '正在读取'
  if (ruleDiff.value?.baseline_source === 'live') return '实时 n9e'
  if (ruleDiff.value?.baseline_source === 'snapshot') return '最近快照'
  return '未对比'
})

const severityLabels = {
  critical: '严重',
  warning: '警告',
  info: '提示'
}

const categoryLabels = {
  host: '主机',
  docker: 'Docker',
  mysql: 'MySQL',
  redis: 'Redis',
  nginx: 'Nginx',
  blackbox: '探测',
  probe: '探测',
  platform: '平台',
  categraf: 'Categraf'
}

function normalizeList(data) {
  return data?.results || data || []
}

function ruleFindingsFor(rule) {
  return ruleFindings.value.filter((finding) => finding.subject_key === rule.name)
}

function ruleTemplateMeta(rule) {
  if (rule.category) return ruleCategoryLabel(rule.category)
  return '本地模板'
}

function severityLabel(severity) {
  const value = String(severity || '').toLowerCase()
  return severityLabels[value] || severity || '未设置级别'
}

function ruleCategoryLabel(category) {
  const value = String(category || '').toLowerCase()
  return categoryLabels[value] || category || '未分类'
}

function compactRuleText(value) {
  return String(value || '')
    .replace(/\s+/g, '')
    .replace(/[，。,.、:：；;（）()【】[\]_-]/g, '')
    .toLowerCase()
}

function ruleSubtitle(rule) {
  const title = compactRuleText(rule.alert)
  const candidates = [rule.summary, rule.description].filter(Boolean)
  const subtitle = candidates.find((item) => {
    const value = compactRuleText(item)
    return value && value !== title
  })
  return subtitle || ''
}

function findingRuleName(finding) {
  return finding.details?.name || finding.details?.rule_file || finding.title || finding.subject_key
}

function findingStatusLabel(finding) {
  if (finding.category === 'n9e_rule_untracked') return '仅存在于 n9e'
  if (finding.category === 'rule_template_not_imported') return '待同步到 n9e'
  return finding.category || t('common.emptyValue')
}

function findingDescription(finding) {
  if (finding.category === 'n9e_rule_untracked') {
    return '这条告警规则已经在 n9e 中存在，但 HyperOps 没有对应的本地模板或导入记录。确认它由 n9e 独立维护时可以忽略。'
  }
  if (finding.category === 'rule_template_not_imported') {
    return 'HyperOps 有这份规则模板，但还没有成功同步到 n9e。需要执行同步到 n9e。'
  }
  return finding.title || t('common.emptyValue')
}

function findingBadgeClass(finding) {
  if (finding.category === 'n9e_rule_untracked') {
    return 'border-sky-200 bg-sky-50 text-sky-700'
  }
  if (finding.category === 'rule_template_not_imported') {
    return 'border-amber-200 bg-amber-50 text-amber-700'
  }
  return 'border-slate-200 bg-slate-50 text-slate-600'
}

function ruleSeverityClass(severity) {
  const value = String(severity || '').toLowerCase()
  if (value === 'critical') return 'border-rose-200 bg-rose-50 text-rose-700'
  if (value === 'warning') return 'border-amber-200 bg-amber-50 text-amber-700'
  if (value === 'info') return 'border-sky-200 bg-sky-50 text-sky-700'
  return 'border-slate-200 bg-slate-50 text-slate-600'
}

function changeTypeLabel(type) {
  return {
    create: '新增',
    created: '新增',
    copy: '复制',
    edit: '编辑',
    updated: '修改',
    delete: '删除',
    deleted: 'n9e 独有',
    n9e_only: 'n9e 独有',
    unknown: '无法确认',
    change: '本地变动',
    sync: '全量同步',
    unchanged: '无变化'
  }[type] || '变动'
}

function changeTypeClass(type) {
  return {
    create: 'bg-emerald-100 text-emerald-700',
    created: 'bg-emerald-100 text-emerald-700',
    copy: 'bg-sky-100 text-sky-700',
    edit: 'bg-amber-100 text-amber-700',
    updated: 'bg-amber-100 text-amber-700',
    delete: 'bg-rose-100 text-rose-700',
    deleted: 'bg-rose-100 text-rose-700',
    n9e_only: 'bg-slate-200 text-slate-700',
    unknown: 'bg-orange-100 text-orange-700',
    change: 'bg-amber-100 text-amber-700',
    sync: 'bg-slate-200 text-slate-700',
    unchanged: 'bg-emerald-100 text-emerald-700'
  }[type] || 'bg-slate-100 text-slate-700'
}

function diffStatusDescription(item) {
  if (item.status === 'created') return '本地模板中存在，n9e 中不存在'
  if (item.status === 'n9e_only' || item.status === 'deleted') return 'n9e 中存在，本次模板同步不会删除'
  if (item.status === 'unknown') return item.reason || '字段不足，无法确认差异'
  if (item.status === 'updated') {
    return Object.keys(item.changes || {}).map(diffFieldLabel).join('、') || '字段有变化'
  }
  return '无变化'
}

function diffFieldLabel(field) {
  return {
    expr: '表达式',
    for: '持续时间',
    severity: '级别',
    category: '分类',
    summary: '摘要',
    description: '描述'
  }[field] || field
}

function recordRuleChange(type, name) {
  if (!selectedRule.value) return
  const current = ruleChangeLog.value[selectedRule.value] || []
  ruleChangeLog.value = {
    ...ruleChangeLog.value,
    [selectedRule.value]: [
      ...current,
      {
        type,
        name: name || '未命名规则',
        group: selectedRuleGroups.value.find((group) => group.index === ruleForm.groupIndex)?.name || `规则组 ${ruleForm.groupIndex + 1}`,
        severity: ruleForm.severity,
        category: ruleForm.category,
        expr: ruleForm.expr
      }
    ].slice(-8)
  }
}

function setRuleForm(rule, mode = 'edit') {
  Object.assign(ruleForm, {
    mode,
    groupIndex: rule.group_index ?? selectedRuleGroups.value[0]?.index ?? 0,
    ruleIndex: rule.rule_index ?? 0,
    alert: rule.alert || '',
    expr: rule.expr || '',
    ruleFor: rule.for || '',
    severity: rule.severity || 'warning',
    category: rule.category || 'host',
    summary: rule.summary || '',
    description: rule.description || ''
  })
}

function openCreateRule() {
  setRuleForm(
    {
      group_index: selectedRuleGroups.value[0]?.index ?? 0,
      alert: '',
      expr: '',
      for: '5m',
      severity: 'warning',
      category: 'host',
      summary: '',
      description: ''
    },
    'create'
  )
  showRuleEditModal.value = true
}

function openCopyRule(rule) {
  setRuleForm(
    {
      ...rule,
      alert: `${rule.alert || '未命名规则'} 副本`
    },
    'copy'
  )
  showRuleEditModal.value = true
}

function openEditRule(rule) {
  setRuleForm(rule, 'edit')
  showRuleEditModal.value = true
}

function closeEditRule() {
  showRuleEditModal.value = false
}

function openYamlEditor() {
  yamlContent.value = selectedContent.value || ''
  yamlError.value = ''
  showYamlModal.value = true
}

function closeYamlEditor() {
  showYamlModal.value = false
  yamlError.value = ''
}

function confirmDeleteRule(rule) {
  requestConfirm({
    title: '删除告警规则',
    message: `确定删除“${rule.alert || '未命名规则'}”吗？这只会删除 HyperOps 本地模板中的规则，不会直接删除 n9e 中已存在的规则；需要同步到 n9e 后才会影响 n9e。`,
    confirmText: t('common.delete'),
    variant: 'danger',
    onConfirm: () => deleteRule(rule)
  })
}

function resetRuleFilters() {
  ruleFilters.keyword = ''
  ruleFilters.category = 'all'
  ruleFilters.severity = 'all'
}

function applyRuleDetail(data, { resetFilters = true } = {}) {
  selectedContent.value = data.content || ''
  selectedRuleGroups.value = data.groups || []
  selectedRuleCount.value = Number(data.rule_count || 0)
  if (resetFilters) resetRuleFilters()
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    await monitoringStackApi.getGovernanceOverview()
    const [configData, rulesData, findingData] = await Promise.all([
      monitoringStackApi.getConfig(),
      monitoringStackApi.getRules(),
      monitoringStackApi.getGovernanceFindings({ status: 'open', subject_type: 'rule' })
    ])
    n9eConfig.value = configData?.n9e || {}
    form.n9eUrl = form.n9eUrl || configData?.n9e_url || configData?.installer?.n9e_url || ''
    rules.value = rulesData?.results || []
    ruleFindings.value = normalizeList(findingData)
    if (!routeTemplateName.value) {
      error.value = '缺少规则模板名称'
      return
    }
    selectedRule.value = routeTemplateName.value
    await selectRule(routeTemplateName.value)
  } catch (err) {
    error.value = err?.response?.data?.detail || err.message
  } finally {
    loading.value = false
  }
}

async function openImportFromFinding(finding) {
  const ruleFile = finding.details?.rule_file || finding.subject_key
  if (ruleFile) await selectRule(ruleFile)
  await openSyncModal()
}

async function ignoreRuleFinding(finding) {
  resolvingFindingId.value = finding.id
  try {
    await monitoringStackApi.resolveGovernanceFinding(finding.id, {
      action: 'ignore'
    })
    await load()
  } finally {
    resolvingFindingId.value = null
  }
}

async function selectRule(name) {
  selectedRule.value = name
  const data = await monitoringStackApi.getRule(name)
  applyRuleDetail(data, { resetFilters: true })
}

async function saveRule() {
  savingRule.value = true
  error.value = ''
  try {
    const payload = {
      group_index: ruleForm.groupIndex,
      rule: {
        alert: ruleForm.alert,
        expr: ruleForm.expr,
        for: ruleForm.ruleFor,
        severity: ruleForm.severity,
        category: ruleForm.category,
        summary: ruleForm.summary,
        description: ruleForm.description
      }
    }
    const data = ruleForm.mode === 'edit'
      ? await monitoringStackApi.updateRule(selectedRule.value, {
          ...payload,
          rule_index: ruleForm.ruleIndex
        })
      : await monitoringStackApi.createRule(selectedRule.value, payload)
    applyRuleDetail(data, { resetFilters: false })
    pendingSyncRules.value = new Set([...pendingSyncRules.value, selectedRule.value])
    recordRuleChange(ruleForm.mode, ruleForm.alert)
    closeEditRule()
  } catch (err) {
    error.value = err?.response?.data?.detail || err.message
  } finally {
    savingRule.value = false
  }
}

async function saveYamlContent() {
  if (!selectedRule.value || !yamlHasChanges.value) return
  savingYaml.value = true
  yamlError.value = ''
  error.value = ''
  try {
    const data = await monitoringStackApi.updateRule(selectedRule.value, {
      content: yamlContent.value
    })
    applyRuleDetail(data, { resetFilters: false })
    pendingSyncRules.value = new Set([...pendingSyncRules.value, selectedRule.value])
    recordYamlChange()
    showYamlModal.value = false
    showSuccess('YAML 已保存')
  } catch (err) {
    yamlError.value = err?.response?.data?.detail || err.message
  } finally {
    savingYaml.value = false
  }
}

async function copyYamlContent() {
  try {
    await navigator.clipboard.writeText(yamlContent.value || '')
    showSuccess('YAML 已复制')
  } catch (err) {
    showError(`复制失败：${err.message}`)
  }
}

function recordYamlChange() {
  if (!selectedRule.value) return
  const current = ruleChangeLog.value[selectedRule.value] || []
  ruleChangeLog.value = {
    ...ruleChangeLog.value,
    [selectedRule.value]: [
      ...current,
      {
        type: 'edit',
        name: 'YAML 内容已修改',
        group: '整份模板',
        expr: ''
      }
    ].slice(-8)
  }
}

async function deleteRule(rule) {
  error.value = ''
  try {
    const data = await monitoringStackApi.deleteRule(selectedRule.value, {
      group_index: rule.group_index,
      rule_index: rule.rule_index
    })
    applyRuleDetail(data, { resetFilters: false })
    pendingSyncRules.value = new Set([...pendingSyncRules.value, selectedRule.value])
    recordRuleChange('delete', rule.alert)
  } catch (err) {
    error.value = err?.response?.data?.detail || err.message
    throw err
  }
}

async function discover() {
  discovering.value = true
  importResult.value = ''
  importSummary.value = null
  try {
    const data = await monitoringStackApi.discoverN9e({})
    groups.value = data.groups || []
    datasources.value = data.datasources || []
    form.groupId = groups.value[0]?.id || ''
    form.datasourceId = datasources.value[0]?.id || ''
  } finally {
    discovering.value = false
  }
}

async function openSyncModal() {
  showImportModal.value = true
  if (!groups.value.length && !datasources.value.length) {
    await discover()
  }
  await loadRuleDiff()
}

async function loadRuleDiff() {
  if (!selectedRule.value) return
  ruleDiffLoading.value = true
  try {
    ruleDiff.value = await monitoringStackApi.getRuleDiff(selectedRule.value, {
      group_id: form.groupId,
      datasource_id: form.datasourceId
    })
  } finally {
    ruleDiffLoading.value = false
  }
}

async function importRules() {
  if (!selectedRule.value) return
  importing.value = true
  try {
    const data = await monitoringStackApi.importN9eRules({
      group_id: Number(form.groupId),
      datasource_id: Number(form.datasourceId),
      rule_file: selectedRule.value,
      enabled: form.enabled
    })
    importSummary.value = data?.summary || null
    importResult.value = JSON.stringify(data?.result || data, null, 2)
    if (Number(data?.summary?.failed || 0) === 0) {
      const next = new Set(pendingSyncRules.value)
      next.delete(selectedRule.value)
      pendingSyncRules.value = next
      const nextLog = { ...ruleChangeLog.value }
      delete nextLog[selectedRule.value]
      ruleChangeLog.value = nextLog
    }
  } finally {
    importing.value = false
  }
}

watch(routeTemplateName, (next, previous) => {
  if (next && next !== previous) load()
})

onMounted(load)
</script>
