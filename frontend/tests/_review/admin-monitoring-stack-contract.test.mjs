import { strict as assert } from 'node:assert'
import { existsSync, readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const repoRoot = resolve(here, '..', '..')

const platformAccessPath = resolve(repoRoot, 'src/utils/platformAccess.js')
const routesPath = resolve(repoRoot, 'src/admin/routes.js')
const sidebarPath = resolve(repoRoot, 'src/admin/layout/AdminSidebar.vue')
const apiPath = resolve(repoRoot, 'src/admin/api/monitoringStack.js')
const globalApiPath = resolve(repoRoot, 'src/api/index.js')
const pagePaths = [
  'src/admin/pages/Monitoring/Overview.vue',
  'src/admin/pages/Monitoring/Installers.vue',
  'src/admin/pages/Monitoring/Probes.vue',
  'src/admin/pages/Monitoring/BlackboxInstances.vue',
  'src/admin/pages/Monitoring/Assets.vue',
  'src/admin/pages/Monitoring/Rules.vue',
  'src/admin/pages/Monitoring/RuleDetail.vue',
  'src/admin/pages/Monitoring/Jobs.vue',
  'src/admin/pages/Monitoring/Settings.vue'
].map((path) => resolve(repoRoot, path))

for (const filePath of [platformAccessPath, routesPath, sidebarPath, apiPath, globalApiPath, ...pagePaths]) {
  assert.ok(existsSync(filePath), `${filePath} must exist`)
}

const platformAccessSource = readFileSync(platformAccessPath, 'utf8')
const routesSource = readFileSync(routesPath, 'utf8')
const sidebarSource = readFileSync(sidebarPath, 'utf8')
const apiSource = readFileSync(apiPath, 'utf8')
const globalApiSource = readFileSync(globalApiPath, 'utf8')
const overviewSource = readFileSync(resolve(repoRoot, 'src/admin/pages/Monitoring/Overview.vue'), 'utf8')
const installersSource = readFileSync(resolve(repoRoot, 'src/admin/pages/Monitoring/Installers.vue'), 'utf8')
const probesSource = readFileSync(resolve(repoRoot, 'src/admin/pages/Monitoring/Probes.vue'), 'utf8')
const blackboxSource = readFileSync(resolve(repoRoot, 'src/admin/pages/Monitoring/BlackboxInstances.vue'), 'utf8')
const assetsSource = readFileSync(resolve(repoRoot, 'src/admin/pages/Monitoring/Assets.vue'), 'utf8')
const rulesSource = readFileSync(resolve(repoRoot, 'src/admin/pages/Monitoring/Rules.vue'), 'utf8')
const ruleDetailSource = readFileSync(resolve(repoRoot, 'src/admin/pages/Monitoring/RuleDetail.vue'), 'utf8')
const jobsSource = readFileSync(resolve(repoRoot, 'src/admin/pages/Monitoring/Jobs.vue'), 'utf8')
const settingsSource = readFileSync(resolve(repoRoot, 'src/admin/pages/Monitoring/Settings.vue'), 'utf8')
const uiLanguageSource = readFileSync(resolve(repoRoot, 'src/utils/uiLanguage.js'), 'utf8')
const uiLanguage = await import(pathToFileURL(resolve(repoRoot, 'src/utils/uiLanguage.js')).href)
const localeSources = {
  en: JSON.parse(readFileSync(resolve(repoRoot, 'src/admin/locales/en.json'), 'utf8')),
  zhCN: JSON.parse(readFileSync(resolve(repoRoot, 'src/admin/locales/zh-CN.json'), 'utf8'))
}

assert.match(
  platformAccessSource,
  /key:\s*'admin_monitoring'/,
  'platform access should expose admin_monitoring'
)
assert.match(
  platformAccessSource,
  /defaultPath:\s*'\/management\/monitoring\/overview'/,
  'admin_monitoring should land on monitoring access overview'
)
assert.match(
  routesSource,
  /path:\s*'\/management\/monitoring\/overview'/,
  'admin routes should include monitoring overview'
)
assert.match(
  routesSource,
  /path:\s*'\/management\/monitoring\/installers'/,
  'admin routes should keep monitoring installers available as an advanced page'
)
assert.match(
  routesSource,
  /path:\s*'\/management\/monitoring\/settings'/,
  'admin routes should include monitoring integration settings'
)
assert.match(
  routesSource,
  /path:\s*'\/management\/monitoring\/blackbox'/,
  'admin routes should include blackbox instance management'
)
assert.match(
  routesSource,
  /path:\s*'\/management\/monitoring\/rules\/:templateName'/,
  'admin routes should include monitoring rule template detail'
)
assert.match(
  routesSource,
  /requiredFeature:\s*'admin_monitoring'/,
  'monitoring routes should require admin_monitoring'
)
assert.match(
  sidebarSource,
  /adminNav\.monitoringManagement/,
  'admin sidebar should include monitoring management navigation'
)
assert.match(
  sidebarSource,
  /adminNav\.monitoringOverview/,
  'admin sidebar should expose monitoring overview navigation'
)
assert.match(
  sidebarSource,
  /adminNav\.monitoringSettings/,
  'admin sidebar should expose monitoring integration settings navigation'
)
assert.doesNotMatch(
  sidebarSource,
  /adminNav\.monitoringBlackbox/,
  'blackbox instances should stay routable but not be exposed as primary sidebar navigation'
)
assert.match(
  apiSource,
  /\/v1\/monitoring\/probe-targets\//,
  'monitoring API client should target the new monitoring API prefix'
)
assert.match(
  globalApiSource,
  /getRequestUiLanguage\(\)/,
  'API requests should use the shared UI language normalization'
)
assert.match(
  uiLanguageSource,
  /DEFAULT_UI_LANGUAGE\s*=\s*'zh-CN'/,
  'HyperOps UI should default to Chinese when no explicit UI language is saved'
)
assert.equal(
  uiLanguage.normalizeUiLanguage('zh'),
  'zh-CN',
  'legacy zh UI language values should stay Chinese, not fall back to English'
)
assert.equal(
  uiLanguage.normalizeUiLanguage('zh-Hans'),
  'zh-CN',
  'Chinese browser language variants should normalize to zh-CN'
)
assert.equal(
  uiLanguage.normalizeUiLanguage(null),
  'zh-CN',
  'missing UI language should default to zh-CN for the admin console'
)
assert.equal(
  uiLanguage.getStoredUiLanguage(),
  'zh-CN',
  'server-side and first-load UI language resolution should default to zh-CN'
)
assert.match(
  apiSource,
  /createJob\(body\)/,
  'monitoring API client should expose install job creation'
)
assert.match(
  apiSource,
  /getPrometheusTargetsSummary\(\)/,
  'monitoring API client should expose Prometheus target summary'
)
assert.match(
  apiSource,
  /getPrometheusHttpSdConfig\(\)/,
  'monitoring API client should expose Prometheus HTTP SD config preview'
)
assert.match(
  apiSource,
  /getProbeNodes\(params/,
  'monitoring API client should expose blackbox probe node listing'
)
assert.match(
  apiSource,
  /createProbeNode\(body\)/,
  'monitoring API client should expose blackbox probe node creation'
)
assert.match(
  apiSource,
  /rotatePrometheusHttpSdToken\(\)/,
  'monitoring API client should expose Prometheus HTTP SD token generation'
)
assert.match(
  apiSource,
  /getBlackboxInstances\(\)/,
  'monitoring API client should expose blackbox instance aggregation'
)
assert.match(
  apiSource,
  /getAssetsReconciliation\(\)/,
  'monitoring API client should expose asset reconciliation'
)
assert.match(
  apiSource,
  /getN9eSummary\(\)/,
  'monitoring API client should expose n9e platform summary'
)
assert.match(
  apiSource,
  /syncGovernance\(source/,
  'monitoring API client should expose governance snapshot sync'
)
assert.match(
  apiSource,
  /\/v1\/monitoring\/governance\/sync\//,
  'monitoring API client should call the governance sync endpoint'
)
assert.match(
  apiSource,
  /getGovernanceOverview\(\)/,
  'monitoring API client should expose governance overview'
)
assert.match(
  apiSource,
  /getGovernanceFindings\(params/,
  'monitoring API client should expose governance findings'
)
assert.match(
  apiSource,
  /resolveGovernanceFinding\(id,\s*body/,
  'monitoring API client should expose governance finding resolution'
)
assert.match(
  apiSource,
  /\/v1\/monitoring\/governance\/overview\//,
  'monitoring API client should call the governance overview endpoint'
)
assert.match(
  apiSource,
  /\/v1\/monitoring\/governance\/findings\//,
  'monitoring API client should call the governance findings endpoint'
)
assert.match(
  apiSource,
  /\/v1\/monitoring\/governance\/findings\/\$\{id\}\/resolve\//,
  'monitoring API client should call the governance finding resolve endpoint'
)
assert.match(
  apiSource,
  /deleteRule\(name,\s*body\)/,
  'monitoring API client should expose rule deletion'
)
assert.match(
  apiSource,
  /createRule\(name,\s*body\)/,
  'monitoring API client should expose rule creation'
)
assert.match(
  apiSource,
  /getRuleDiff\(name,\s*params\s*=\s*\{\}\)/,
  'monitoring API client should expose rule diff preview'
)
assert.match(
  overviewSource,
  /hyperopsConfigState/,
  'overview page should keep HyperOps configuration as a distinct status card'
)
assert.match(
  overviewSource,
  /prometheusRealityState/,
  'overview page should keep Prometheus reality as a distinct status card'
)
assert.match(
  overviewSource,
  /n9eRealityState/,
  'overview page should keep n9e reality as a distinct status card'
)
assert.doesNotMatch(
  overviewSource,
  /sourceHyperOps|sourceN9e|sourcePrometheus/,
  'overview page should not show repeated source explanation labels'
)
assert.match(
  overviewSource,
  /syncGovernance\('all'\)/,
  'overview page should allow operators to sync real monitoring state'
)
assert.match(
  overviewSource,
  /getGovernanceOverview\(\)/,
  'overview page should load backend governance overview'
)
assert.match(
  overviewSource,
  /governanceFindingsTitle/,
  'overview page should show actionable governance findings'
)
assert.match(
  overviewSource,
  /syncRealState/,
  'overview page should label the real-state sync action'
)
assert.match(
  installersSource,
  /getInstallerAssets/,
  'installers page should own installer asset status'
)
assert.doesNotMatch(
  settingsSource,
  /getInstallerAssets|buildInstallerAssets|installerFiles/,
  'settings page should stay focused on integrations and defaults, not installer file status'
)
assert.match(
  settingsSource,
  /rotatePrometheusHttpSdToken\(\)/,
  'settings page should allow operators to generate the Prometheus HTTP SD token'
)
assert.match(
  settingsSource,
  /generatedToken/,
  'settings page should show the generated HTTP SD token once for copying'
)
assert.match(
  installersSource,
  /installerOptions/,
  'installers page should use backend-provided installer options'
)
assert.match(
  probesSource,
  /updateProbeTarget\(form\.id/,
  'probe targets page should support editing existing targets'
)
assert.match(
  probesSource,
  /prometheusStatusFor/,
  'probe targets page should compare HyperOps configuration with Prometheus reality'
)
assert.match(
  probesSource,
  /getGovernanceFindings\(\{\s*status:\s*'open',\s*subject_type:\s*'probe'/,
  'probe targets page should load open probe governance findings'
)
assert.match(
  probesSource,
  /resolveGovernanceFinding\(/,
  'probe targets page should resolve probe governance findings through the API client'
)
assert.match(
  probesSource,
  /getPrometheusHttpSdConfig\(\)/,
  'probe targets page should load copyable Prometheus HTTP SD config'
)
assert.match(
  probesSource,
  /getProbeNodes\(\)/,
  'probe targets page should load blackbox probe nodes'
)
assert.match(
  probesSource,
  /probe_node:\s*form\.probeNode/,
  'probe targets page should bind targets to selected probe nodes'
)
assert.match(
  probesSource,
  /copyPrometheusYaml/,
  'probe targets page should let operators copy Prometheus YAML'
)
assert.match(
  blackboxSource,
  /getBlackboxInstances\(\)/,
  'blackbox page should load aggregated blackbox instances'
)
assert.match(
  blackboxSource,
  /syncGovernance\('all'\)/,
  'blackbox page should let operators resync real monitoring state'
)
assert.match(
  assetsSource,
  /createJob\(/,
  'assets page should be able to execute install jobs'
)
assert.match(
  assetsSource,
  /alignmentStatus/,
  'assets page should expose alignment status filtering'
)
assert.match(
  assetsSource,
  /host_not_scraped_by_prometheus/,
  'assets page should surface Prometheus host scrape drift'
)
assert.match(
  assetsSource,
  /getAssetsReconciliation\(\)/,
  'assets page should load n9e and Prometheus discovered assets'
)
assert.match(
  assetsSource,
  /v-if="discoveredAssets\.length"/,
  'assets page should only show the discovered assets panel when external assets exist'
)
assert.doesNotMatch(
  assetsSource,
  /noDiscoveredAssets/,
  'assets page should not render an always-visible empty discovered assets table'
)
assert.match(
  assetsSource,
  /importDiscoveredAsset/,
  'assets page should import discovered assets into HyperOps'
)
assert.match(
  assetsSource,
  /getGovernanceFindings\(\{\s*status:\s*'open',\s*subject_type:\s*'host'/,
  'assets page should load open host governance findings'
)
assert.doesNotMatch(
  assetsSource,
  /collectionOverview|function collectionStates|monitoring\.collectionStatus/,
  'assets table should not show a separate collection-status column'
)
assert.match(
  assetsSource,
  /installComponents/,
  'assets page should use one install component entry for single-host and bulk installs'
)
assert.match(
  assetsSource,
  /hostComponentFindingLabel\(finding,\s*'categraf'\)/,
  'assets page should use short component status labels inside the Categraf column'
)
assert.match(
  assetsSource,
  /hostComponentFindingLabel\(finding,\s*'blackbox'\)/,
  'assets page should use short component status labels inside the blackbox column'
)
assert.match(
  assetsSource,
  /return t\('adminPages\.monitoring\.installStatusNotInstalled'\)/,
  'component install drift badges should render as "not installed" without repeating the component name'
)
assert.match(
  assetsSource,
  /value === 'external' \? 'success' : value/,
  'assets page should show externally discovered components as installed instead of unknown'
)
assert.match(
  assetsSource,
  /componentDisplayText\(host,\s*'categraf'\)/,
  'assets page should merge install and runtime state into one Categraf badge'
)
assert.match(
  assetsSource,
  /componentDisplayText\(host,\s*'blackbox'\)/,
  'assets page should merge install and runtime state into one blackbox badge'
)
assert.doesNotMatch(
  assetsSource,
  /runtimeStatusText|runtimeStatusClass/,
  'assets page should not stack a separate runtime badge below the install badge'
)
assert.doesNotMatch(
  assetsSource,
  /repairableHostFindings|hostFindingActionText|resolveHostFinding\(finding\)/,
  'assets page should not show row-level install buttons next to every host'
)
assert.match(
  rulesSource,
  /AdminMonitoringRuleDetail/,
  'rules list page should link to rule template detail pages'
)
assert.match(
  rulesSource,
  /loadRuleStats/,
  'rules list page should summarize template rule and group counts'
)
assert.match(
  rulesSource,
  /getGovernanceFindings\(\{\s*status:\s*'open',\s*subject_type:\s*'rule'/,
  'rules list page should load open rule governance findings'
)
assert.match(
  ruleDetailSource,
  /useRoute/,
  'rule detail page should read the selected template from the route'
)
assert.match(
  ruleDetailSource,
  /discoverN9e/,
  'rule detail page should load n9e groups and datasources before import'
)
assert.match(
  ruleDetailSource,
  /refreshN9eOptions/,
  'rule detail page should refresh n9e groups and datasources from integration config'
)
assert.match(
  ruleDetailSource,
  /getGovernanceFindings\(\{\s*status:\s*'open',\s*subject_type:\s*'rule'/,
  'rule detail page should load open rule governance findings'
)
assert.match(
  ruleDetailSource,
  /resolveGovernanceFinding\(/,
  'rule detail page should resolve ignorable rule governance findings through the API client'
)
assert.match(
  ruleDetailSource,
  /requestConfirm\(/,
  'rule detail page should confirm before deleting a rule'
)
assert.match(
  ruleDetailSource,
  /deleteRule\(selectedRule\.value/,
  'rule detail page should delete a rule through the monitoring API client'
)
assert.match(
  ruleDetailSource,
  /openCreateRule\(/,
  'rule detail page should expose a create-rule flow'
)
assert.match(
  ruleDetailSource,
  /openCopyRule\(/,
  'rule detail page should expose a copy-rule flow'
)
assert.match(
  ruleDetailSource,
  /showYamlModal/,
  'rule detail page should open YAML in a focused editor modal instead of expanding it below the list'
)
assert.match(
  ruleDetailSource,
  /saveYamlContent/,
  'rule detail page should support saving full YAML template edits'
)
assert.doesNotMatch(
  ruleDetailSource,
  /原始 YAML 内容|showYamlPreview/,
  'rule detail page should not show raw YAML as an inline details block below the rule list'
)
assert.match(
  ruleDetailSource,
  /createRule\(selectedRule\.value/,
  'rule detail page should create rules through the monitoring API client'
)
assert.match(
  ruleDetailSource,
  /syncChangePreview/,
  'rule detail page should show a change preview before syncing rules to n9e'
)
assert.match(
  ruleDetailSource,
  /getRuleDiff\(selectedRule\.value,/,
  'rule detail page should load backend rule diff before syncing to n9e'
)
assert.match(
  ruleDetailSource,
  /getRuleDiff\(selectedRule\.value,\s*\{[\s\S]*group_id:\s*form\.groupId[\s\S]*datasource_id:\s*form\.datasourceId/,
  'rule detail page should request rule diff using the selected n9e group and datasource'
)
assert.match(
  ruleDetailSource,
  /@change="loadRuleDiff"/,
  'rule detail page should refresh rule diff when the selected group or datasource changes'
)
assert.match(
  ruleDetailSource,
  /ruleDiffSummaryCards/,
  'rule detail page should summarize created, updated, deleted, and unchanged rule counts'
)
assert.match(
  ruleDetailSource,
  /baselineSourceLabel/,
  'rule detail page should show whether rule diff comes from live n9e data or snapshots'
)
assert.match(
  ruleDetailSource,
  /n9e 独有/,
  'rule detail page should call rules that only exist in n9e "n9e only" instead of delete'
)
assert.doesNotMatch(
  ruleDetailSource,
  /label:\s*'删除'/,
  'rule detail page should not present n9e-only rules as rules that will be deleted'
)
assert.match(
  ruleDetailSource,
  /刷新对比/,
  'rule detail page should provide an explicit refresh diff action'
)
assert.doesNotMatch(
  ruleDetailSource,
  /const syncChangePreview[\s\S]*const items = ruleChangeLog[\s\S]*if \(items\.length\) return items[\s\S]*const diffItems/,
  'rule detail page should not let local edit logs hide backend rule diff preview'
)
assert.match(
  ruleDetailSource,
  /count_available\s*===\s*false/,
  'rule detail page should not render unavailable n9e import counts as zero-count results'
)
assert.match(
  ruleDetailSource,
  /未提供明细/,
  'rule detail page should explain when n9e import does not return itemized counts'
)
assert.doesNotMatch(
  ruleDetailSource,
  /return currentTemplateRulePreview\('sync'\)/,
  'rule detail page should not present every rule in a full sync as a real change item'
)
assert.doesNotMatch(
  ruleDetailSource,
  /password:\s*form\.password|n9ePassword/,
  'rule detail page should use saved n9e credentials instead of asking for the password again'
)
assert.match(
  jobsSource,
  /getGovernanceFindings\(\{\s*status:\s*'open',\s*subject_type:\s*'job'/,
  'jobs page should load open job governance findings'
)
assert.match(
  jobsSource,
  /resolveGovernanceFinding\(/,
  'jobs page should retry failed install jobs through governance finding resolution'
)

for (const [name, source] of [
  ['overview', overviewSource],
  ['installers', installersSource],
  ['probes', probesSource],
  ['blackbox', blackboxSource],
  ['assets', assetsSource],
  ['rules', rulesSource],
  ['ruleDetail', ruleDetailSource],
  ['jobs', jobsSource],
  ['settings', settingsSource]
]) {
  assert.doesNotMatch(
    source,
    /tr\('adminPages\.monitoring|sourceHyperOps|sourceN9e|sourcePrometheus/,
    `${name} page should not rely on raw-key fallbacks or repeated source explanation labels`
  )
}

assert.equal(
  localeSources.zhCN.adminPages.monitoring.activeTargets,
  '正常采集目标',
  'Chinese Prometheus active target label should be operational, not mixed English'
)
assert.equal(
  localeSources.zhCN.adminPages.monitoring.downTargets,
  '异常采集目标',
  'Chinese Prometheus down target label should be operational, not mixed English'
)
assert.equal(
  localeSources.zhCN.adminPages.monitoring.installComponents,
  '安装组件',
  'Chinese asset toolbar should not show the English install component label'
)
assert.equal(
  localeSources.zhCN.adminPages.monitoring.runtimeOnline,
  '在线',
  'Chinese component runtime label should be concise inside component status columns'
)

const monitoringLocaleKeys = new Set()
for (const filePath of pagePaths) {
  const source = readFileSync(filePath, 'utf8')
  for (const match of source.matchAll(/adminPages\.monitoring\.([A-Za-z0-9_]+)/g)) {
    monitoringLocaleKeys.add(match[1])
  }
}

for (const key of monitoringLocaleKeys) {
  assert.ok(
    localeSources.en.adminPages?.monitoring?.[key],
    `en locale should define adminPages.monitoring.${key}`
  )
  assert.ok(
    localeSources.zhCN.adminPages?.monitoring?.[key],
    `zh-CN locale should define adminPages.monitoring.${key}`
  )
}

console.log('admin-monitoring-stack-contract.test.mjs: OK')
