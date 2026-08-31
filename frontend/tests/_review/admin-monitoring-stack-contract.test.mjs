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
  'src/admin/pages/Monitoring/ProbeSettings.vue',
  'src/admin/pages/Monitoring/probes/ProbeManagementTabs.vue',
  'src/admin/pages/Monitoring/BlackboxInstances.vue',
  'src/admin/pages/Monitoring/Assets.vue',
  'src/admin/pages/Monitoring/Rules.vue',
  'src/admin/pages/Monitoring/RuleDetail.vue',
  'src/admin/pages/Monitoring/Jobs.vue',
  'src/admin/pages/Monitoring/HostDeploymentStatus.vue',
  'src/admin/pages/Monitoring/Settings.vue'
].map((path) => resolve(repoRoot, path))

for (const filePath of [
  platformAccessPath,
  routesPath,
  sidebarPath,
  apiPath,
  globalApiPath,
  ...pagePaths
]) {
  assert.ok(existsSync(filePath), `${filePath} must exist`)
}

const platformAccessSource = readFileSync(platformAccessPath, 'utf8')
const routesSource = readFileSync(routesPath, 'utf8')
const sidebarSource = readFileSync(sidebarPath, 'utf8')
const apiSource = readFileSync(apiPath, 'utf8')
const globalApiSource = readFileSync(globalApiPath, 'utf8')
const overviewSource = readFileSync(
  resolve(repoRoot, 'src/admin/pages/Monitoring/Overview.vue'),
  'utf8'
)
const installersSource = readFileSync(
  resolve(repoRoot, 'src/admin/pages/Monitoring/Installers.vue'),
  'utf8'
)
const probesSource = readFileSync(
  resolve(repoRoot, 'src/admin/pages/Monitoring/Probes.vue'),
  'utf8'
)
const probeSettingsSource = readFileSync(
  resolve(repoRoot, 'src/admin/pages/Monitoring/ProbeSettings.vue'),
  'utf8'
)
const probeTabsSource = readFileSync(
  resolve(
    repoRoot,
    'src/admin/pages/Monitoring/probes/ProbeManagementTabs.vue'
  ),
  'utf8'
)
const blackboxSource = readFileSync(
  resolve(repoRoot, 'src/admin/pages/Monitoring/BlackboxInstances.vue'),
  'utf8'
)
const assetsSource = readFileSync(
  resolve(repoRoot, 'src/admin/pages/Monitoring/Assets.vue'),
  'utf8'
)
const rulesSource = readFileSync(
  resolve(repoRoot, 'src/admin/pages/Monitoring/Rules.vue'),
  'utf8'
)
const ruleDetailSource = readFileSync(
  resolve(repoRoot, 'src/admin/pages/Monitoring/RuleDetail.vue'),
  'utf8'
)
const jobsSource = readFileSync(
  resolve(repoRoot, 'src/admin/pages/Monitoring/Jobs.vue'),
  'utf8'
)
const hostDeploymentSource = readFileSync(
  resolve(repoRoot, 'src/admin/pages/Monitoring/HostDeploymentStatus.vue'),
  'utf8'
)
const hostCurrentStatusSource = hostDeploymentSource.slice(
  hostDeploymentSource.indexOf(`v-if="activeTab === 'current'"`),
  hostDeploymentSource.indexOf(`v-else-if="activeTab === 'history'"`)
)
const settingsSource = readFileSync(
  resolve(repoRoot, 'src/admin/pages/Monitoring/Settings.vue'),
  'utf8'
)
const jobHistoryUtilsPath = resolve(
  repoRoot,
  'src/admin/utils/monitoringJobHistory.js'
)
const uiLanguageSource = readFileSync(
  resolve(repoRoot, 'src/utils/uiLanguage.js'),
  'utf8'
)
const i18nSource = readFileSync(resolve(repoRoot, 'src/i18n/index.js'), 'utf8')
const uiLanguage = await import(
  pathToFileURL(resolve(repoRoot, 'src/utils/uiLanguage.js')).href
)
const { normalizeHostSummaries, keepLogPinnedAfterRender } = await import(
  pathToFileURL(jobHistoryUtilsPath).href
)
const localeSources = {
  en: JSON.parse(
    readFileSync(resolve(repoRoot, 'src/admin/locales/en.json'), 'utf8')
  ),
  zhCN: JSON.parse(
    readFileSync(resolve(repoRoot, 'src/admin/locales/zh-CN.json'), 'utf8')
  )
}

