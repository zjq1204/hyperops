<template>
  <AdminLayout>
    <PageFrame variant="soft" :title="t('adminPages.monitoring.rulesTitle')">
      <AdminListSection>
        <AdminPageState :loading="loading" :error="error" :empty="false">
          <section class="grid gap-4">
            <section class="overflow-hidden rounded-xl border border-slate-200/70 bg-white shadow-sm shadow-slate-200/40">
              <div class="border-b border-slate-100 bg-white px-5 py-4">
                <div class="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,28rem)] lg:items-center">
                  <div>
                    <div class="flex flex-wrap items-center gap-2">
                      <p class="text-base font-semibold text-slate-950">模板库</p>
                      <BaseButton variant="ghost" size="sm" :loading="loading" @click="load">
                        {{ t('common.refresh') }}
                      </BaseButton>
                    </div>
                    <div class="mt-2 flex flex-wrap gap-2 text-xs">
                      <span class="rounded-full bg-slate-100 px-2.5 py-1 font-semibold text-slate-700">
                        {{ rules.length }} 个模板
                      </span>
                      <span class="rounded-full bg-slate-100 px-2.5 py-1 font-semibold text-slate-700">
                        {{ totalRuleCount }} 条规则
                      </span>
                      <span
                        class="rounded-full px-2.5 py-1 font-semibold"
                        :class="templatesWithFindings ? 'bg-amber-100 text-amber-700' : 'bg-emerald-100 text-emerald-700'"
                      >
                        {{ templatesWithFindings }} 个待处理
                      </span>
                    </div>
                  </div>
                  <div class="grid gap-3 sm:grid-cols-[minmax(0,18rem)_10rem]">
                    <label class="admin-filter-field">
                      <span class="admin-filter-label">搜索模板</span>
                      <input
                        v-model="filters.keyword"
                        class="admin-filter-control"
                        placeholder="模板名称、文件名"
                      />
                    </label>
                    <label class="admin-filter-field">
                      <span class="admin-filter-label">分类</span>
                      <select v-model="filters.category" class="admin-filter-control">
                        <option value="all">全部</option>
                        <option v-for="item in availableCategories" :key="item" :value="item">
                          {{ ruleCategoryLabel(item) }}
                        </option>
                      </select>
                    </label>
                  </div>
                </div>
              </div>

              <div class="bg-slate-50/60 p-3">
                <p v-if="!filteredRules.length" class="rounded-lg bg-white px-4 py-12 text-center text-sm text-slate-400">
                  {{ t('common.noData') }}
                </p>
                <div v-else class="grid gap-3">
                  <router-link
                    v-for="rule in filteredRules"
                    :key="rule.name"
                    class="group block rounded-xl border border-slate-200/80 bg-white px-4 py-4 transition hover:border-blue-200 hover:bg-blue-50/30 hover:shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500/30"
                    :to="ruleDetailRoute(rule)"
                  >
                    <div class="grid gap-4 lg:grid-cols-[minmax(0,1fr)_13rem_10rem] lg:items-center">
                      <div class="min-w-0">
                        <div class="flex flex-wrap items-center gap-2">
                          <p class="break-words text-sm font-semibold text-slate-950">
                            {{ rule.title || rule.name }}
                          </p>
                          <span
                            class="inline-flex rounded-full px-2 py-0.5 text-xs font-semibold"
                            :class="templateStatusClass(rule)"
                          >
                            {{ templateStatusLabel(rule) }}
                          </span>
                        </div>
                        <p class="mt-1 break-all font-mono text-xs text-slate-500">{{ rule.name }}</p>
                        <div class="mt-3 flex flex-wrap gap-1.5">
                          <span
                            v-for="item in visibleRuleCategories(rule)"
                            :key="item"
                            class="inline-flex rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-600"
                          >
                            {{ ruleCategoryLabel(item) }}
                          </span>
                          <span
                            v-if="hiddenCategoryCount(rule)"
                            class="inline-flex rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-500"
                          >
                            +{{ hiddenCategoryCount(rule) }}
                          </span>
                        </div>
                      </div>

                      <div class="grid grid-cols-2 gap-2 text-center">
                        <div class="rounded-lg bg-slate-50 px-3 py-2">
                          <p class="text-base font-semibold text-slate-950">{{ rule.rule_count ?? '-' }}</p>
                          <p class="text-xs text-slate-500">规则</p>
                        </div>
                        <div class="rounded-lg bg-slate-50 px-3 py-2">
                          <p class="text-base font-semibold text-slate-950">{{ rule.group_count ?? '-' }}</p>
                          <p class="text-xs text-slate-500">分组</p>
                        </div>
                      </div>

                      <div class="flex items-center justify-between gap-3 lg:justify-end">
                        <span
                          v-if="ruleFindingsFor(rule).length"
                          class="inline-flex rounded-full bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-700"
                        >
                          {{ ruleFindingsFor(rule).length }} 个治理项
                        </span>
                        <span class="inline-flex min-h-10 items-center rounded-lg border border-slate-200 px-3 text-sm font-semibold text-slate-700 transition group-hover:border-blue-200 group-hover:text-blue-700">
                          查看详情
                        </span>
                      </div>
                    </div>
                  </router-link>
                </div>
              </div>
            </section>
          </section>
        </AdminPageState>
      </AdminListSection>
    </PageFrame>
  </AdminLayout>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AdminLayout from '@/admin/layout/AdminLayout.vue'
