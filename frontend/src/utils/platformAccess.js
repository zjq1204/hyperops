export const FEATURE_DEFINITIONS = [
  {
    key: 'workspace_dashboard',
    label: '工作台首页',
    defaultPath: '/dashboard',
    platform: 'workspace',
    parentKey: 'workspace'
  },
  {
    key: 'workspace_jenkins',
    label: 'Jenkins 工作台',
    defaultPath: '/jenkins/workspace',
    platform: 'workspace',
    parentKey: 'workspace'
  },
  {
    key: 'workspace_actions',
    label: '动作编排',
    defaultPath: '/actions/workspace',
    platform: 'workspace',
    parentKey: 'workspace'
  },
  {
    key: 'admin_users',
    label: '用户管理',
    defaultPath: '/management/users',
    platform: 'admin_console',
    parentKey: 'admin_console'
  },
  {
    key: 'admin_jenkins',
    label: 'Jenkins 管理',
    defaultPath: '/management/jenkins/instances',
    platform: 'admin_console',
    parentKey: 'admin_console'
  },
  {
    key: 'admin_gitlab',
    label: 'GitLab 管理',
    defaultPath: '/management/gitlab/instances',
    platform: 'admin_console',
    parentKey: 'admin_console'
  },
  {
    key: 'admin_notifications',
    label: '通知管理',
    defaultPath: '/management/notifier/stats',
    platform: 'admin_console',
    parentKey: 'admin_console'
  },
  {
    key: 'admin_actions',
    label: '动作编排管理',
    defaultPath: '/management/actions/templates',
    platform: 'admin_console',
    parentKey: 'admin_console'
  },
  {
    key: 'admin_monitoring',
    label: '监控接入控制台',
    defaultPath: '/management/monitoring/overview',
    platform: 'admin_console',
    parentKey: 'admin_console'
  }
]

export const PLATFORM_DEFINITIONS = [
  {
    key: 'workspace',
    labelKey: 'platforms.workspace',
    defaultPath: '/dashboard',
    matchers: ['/dashboard', '/jenkins', '/actions']
  },
  {
    key: 'admin_console',
    labelKey: 'platforms.adminConsole',
    defaultPath: '/management/users',
    matchers: ['/management']
  }
]

export const FEATURE_KEY_SET = new Set(
  FEATURE_DEFINITIONS.map((item) => item.key)
)
export const PLATFORM_KEY_SET = new Set(
  PLATFORM_DEFINITIONS.map((item) => item.key)
)

const FEATURE_MAP = new Map(FEATURE_DEFINITIONS.map((item) => [item.key, item]))
const PLATFORM_MAP = new Map(PLATFORM_DEFINITIONS.map((item) => [item.key, item]))

const FEATURE_ALIASES = {
  workspace: ['workspace_dashboard', 'workspace_jenkins', 'workspace_actions'],
  admin_console: [
    'admin_users',
    'admin_jenkins',
    'admin_gitlab',
    'admin_notifications',
    'admin_actions',
    'admin_monitoring'
  ],
  jenkins: ['workspace_dashboard', 'workspace_jenkins'],
  gitlab: ['workspace_dashboard', 'workspace_jenkins'],
  cloud_billing: ['workspace_dashboard', 'workspace_jenkins'],
  data_collector: ['workspace_dashboard', 'workspace_jenkins'],
  operations_console: ['workspace_dashboard', 'workspace_jenkins'],
  hyperbdr_dashboard: ['workspace_dashboard', 'workspace_jenkins'],
  ai_model_pricing: ['workspace_dashboard', 'workspace_jenkins'],
  ai_pricehub: ['workspace_dashboard', 'workspace_jenkins'],
  jenkins_admin: [
    'admin_users',
    'admin_jenkins',
    'admin_gitlab',
    'admin_notifications',
    'admin_actions',
    'admin_monitoring'
  ],
  gitlab_admin: [
    'admin_users',
    'admin_jenkins',
    'admin_gitlab',
    'admin_notifications',
    'admin_actions',
    'admin_monitoring'
  ],
  llm_console: [
    'admin_users',
    'admin_jenkins',
    'admin_gitlab',
    'admin_notifications',
    'admin_actions',
    'admin_monitoring'
  ],
  task_management_console: [
    'admin_users',
    'admin_jenkins',
    'admin_gitlab',
    'admin_notifications',
    'admin_actions',
    'admin_monitoring'
  ],
  notification_console: [
    'admin_users',
    'admin_jenkins',
    'admin_gitlab',
    'admin_notifications',
    'admin_actions',
    'admin_monitoring'
  ]
}

function expandFeatureKey(value) {
  const resolved = FEATURE_ALIASES[value] || value
  return Array.isArray(resolved) ? resolved : [resolved]
}

export function normalizeFeatureKeys(values) {
  if (!Array.isArray(values)) return []

  const seen = new Set()
  return FEATURE_DEFINITIONS.map((item) => item.key).filter((key) => {
    const matches = values.some((value) => {
      const normalized = expandFeatureKey(value)
      return normalized.includes(key)
    })
    return matches && !seen.has(key) && seen.add(key)
  })
}

export function normalizePlatformKey(value) {
  if (PLATFORM_KEY_SET.has(value)) return value
  const matchedFeature = expandFeatureKey(value).find((key) =>
    FEATURE_KEY_SET.has(key)
  )
  return FEATURE_MAP.get(matchedFeature)?.platform || ''
}

export function getAccessProfile(user) {
  return (
    user?.access_profile || {
      visible_features: [],
      available_platforms: [],
      preferred_platform: '',
      landing_path: '/dashboard'
    }
  )
}

export function hasFeature(user, featureKey) {
  const normalizedFeatureKeys = expandFeatureKey(featureKey)
  const visibleFeatures = normalizeFeatureKeys(
    getAccessProfile(user).visible_features
  )
  return normalizedFeatureKeys.some((key) => visibleFeatures.includes(key))
}

export function getAvailablePlatforms(user, t) {
  const accessProfile = getAccessProfile(user)
  const platformMap = new Map(
    (accessProfile.available_platforms || []).map((item) => [item.key, item])
  )

  return PLATFORM_DEFINITIONS.filter((item) => platformMap.has(item.key)).map(
    (item) => {
      const resolved = platformMap.get(item.key)
      return {
        key: item.key,
        label: t ? t(item.labelKey) : item.key,
        defaultPath: resolved?.default_path || item.defaultPath
      }
    }
  )
}

export function getLandingPath(user) {
  return getAccessProfile(user).landing_path || '/dashboard'
}

export function getCurrentPlatformKey(path) {
  const matched = PLATFORM_DEFINITIONS.find((item) =>
    item.matchers.some((matcher) => path.startsWith(matcher))
  )
  return matched?.key || 'workspace'
}

export function getPlatformByKey(platformKey, t) {
  const definition = PLATFORM_MAP.get(platformKey)
  if (!definition) return null
  return {
    key: definition.key,
    label: t ? t(definition.labelKey) : definition.key,
    defaultPath: definition.defaultPath
  }
}
