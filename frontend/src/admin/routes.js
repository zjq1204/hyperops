/**
 * Admin (management) routes. Mount with ...adminRoutes in the main router (before 404/catch-all).
 */
export const adminRoutes = [
  {
    path: '/management',
    redirect: '/management/users'
  },
  // User Management
  {
    path: '/management/users',
    name: 'AdminUsers',
    component: () => import('@/admin/pages/Management/Users.vue'),
    meta: { requiresAuth: true, requiredFeature: 'admin_users' }
  },
  {
    path: '/management/groups',
    name: 'AdminGroups',
    component: () => import('@/admin/pages/Management/Groups.vue'),
    meta: { requiresAuth: true, requiredFeature: 'admin_users' }
  },
  {
    path: '/management/roles',
    name: 'AdminRoles',
    component: () => import('@/admin/pages/Management/Roles.vue'),
    meta: { requiresAuth: true, requiredFeature: 'admin_users' }
  },
  {
    path: '/management/ldap',
    name: 'AdminLdap',
    component: () => import('@/admin/pages/Management/Ldap.vue'),
    meta: { requiresAuth: true, requiredFeature: 'admin_users' }
  },
  // Jenkins Admin
  {
    path: '/management/jenkins',
    redirect: '/management/jenkins/instances'
  },
  {
    path: '/management/jenkins/instances',
    name: 'AdminJenkinsInstances',
    component: () => import('@/admin/pages/Jenkins/Instances.vue'),
    meta: { requiresAuth: true, requiredFeature: 'admin_jenkins' }
  },
  {
    path: '/management/jenkins/jobs',
    name: 'AdminJenkinsJobs',
    component: () => import('@/admin/pages/Jenkins/Jobs.vue'),
    meta: { requiresAuth: true, requiredFeature: 'admin_jenkins' }
  },
  {
    path: '/management/jenkins/entries',
    name: 'AdminJenkinsEntries',
    component: () => import('@/admin/pages/Jenkins/Entries.vue'),
    meta: { requiresAuth: true, requiredFeature: 'admin_jenkins' }
  },
  // GitLab Admin
  {
    path: '/management/gitlab',
    redirect: '/management/gitlab/instances'
  },
  {
    path: '/management/gitlab/instances',
    name: 'AdminGitLabInstances',
    component: () => import('@/admin/pages/GitLab/Instances.vue'),
    meta: { requiresAuth: true, requiredFeature: 'admin_gitlab' }
  },
  {
    path: '/management/gitlab/groups',
    name: 'AdminGitLabGroups',
    component: () => import('@/admin/pages/GitLab/Groups.vue'),
    meta: { requiresAuth: true, requiredFeature: 'admin_gitlab' }
  },
  {
    path: '/management/gitlab/projects',
    name: 'AdminGitLabProjects',
    component: () => import('@/admin/pages/GitLab/Projects.vue'),
    meta: { requiresAuth: true, requiredFeature: 'admin_gitlab' }
  },
  {
    path: '/management/gitlab/branches',
    name: 'AdminGitLabBranches',
    component: () => import('@/admin/pages/GitLab/Branches.vue'),
    meta: { requiresAuth: true, requiredFeature: 'admin_gitlab' }
  },
  {
    path: '/management/gitlab/tags',
    name: 'AdminGitLabTags',
    component: () => import('@/admin/pages/GitLab/Tags.vue'),
    meta: { requiresAuth: true, requiredFeature: 'admin_gitlab' }
  },
  {
    path: '/management/gitlab/webhooks',
    name: 'AdminGitLabWebhooks',
    component: () => import('@/admin/pages/GitLab/Webhooks.vue'),
    meta: { requiresAuth: true, requiredFeature: 'admin_gitlab' }
  },
  {
    path: '/management/gitlab/operation-records',
    name: 'AdminGitLabOperationRecords',
    component: () => import('@/admin/pages/GitLab/OperationRecords.vue'),
    meta: { requiresAuth: true, requiredFeature: 'admin_gitlab' }
  },
  // Notification Admin
  {
    path: '/management/notifier',
    redirect: '/management/notifier/stats'
  },
  {
    path: '/management/notifier/stats',
    name: 'AdminNotificationsStats',
    component: () => import('@/admin/pages/Notifications/Stats.vue'),
    meta: {
      requiresAuth: true,
      requiredFeature: 'admin_notifications',
      requiresModuleFlag: 'enable_notifier'
    }
  },
  {
    path: '/management/notifier/records',
    name: 'AdminNotificationsRecords',
    component: () => import('@/admin/pages/Notifications/Records.vue'),
    meta: {
      requiresAuth: true,
      requiredFeature: 'admin_notifications',
      requiresModuleFlag: 'enable_notifier'
    }
  },
  {
    path: '/management/notifier/channels',
    name: 'AdminNotificationsChannels',
    component: () => import('@/admin/pages/Notifications/Channels.vue'),
    meta: {
      requiresAuth: true,
      requiredFeature: 'admin_notifications',
      requiresModuleFlag: 'enable_notifier'
    }
  },
  {
    path: '/management/notifier/settings',
    name: 'AdminNotificationsSettings',
    component: () => import('@/admin/pages/Notifications/Config.vue'),
    meta: {
      requiresAuth: true,
      requiredFeature: 'admin_notifications',
      requiresModuleFlag: 'enable_notifier'
    }
  },
  // Action Orchestration Admin
  {
    path: '/management/actions',
    redirect: '/management/actions/templates'
  },
  {
    path: '/management/actions/templates',
    name: 'AdminActionTemplates',
    component: () => import('@/admin/pages/Actions/Templates.vue'),
    meta: { requiresAuth: true, requiredFeature: 'admin_actions' }
  },
  // Monitoring Stack Admin
  {
    path: '/management/monitoring',
    redirect: '/management/monitoring/overview'
  },
  {
    path: '/management/monitoring/overview',
    name: 'AdminMonitoringOverview',
    component: () => import('@/admin/pages/Monitoring/Overview.vue'),
    meta: {
      requiresAuth: true,
      requiredFeature: 'admin_monitoring',
      requiresModuleFlag: 'enable_monitoring'
    }
  },
  {
    path: '/management/monitoring/installers',
    redirect: () => ({
      path: '/management/monitoring/jobs',
      query: { view: 'resources' }
    })
  },
  {
    path: '/management/monitoring/probes',
    name: 'AdminMonitoringProbes',
    component: () => import('@/admin/pages/Monitoring/Probes.vue'),
    meta: {
      requiresAuth: true,
      requiredFeature: 'admin_monitoring',
      requiresModuleFlag: 'enable_monitoring'
    }
  },
  {
    path: '/management/monitoring/probes/nodes',
    name: 'AdminMonitoringProbeNodes',
    component: () => import('@/admin/pages/Monitoring/ProbeSettings.vue'),
    meta: {
      requiresAuth: true,
      requiredFeature: 'admin_monitoring',
      requiresModuleFlag: 'enable_monitoring'
    }
  },
  {
    path: '/management/monitoring/probes/settings',
    name: 'AdminMonitoringProbeSettings',
    component: () => import('@/admin/pages/Monitoring/ProbeSettings.vue'),
    meta: {
      requiresAuth: true,
      requiredFeature: 'admin_monitoring',
      requiresModuleFlag: 'enable_monitoring'
    }
  },
  {
    path: '/management/monitoring/blackbox',
    name: 'AdminMonitoringBlackbox',
    component: () => import('@/admin/pages/Monitoring/BlackboxInstances.vue'),
    meta: {
      requiresAuth: true,
      requiredFeature: 'admin_monitoring',
      requiresModuleFlag: 'enable_monitoring'
    }
  },
  {
    path: '/management/monitoring/assets',
    name: 'AdminMonitoringAssets',
    component: () => import('@/admin/pages/Monitoring/Assets.vue'),
    meta: {
      requiresAuth: true,
      requiredFeature: 'admin_monitoring',
      requiresModuleFlag: 'enable_monitoring'
    }
  },
  {
    path: '/management/monitoring/credentials',
    name: 'AdminMonitoringCredentials',
    component: () => import('@/admin/pages/Monitoring/Credentials.vue'),
    meta: {
      requiresAuth: true,
      requiredFeature: 'admin_monitoring',
      requiresModuleFlag: 'enable_monitoring',
      requiredOperationPermission: 'monitoring_credentials_view'
    }
  },
  {
    path: '/management/monitoring/rules',
    name: 'AdminMonitoringRules',
    component: () => import('@/admin/pages/Monitoring/Rules.vue'),
    meta: {
      requiresAuth: true,
      requiredFeature: 'admin_monitoring',
      requiresModuleFlag: 'enable_monitoring'
    }
  },
  {
    path: '/management/monitoring/rules/:templateName',
    name: 'AdminMonitoringRuleDetail',
    component: () => import('@/admin/pages/Monitoring/RuleDetail.vue'),
    meta: {
      requiresAuth: true,
      requiredFeature: 'admin_monitoring',
      requiresModuleFlag: 'enable_monitoring'
    }
  },
  {
    path: '/management/monitoring/jobs',
    name: 'AdminMonitoringJobs',
    component: () => import('@/admin/pages/Monitoring/Jobs.vue'),
    meta: {
      requiresAuth: true,
      requiredFeature: 'admin_monitoring',
      requiresModuleFlag: 'enable_monitoring'
    }
  },
  {
    path: '/management/monitoring/jobs/hosts/:hostId',
    name: 'AdminMonitoringHostDeploymentStatus',
    component: () =>
      import('@/admin/pages/Monitoring/HostDeploymentStatus.vue'),
    meta: {
      requiresAuth: true,
      requiredFeature: 'admin_monitoring',
      requiresModuleFlag: 'enable_monitoring'
    }
  },
  {
    path: '/management/monitoring/settings',
    name: 'AdminMonitoringSettings',
    component: () => import('@/admin/pages/Monitoring/Settings.vue'),
    meta: {
      requiresAuth: true,
      requiredFeature: 'admin_monitoring',
      requiresModuleFlag: 'enable_monitoring'
    }
  }
]