import AdminListSection from '@/admin/components/AdminListSection.vue'
import AdminPageState from '@/admin/components/AdminPageState.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import PageFrame from '@/components/ui/PageFrame.vue'
import { monitoringStackApi } from '@/admin/api/monitoringStack'

const { t } = useI18n()
const loading = ref(false)
const error = ref('')
const rules = ref([])
const ruleFindings = ref([])
const filters = reactive({
  keyword: '',
  category: 'all'
})

const availableCategories = computed(() =>
  [...new Set(rules.value.flatMap((rule) => rule.categories || []).filter(Boolean))].sort()
)

const filteredRules = computed(() => {
  const keyword = filters.keyword.trim().toLowerCase()
  return rules.value.filter((rule) => {
    if (filters.category !== 'all' && !(rule.categories || []).includes(filters.category)) return false
    if (!keyword) return true
    return [rule.name, rule.title]
      .filter(Boolean)
      .some((item) => String(item).toLowerCase().includes(keyword))
  })
})

const totalRuleCount = computed(() =>
  rules.value.reduce((total, rule) => total + Number(rule.rule_count || 0), 0)
)

const templatesWithFindings = computed(() =>
  rules.value.filter((rule) => ruleFindingsFor(rule).length > 0).length
)

const categoryLabels = {
  mixed: '综合',
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

function ruleCategoryLabel(category) {
  const value = String(category || '').toLowerCase()
  return categoryLabels[value] || category || '未分类'
}

function deriveTemplateCategories(detail, fallback) {
  const categories = new Set()
  for (const group of detail?.groups || []) {
    for (const rule of group.rules || []) {
      if (rule.category) categories.add(String(rule.category).toLowerCase())
    }
  }
  if (!categories.size && fallback) categories.add(String(fallback).toLowerCase())
  return [...categories].sort()
}

function visibleRuleCategories(rule) {
  const categories = rule.categories?.length ? rule.categories : [rule.category].filter(Boolean)
  return categories.slice(0, 4)
}

function hiddenCategoryCount(rule) {
  const categories = rule.categories?.length ? rule.categories : [rule.category].filter(Boolean)
  return Math.max(0, categories.length - 4)
}

function ruleFindingsFor(rule) {
  return ruleFindings.value.filter((finding) => finding.subject_key === rule.name)
}

function templateStatusLabel(rule) {
  const findings = ruleFindingsFor(rule)
  if (findings.some((item) => item.category === 'rule_template_not_imported')) return '待同步'
  if (findings.length) return '待处理'
  return '正常'
}

function templateStatusClass(rule) {
  const status = templateStatusLabel(rule)
  if (status === '待同步') return 'bg-amber-100 text-amber-700'
  if (status === '待处理') return 'bg-orange-100 text-orange-700'
  return 'bg-emerald-100 text-emerald-700'
}

function ruleDetailRoute(rule) {
  return {
    name: 'AdminMonitoringRuleDetail',
    params: { templateName: rule.name }
  }
}

async function loadRuleStats(items) {
  const stats = await Promise.allSettled(
    items.map((rule) => monitoringStackApi.getRule(rule.name))
  )
  return items.map((rule, index) => {
    const detail = stats[index].status === 'fulfilled' ? stats[index].value : null
    const categories = deriveTemplateCategories(detail, rule.category)
    return {
      ...rule,
      category: categories.length > 1 ? 'mixed' : categories[0] || rule.category,
      categories,
      rule_count: Number(detail?.rule_count ?? rule.rule_count ?? 0),
      group_count: Number(detail?.groups?.length ?? rule.group_count ?? 0)
    }
  })
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    await monitoringStackApi.getGovernanceOverview()
    const [rulesData, findingData] = await Promise.all([
      monitoringStackApi.getRules(),
      monitoringStackApi.getGovernanceFindings({ status: 'open', subject_type: 'rule' })
    ])
    ruleFindings.value = normalizeList(findingData)
    rules.value = await loadRuleStats(normalizeList(rulesData))
  } catch (err) {
    error.value = err?.response?.data?.detail || err.message
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>