assert.equal(
  localeSources.zhCN.adminPages.monitoring.duplicateTarget,
  '创建副本',
  'Chinese probe actions should label duplicate creation in Chinese'
)
assert.equal(
  localeSources.en.adminPages.monitoring.duplicateTarget,
  'Create copy',
  'English probe actions should keep an English duplicate label'
)
assert.match(
  i18nSource,
  /import\.meta\.hot\.accept\([\s\S]*window\.location\.reload\(\)/,
  'locale resource updates should reload atomically instead of leaving mixed-language HMR state'
)

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
  /path:\s*'\/management\/monitoring\/installers',[\s\S]*redirect:[\s\S]*path:\s*'\/management\/monitoring\/jobs'[\s\S]*view:\s*'resources'/,
  'legacy installer URLs should redirect to the deployment resource tab'
)
assert.match(
  routesSource,
  /path:\s*'\/management\/monitoring\/probes\/nodes'/,
  'admin routes should include probe node management'
)
assert.match(
  routesSource,
  /path:\s*'\/management\/monitoring\/probes\/settings'/,
  'admin routes should include probe foundational settings'
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
  /adminNav\.monitoringProbeManagement/,
  'admin sidebar should expose probe management as one product area'
)
assert.match(
  probeTabsSource,
  /monitoring\/probes\/nodes/,
  'probe management tabs should link to probe nodes'
)
assert.match(
  probeTabsSource,
  /monitoring\/probes\/settings/,
  'probe management tabs should link to access configuration'
)
assert.match(
  probesSource,
  /ProbeManagementTabs/,
  'probe targets should use the shared probe management tabs'
)
assert.match(
  probeSettingsSource,
  /isNodesPage/,
  'probe node and access configuration routes should render focused content'
)
assert.match(
  probeSettingsSource,
  /component:\s*'blackbox'/,
  'probe node management should own blackbox deployment'
)
assert.match(
  probeSettingsSource,
  /blackboxHostDeploymentState[\s\S]*blackboxDeployableHosts[\s\S]*canDeployBlackbox/,
  'blackbox deployment should derive host eligibility from component and probe-node state'
)
assert.match(
  probeSettingsSource,
  /:disabled="blackboxHostDeploymentState\(host\)\.disabled"[\s\S]*noBlackboxDeploymentCandidates/,
  'blackbox deployment should disable managed hosts and explain when no candidates remain'
)
assert.match(
  probeSettingsSource,
  /nodeIdentityManaged[\s\S]*nodeActionText[\s\S]*managedProbeNodeNotice/,
  'managed probe nodes should use a management action and explain their ownership boundary'
)
assert.match(
  probeSettingsSource,
  /:readonly="nodeIdentityManaged"[\s\S]*:disabled="nodeIdentityManaged"/,
  'deployment and discovery owned node identity fields should be read only'
)
assert.doesNotMatch(
  assetsSource,
  /componentBlackbox|installBlackbox|probe_state|blackboxJobPayload/,
  'collection hosts should only manage Categraf collection'
)
assert.match(
  sidebarSource,
  /adminNav\.monitoringSettings/,
  'admin sidebar should expose monitoring integration settings navigation'
)
assert.doesNotMatch(
  sidebarSource,
  /layout-admin-sidebar relative z-20/,
  'admin sidebar must not keep relative positioning when mobile fixed positioning is active'
)
assert.match(
  sidebarSource,
  /useWindowSize\(\)/,
  'admin sidebar should react when the viewport crosses the mobile breakpoint'
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
  /function findingTitle\(item\)/,
  'overview should translate deployment failure titles instead of rendering backend English'
)
assert.match(
  overviewSource,
  /item\.subject_type === 'job'[\s\S]*path:\s*'\/management\/monitoring\/jobs'[\s\S]*job:\s*item\.details\?\.job_id/,
  'deployment findings should open the matching deployment task detail'
)
assert.equal(
  localeSources.zhCN.adminPages.monitoring.deploymentFailedFinding,
  '{host} 的 {component} 部署失败',
  'Chinese overview should describe deployment failures in product language'
)
assert.equal(
  localeSources.zhCN.adminPages.monitoring.deploymentHistory,
  '部署记录',
  'overview deployment history should not be labelled as a current failure count'
)
assert.equal(
  localeSources.zhCN.adminPages.monitoring.viewDeploymentHistory,
  '查看记录',
  'overview deployment history action should describe its destination'
)
assert.doesNotMatch(
  overviewSource,
  /failedJobs|failedJobCount|pendingFailedJobs/,
  'overview should not present cumulative historical failures as current issues'
)
assert.match(
  overviewSource,
  /label:\s*t\('adminPages\.monitoring\.deploymentHistory'\),\s*value:\s*jobs\.value\.length/,
  'overview statistics should label the total as deployment history'
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
  installersSource,
  /<AdminLayout>|<PageFrame/,
  'installer resources should be embeddable inside deployment management'
)
assert.match(
  installersSource,
  /buildInstallerAssets/,
  'installers page should allow operators to rebuild installer assets'
)
assert.doesNotMatch(
  installersSource,
  /generatedCommand|copyCommand|installCommand|installerOptions|commandProfiles/,
  'installers page should focus on managed files instead of command generation'
)
assert.doesNotMatch(
  installersSource,
  /<details[\s\S]*installerFiles/,
  'installer files should remain visible as the primary page content'
)
assert.match(
  installersSource,
  /sm:hidden[\s\S]*adminPages\.monitoring\.download/,
  'installer rows should keep download actions visible in the mobile layout'
)
assert.match(
  installersSource,
  /hidden sm:table-cell/,
  'installer metadata columns should collapse into the mobile file row'
)
assert.doesNotMatch(
  settingsSource,
  /getInstallerAssets|buildInstallerAssets|installerFiles/,
  'settings page should stay focused on integrations and defaults, not installer file status'
)
assert.doesNotMatch(
  settingsSource,
  /rotatePrometheusHttpSdToken\(|generatedToken|prometheusHttpSdTitle/,
  'integration settings should not duplicate Prometheus HTTP SD management'
)
assert.equal(
  localeSources.zhCN.adminPages.monitoring.advancedInstallerPage,
  '安装资源',
  'the Chinese settings entry should match the installer resource destination'
)
assert.doesNotMatch(
  settingsSource,
  /installerBaseUrl|categrafInstallDir|blackboxInstallDir|blackboxPort|blackboxImage|advancedInstallerPage/,
  'integration settings should not expose deployment defaults or duplicate resource navigation'
)
assert.match(
  settingsSource,
  /integrationRows/,
  'integration settings should render each external system as a distinct row'
)
assert.match(
  settingsSource,
  /function validateUrl\(field\)/,
  'integration URLs should validate on blur'
)
assert.match(
  settingsSource,
  /showPassword/,
  'n9e credentials should provide a password visibility control'
)
assert.match(
  settingsSource,
  /<Teleport to="body">/,
  'integration settings should render editing outside the list layout'
)
assert.match(
  settingsSource,
  /max-w-xl/,
  'desktop integration editing should use a wide right-side drawer'
)
assert.match(
  settingsSource,
  /sticky bottom-0/,
  'drawer save and cancel actions should remain visible while scrolling'
)
assert.match(
  settingsSource,
  /function cancelEdit\(\)/,
  'each integration editor should support cancelling unsaved changes'
)
assert.match(
  settingsSource,
  /async function saveIntegration\(\)/,
  'each integration should save independently'
)
assert.match(
  settingsSource,
  /:disabled="!activeIsDirty \|\| hasActiveError"/,
  'the active editor should only save valid unsaved changes'
)
assert.match(
  settingsSource,
  /aria-live="polite"/,
  'save results should be announced without stealing focus'
)
assert.match(
  settingsSource,
  /unsavedIntegrationChanges/,
  'closing a dirty integration drawer should require confirmation'
)
assert.doesNotMatch(
  settingsSource,
  /adminPages\.monitoring\.saveChanges|@click="load"/,
  'the integration list should not keep page-level save or refresh actions'
)
assert.match(
  probesSource,
  /if \(id\) await monitoringStackApi\.updateProbeTarget\(id, payload\)/,
  'probe targets page should support editing existing targets'
)
assert.match(
  probesSource,
  /openActionMenuId/,
  'probe target actions should use one controlled menu instead of independent details elements'
)
assert.doesNotMatch(
  probesSource,
  /<details class="relative">/,
  'probe target rows should not allow multiple native details menus to stay open'
)
assert.match(
  probesSource,
  /function duplicateTarget\(target\)/,
  'probe targets should support opening a prefilled create form from an existing target'
)
assert.match(
  probesSource,
  /id:\s*null/,
  'duplicated probe targets must clear the source id so save creates a new target'
)
assert.match(
  probesSource,
  /targetEffectState/,
  'probe targets page should compare HyperOps configuration with Prometheus reality'
)
assert.doesNotMatch(
  probesSource,
  /getGovernanceFindings|resolveGovernanceFinding/,
  'probe targets page should not expose a separate governance workbench'
)
assert.doesNotMatch(
  probesSource,
  /getPrometheusHttpSdConfig\(\)|copyPrometheusYaml/,
  'probe targets page should not own Prometheus access configuration'
)
assert.match(
  probeSettingsSource,
  /getPrometheusHttpSdConfig\(\)/,
  'probe foundational settings should load copyable Prometheus HTTP SD config'
)
assert.match(
  probeSettingsSource,
  /getProbeNodes\(\)/,
  'probe foundational settings should load blackbox probe nodes'
)
assert.match(
  apiSource,
  /getProbeNodeDiscoveries\(\)/,
  'monitoring API should expose Prometheus probe node discoveries'
)
assert.match(
  apiSource,
  /onboardProbeNode\(body\)/,
  'monitoring API should onboard discovered probe nodes explicitly'
)
assert.match(
  probeSettingsSource,
  /v-if="isNodesPage && probeNodeDiscoveries\.length"/,
  'probe nodes should only show the discovery panel when unmanaged nodes exist'
)
assert.match(
  probeSettingsSource,
  /monitoringStackApi\.onboardProbeNode/,
  'probe settings should onboard a selected Prometheus discovery'
)
assert.match(
  probeSettingsSource,
  /bind_unassigned_targets/,
  'probe node onboarding should explicitly control unassigned target binding'
)
assert.match(
  probeSettingsSource,
  /legacy_http_sd\?\.detected/,
  'probe settings should warn when Prometheus still uses legacy HTTP SD'
)
assert.match(
  probeSettingsSource,
  /probePolicy|probe_policy/,
  'probe settings should expose the effective probe policy'
)
assert.match(
  probeSettingsSource,
  /probeScrapeInterval|probe_scrape_interval|probePolicy\.scrape_interval/,
  'probe settings should show the effective scrape interval'
)
const guidanceStart = probeSettingsSource.indexOf(
  'data-testid="probe-config-guidance"'
)
assert.ok(guidanceStart >= 0, 'probe settings should group configuration guidance')
const guidanceSource = probeSettingsSource.slice(guidanceStart, guidanceStart + 1800)
assert.match(
  guidanceSource,
  /prometheusAccessHintShort|probePolicyHint/,
  'probe settings guidance should contain the shared configuration explanation'
)
assert.match(
  probesSource,
  /ProbeTargetForm/,
  'probe targets page should bind targets to selected probe nodes'
)
assert.match(
  probeSettingsSource,
  /copyPrometheusYaml/,
  'probe foundational settings should let operators copy Prometheus YAML'
)
assert.doesNotMatch(
  probeSettingsSource,
  /tokenFilePath/,
  'embedded HTTP SD credentials should not ask operators to manage a separate token file'
)
assert.match(
  localeSources.zhCN.adminPages.monitoring.rotateTokenWarning,
  /重新复制.*重新加载 Prometheus/,
  'token rotation warning should explain how to refresh embedded Prometheus credentials'
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
  apiSource,
  /testHostConnection\(body\)/,
  'monitoring API should expose transient SSH connection testing'
)
assert.match(
  assetsSource,
  /monitoringStackApi\.testHostConnection/,
  'host form should test the current SSH settings before saving'
)
assert.match(
  assetsSource,
  /AdminMonitoringCredentials/,
  'host form should link to the dedicated credential center'
)
assert.match(
  assetsSource,
  /getCredentials\(\{\s*status:\s*'active',\s*assignable:\s*true/,
  'host form should only load active assignable credentials'
)
assert.doesNotMatch(
  assetsSource,
  /handleSshKeyFile|uploadSshKey|sshKeyUploadContent|createSshKey/,
  'host form must not ingest private key material'
)
assert.match(
  assetsSource,
  /hostConnectionSignature/,
  'host form should track the exact SSH settings that were tested'
)
assert.match(
  assetsSource,
  /isHostConnectionVerified/,
  'host form should expose whether the current SSH settings passed testing'
)
assert.match(
  assetsSource,
  /:disabled="saving \|\| !isHostConnectionVerified"/,
  'host Save should remain disabled until the current SSH settings pass'
)
assert.match(
  assetsSource,
  /filters\.query/,
  'assets page should support host name and address search'
)
assert.match(
  assetsSource,
  /filters\.scope/,
  'assets page should expose one role-aware status scope'
)
assert.match(
  assetsSource,
  /host\.collection_state/,
  'assets page should render normalized collection state'
)
assert.doesNotMatch(
  assetsSource,
  /host\.probe_state/,
  'collection hosts should not render shared probe node state'
)
assert.doesNotMatch(
  assetsSource,
  /filters\.blackboxStatus/,
  'assets page should not expose raw blackbox installation filtering'
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
assert.doesNotMatch(
  assetsSource,
  /getGovernanceFindings\(/,
  'assets page should consume normalized host state instead of loading a second findings model'
)
assert.doesNotMatch(
  assetsSource,
  /collectionOverview|function collectionStates|monitoring\.collectionStatus/,
  'assets table should not show a separate collection-status column'
)
assert.match(
  assetsSource,
  /installCategraf/,
  'assets page should expose one persistent Categraf installation entry'
)
assert.match(
  assetsSource,
  /connectionStateText\(host\.ssh_verification\)/,
  'assets page should render SSH connection state independently'
)
assert.match(
  assetsSource,
  /colspan="2"[\s\S]*componentCategraf/,
  'assets table should group Categraf installation and service columns'
)
assert.match(
  assetsSource,
  /componentInstallationText\(host\.collection_state\)/,
  'assets page should render Categraf installation in its own cell'
)
assert.match(
  assetsSource,
  /componentRuntimeText\(host\.collection_state\)/,
  'assets page should render Categraf service in its own cell'
)
assert.match(
  assetsSource,
  /function openBulkInstallChooser\(\) {\s*showBulkInstallChooser\.value = true/,
  'install chooser should open before hosts are selected'
)
assert.match(
  assetsSource,
  /v-for="host in hosts"[\s\S]*v-model="selectedHostIds"/,
  'install chooser should support selecting hosts'
)
assert.doesNotMatch(
  assetsSource,
  /v-model="selectedHostIds"[\s\S]{0,180}@change="toggleHost/,
  'install chooser should not toggle the same checkbox through two handlers'
)
assert.doesNotMatch(
  assetsSource,
  /hostRoleText|hostRequiredComponents|nextActionText|nextActionHint|runNextAction/,
  'assets rows should not render roles, stacked component rows, or next actions'
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
assert.doesNotMatch(
  jobsSource,
  /getGovernanceFindings\(|resolveGovernanceFinding\(/,
  'host-centered jobs should retry a specific host directly instead of coupling to governance findings'
)
assert.doesNotMatch(
  jobsSource,
  /t\('common\.failed'\)/,
  'jobs page should use its translated failed-status label'
)
assert.match(
  assetsSource,
  /showSuccess\([\s\S]*action:\s*\{[\s\S]*query:\s*\{\s*job:/,
  'asset installation should show a task-detail action after dispatch'
)
assert.match(jobsSource, /useRoute\(\)/, 'jobs should read the task deep link')
assert.match(
  jobsSource,
  /route\.query\.job/,
  'jobs should open the task selected by the job query parameter'
)
assert.match(
  jobsSource,
  /setInterval\([\s\S]*getJob/,
  'jobs should poll the selected active job'
)
assert.match(
  jobsSource,
  /onBeforeUnmount\(clearPolling\)/,
  'jobs should stop polling when the page unmounts'
)
assert.match(
  jobsSource,
  /selectedJob\.progress/,
  'job detail should render structured progress'
)
assert.match(
  apiSource,
  /getJobHostSummaries\(params\s*=\s*\{\}\)/,
  'monitoring API client should expose host-centered job summaries'
)
assert.match(
  apiSource,
  /retryJob\(id,\s*body\s*=\s*\{\}\)/,
  'monitoring API client should support scoped retry payloads'
)
assert.match(
  jobsSource,
  /getJobHostSummaries\(/,
  'jobs page should load host-centered summaries'
)
assert.match(
  jobsSource,
  /adminPages\.monitoring\.viewDeploymentStatus/,
  'jobs page should label the deployment status action'
)
assert.doesNotMatch(
  jobsSource,
  /hostFailureSummary\(host\)|<th[\s\S]{0,160}adminPages\.monitoring\.latestExecution/,
  'deployment list should stay focused on host and component state without execution-detail columns'
)
assert.doesNotMatch(
  jobsSource,
  /adminPages\.monitoring\.attemptShort/,
  'deployment list should show current component state without execution-count noise'
)
assert.doesNotMatch(
  jobsSource,
  /#\{\{\s*latestExecution|`#\$\{selectedJob/,
  'deployment list should present task references without hash-prefixed IDs'
)
assert.match(
  routesSource,
  /path:\s*'\/management\/monitoring\/jobs\/hosts\/:hostId'[\s\S]*name:\s*'AdminMonitoringHostDeploymentStatus'[\s\S]*HostDeploymentStatus\.vue/,
  'host deployment status should have a shareable authenticated route'
)
assert.match(
  jobsSource,
  /name:\s*'AdminMonitoringHostDeploymentStatus'[\s\S]*hostId:\s*host\.host_id/,
  'deployment list should navigate to the selected host status workspace'
)
assert.doesNotMatch(
  jobsSource,
  /selectedComponentSummary|selectedHost\s*=\s*ref|retryHostJob\(/,
  'deployment list should not retain the obsolete host-history modal state'
)
assert.match(
  hostDeploymentSource,
  /getJobHostSummaries\([\s\S]*getJob\(/,
  'host status workspace should combine the host summary with full task details'
)
assert.match(
  hostDeploymentSource,
  /retryJob\([\s\S]*host_id:/,
  'host status workspace should retry only the selected host'
)
assert.match(
  hostDeploymentSource,
  /currentStatusTab[\s\S]*executionHistoryTab[\s\S]*executionDetailTab/,
  'host status workspace should separate current status, history, and execution detail'
)
assert.doesNotMatch(
  hostDeploymentSource,
  /adminPages\.monitoring\.attemptOption|attemptNumber\(/,
  'host status workspace should identify records by task, status, and time instead of ordinal attempts'
)
assert.match(
  hostDeploymentSource,
  /function formatExecutionOption\(attempt\)[\s\S]*taskTypeLabel\(attempt\.component\)[\s\S]*statusLabel[\s\S]*formatDateTime/,
  'execution selectors should present task type, status, and execution time'
)
assert.doesNotMatch(
  hostDeploymentSource,
  /deployment-component-switch|deployment-status-band/,
  'current status should not split components into separate workspaces'
)
assert.doesNotMatch(
  hostCurrentStatusSource,
  /adminPages\.monitoring\.(executionProgress|taskInfo|jobNumber)/,
  'current status should not foreground task execution details'
)
assert.match(
  hostDeploymentSource,
  /adminPages\.monitoring\.installedComponents[\s\S]*adminPages\.monitoring\.enabledCapabilities/,
  'current status should show installed components and enabled capabilities'
)
assert.match(
  hostDeploymentSource,
  /component_statuses[\s\S]*componentJobs/,
  'component overview should combine runtime status with the latest component configuration'
)
assert.match(
  hostDeploymentSource,
  /const allHistory\s*=\s*computed[\s\S]*componentOptions[\s\S]*flatMap/,
  'execution history should merge records across all host components'
)
assert.match(
  hostDeploymentSource,
  /adminPages\.monitoring\.taskType[\s\S]*function taskTypeLabel[\s\S]*componentLabel/,
  'execution history should identify the component installation type instead of a task number'
)
assert.equal(
  localeSources.zhCN.adminPages.monitoring.allTaskTypes,
  '全部任务类型',
  'the history task filter should describe all task types clearly'
)
assert.match(
  hostDeploymentSource,
  /historyComponentFilter[\s\S]*adminPages\.monitoring\.allTaskTypes[\s\S]*componentOptions/,
  'execution history should offer a task type filter for each deployable component'
)
assert.match(
  hostDeploymentSource,
  /const filteredHistory = computed[\s\S]*historyComponentFilter\.value[\s\S]*attempt\.component === historyComponentFilter\.value[\s\S]*historyStatusFilter\.value/,
  'task type and status filters should apply together to execution history'
)
assert.doesNotMatch(
  hostDeploymentSource,
  /adminPages\.monitoring\.installationLogsTab/,
  'raw installation logs should not remain a primary workspace tab'
)
assert.match(
  hostDeploymentSource,
  /adminPages\.monitoring\.returnToExecutionHistory[\s\S]*adminPages\.monitoring\.executionProgress[\s\S]*progressStages/,
  'execution detail should provide a return path and show the selected task process'
)
assert.match(
  hostDeploymentSource,
  /const currentProgressStep = computed[\s\S]*jobFailureReason\(selectedJob\.value\)\.startsWith\('ssh_'\)[\s\S]*selectedJob\.value\?\.progress\?\.current/,
  'SSH failures should stop at host connection even when a stale backend progress value is present'
)
assert.match(
  hostDeploymentSource,
  /function progressStepMarker\(index\)[\s\S]*!detailFailed\.value[\s\S]*currentProgressStep\.value[\s\S]*'✓'/,
  'successful execution details should mark the final stage as completed'
)
assert.match(
  hostDeploymentSource,
  /@media \(max-width: 720px\)[\s\S]*\.execution-progress \{[\s\S]*grid-template-columns:\s*1fr/,
  'mobile execution details should show the full process as a vertical timeline'
)
assert.doesNotMatch(
  hostDeploymentSource,
  /\.execution-progress \{\s*min-width:\s*34rem/,
  'mobile execution progress should not require horizontal scrolling'
)
assert.match(
  hostDeploymentSource,
  /adminPages\.monitoring\.failureDiagnosis[\s\S]*jobFailureSummary[\s\S]*deployment-log-block/,
  'execution detail should combine failure diagnosis with the full log'
)
assert.match(
  hostDeploymentSource,
  /adminPages\.monitoring\.deploymentCapabilities[\s\S]*selectedJobCapabilities[\s\S]*componentCapabilities\(\s*selectedAttempt\.value\.component,\s*selectedJob\.value\s*\)/,
  'execution detail should show the capabilities configured by the selected task'
)
assert.equal(
  localeSources.zhCN.adminPages.monitoring.deploymentCapabilities,
  '本次部署能力',
  'capability details should describe the selected deployment without implying a failed task was installed'
)
assert.equal(
  localeSources.zhCN.adminPages.monitoring.adjustCapabilities,
  '调整能力',
  'Categraf capability changes should use a clear action label'
)
assert.match(
  hostDeploymentSource,
  /adminPages\.monitoring\.adjustCapabilities[\s\S]*openCapabilityAdjustment/,
  'current and detail views should expose a Categraf capability adjustment action'
)
assert.match(
  hostDeploymentSource,
  /function openCapabilityAdjustment\(\)[\s\S]*path:\s*'\/management\/monitoring\/assets'[\s\S]*adjust:\s*'categraf'[\s\S]*host:\s*String\(hostId\.value\)[\s\S]*baseJob:[\s\S]*profiles:/,
  'capability adjustment should reuse the host deployment wizard with the current host, baseline job, and profiles'
)
assert.match(
  assetsSource,
  /useRoute\(\)[\s\S]*route\.query\.adjust !== 'categraf'[\s\S]*selectedHostIds\.value = \[host\.id\][\s\S]*initialCategrafProfiles\.value = existingProfiles[\s\S]*categrafForm\.profiles = \[\.\.\.existingProfiles\][\s\S]*categrafStep\.value = 1[\s\S]*showCategrafForm\.value = true/,
  'the deployment wizard should open on capability selection with the host and existing profiles prefilled'
)
assert.match(
  assetsSource,
  /:disabled="\s*capabilityAdjustmentMode &&\s*initialCategrafProfiles\.includes\(profile\.id\)\s*"/,
  'existing capabilities should remain selected and locked during additive adjustment'
)
assert.match(
  assetsSource,
  /newCategrafProfiles[\s\S]*adminPages\.monitoring\.newCapability[\s\S]*adminPages\.monitoring\.dispatchCapabilityUpdate/,
  'the adjustment wizard should distinguish additions and dispatch them as an update'
)
assert.match(
  assetsSource,
  /capabilityBaseJobId[\s\S]*base_job_id:[\s\S]*capabilityBaseJobId\.value/,
  'capability updates should let the backend inherit protected parameters from the active job'
)
assert.match(
  assetsSource,
  /newCapabilityParamsValid[\s\S]*newCapabilityParamsRequired[\s\S]*safeCapabilityUpdateNotice[\s\S]*deploymentSettingsInherited/,
  'capability updates should validate new parameters and explain inherited settings and rollback protection'
)
assert.match(
  assetsSource,
  /deploymentSettingsBaseline[\s\S]*deploymentSettingChanges[\s\S]*resetDeploymentSettings/,
  'capability updates should track editable deployment settings and allow restoring the successful baseline'
)
assert.match(
  assetsSource,
  /deploymentSettingsTitle[\s\S]*deploymentSettingStatus[\s\S]*deploymentSettingsChangeSummary/,
  'the adjustment wizard should show deployment setting inheritance and changes before dispatch'
)
assert.match(
  hostDeploymentSource,
  /runtime\?\.active_job_id \|\|[\s\S]*latest\?\.job_id/,
  'current component capabilities should come from the last successful job before the latest attempt'
)
assert.match(
  hostDeploymentSource,
  /adminPages\.monitoring\.viewDetails[\s\S]*selectAttempt\(attempt\)/,
  'execution history should open the selected record as execution detail'
)
assert.doesNotMatch(
  hostDeploymentSource,
  /adminPages\.monitoring\.(executionRelationship|independentExecution)|#\{\{|`#\$\{/,
  'execution history should omit internal retry relationships and hash-prefixed task IDs'
)
assert.match(
  `${jobsSource}\n${hostDeploymentSource}`,
  /adminPages\.monitoring\.taskReference/,
  'deployment views should use a localized task reference label'
)
assert.match(
  hostDeploymentSource,
  /navigator\.clipboard\?\.writeText[\s\S]*document\.execCommand\('copy'\)/,
  'host status workspace should copy logs on non-secure internal origins without crashing the page'
)
assert.match(
  jobsSource,
  /DeploymentResources/,
  'deployment management should embed installation resources as a page tab'
)
assert.match(
  jobsSource,
  /route\.query\.view\s*===\s*'resources'/,
  'deployment management should derive the selected tab from the URL'
)
assert.match(
  jobsSource,
  /view:\s*view\s*===\s*'resources'\s*\?\s*'resources'\s*:\s*undefined/,
  'deployment management should keep resource tab navigation shareable'
)
assert.doesNotMatch(
  jobsSource,
  /<tr v-for="job in filteredJobs"/,
  'jobs page should not render every execution as a top-level table row'
)
assert.deepEqual(
  normalizeHostSummaries({
    results: [{ host_id: 7, hostname: 'legacy-host' }]
  }),
  [
    {
      host_id: 7,
      hostname: 'legacy-host',
      address: '',
      components: {
        categraf: { latest: null, attempt_count: 0, history: [] },
        blackbox: { latest: null, attempt_count: 0, history: [] }
      }
    }
  ],
  'jobs page should safely normalize legacy host summaries without component data'
)
assert.deepEqual(
  normalizeHostSummaries({ detail: 'temporarily unavailable' }),
  [],
  'jobs page should reject malformed non-list host summary payloads'
)

{
  const logElement = {
    scrollHeight: 320,
    scrollTop: 200,
    clientHeight: 100
  }
  let mountedElement = logElement

  await assert.doesNotReject(
    keepLogPinnedAfterRender({
      element: logElement,
      getCurrentElement: () => mountedElement,
      nextRender: async () => {
        mountedElement = null
      }
    }),
    'closing job details from the log tab must not access an unmounted log element'
  )
  assert.equal(
    logElement.scrollTop,
    200,
    'an unmounted log element should not be mutated after the render boundary'
  )

  mountedElement = logElement
  await keepLogPinnedAfterRender({
    element: logElement,
    getCurrentElement: () => mountedElement,
    nextRender: async () => {}
  })
  assert.equal(
    logElement.scrollTop,
    logElement.scrollHeight,
    'a mounted log element near the bottom should remain pinned after rendering'
  )
}

assert.match(
  jobsSource,
  /jobFailureSummary\(job\)/,
  'job list should render a concise translated failure summary'
)
assert.doesNotMatch(
  jobsSource,
  /\{\{\s*job\.last_error\s*\|\|/,
  'job list should keep raw Ansible output in the detail log instead of the table'
)

for (const [name, source] of [
  ['overview', overviewSource],
  ['installers', installersSource],
  ['probes', probesSource],
  ['probeSettings', probeSettingsSource],
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
  for (const match of source.matchAll(
    /adminPages\.monitoring\.([A-Za-z0-9_]+)/g
  )) {
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
