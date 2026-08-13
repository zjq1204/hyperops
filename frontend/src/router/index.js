import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '@/store/user'
import { adminRoutes } from '@/admin/routes'
import {
  getLandingPath,
  hasFeature,
  hasOperationPermission
} from '@/utils/platformAccess'

const routes = [
  {
    path: '/',
    redirect: '/dashboard'
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/pages/Auth.vue'),
    meta: { requiresGuest: true }
  },
  // Dashboard
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('@/pages/Dashboard.vue'),
    meta: { requiresAuth: true, requiredFeature: 'workspace_dashboard' }
  },
  // Jenkins module - user workspace
  {
    path: '/jenkins',
    redirect: '/jenkins/workspace'
  },
  {
    path: '/jenkins/workspace',
    name: 'JenkinsWorkspace',
    component: () => import('@/pages/Jenkins/Workspace.vue'),
    meta: { requiresAuth: true, requiredFeature: 'workspace_jenkins' }
  },
  {
    path: '/jenkins/records',
    name: 'JenkinsRecords',
    component: () => import('@/pages/Jenkins/Records.vue'),
    meta: { requiresAuth: true, requiredFeature: 'workspace_jenkins' }
  },
  {
    path: '/jenkins/settings',
    redirect: '/jenkins/workspace'
  },
  {
    path: '/actions',
    redirect: '/actions/workspace'
  },
  {
    path: '/actions/workspace',
    name: 'ActionWorkspace',
    component: () => import('@/pages/Actions/Workspace.vue'),
    meta: { requiresAuth: true, requiredFeature: 'workspace_actions' }
  },
  {
    path: '/actions/runs',
    name: 'ActionRuns',
    component: () => import('@/pages/Actions/Runs.vue'),
    meta: { requiresAuth: true, requiredFeature: 'workspace_actions' }
  },
  // Settings
  {
    path: '/settings',
    redirect: '/settings/profile'
  },
  {
    path: '/settings/profile',
    name: 'SettingsProfile',
    component: () => import('@/pages/settings/Profile.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/auth/oauth/callback',
    name: 'OAuthCallback',
    component: () => import('@/pages/OAuthCallback.vue'),
    meta: { requiresGuest: true }
  },
  ...adminRoutes,
  {
    path: '/404',
    name: 'NotFound',
    component: () => import('@/pages/NotFound.vue')
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'CatchAll',
    component: () => import('@/pages/NotFound.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior() {
    return { top: 0 }
  }
})

// Navigation guards
let platformFlagsPromise = null
const ensurePlatformFlagsLoaded = (userStore) => {
  if (!platformFlagsPromise) {
    platformFlagsPromise = userStore.loadPlatformFlags().catch(() => null)
  }
  return platformFlagsPromise
}

router.beforeEach(async (to, from, next) => {
  const userStore = useUserStore()

  // Lazily hydrate platform flags for any authenticated navigation.
  if (to.meta.requiresAuth || to.meta.requiresModuleFlag) {
    if (userStore.token) {
      await ensurePlatformFlagsLoaded(userStore)
    }
  }

  if (to.meta.requiresAuth) {
    const hasToken = !!localStorage.getItem('access_token')

    if (!hasToken) {
      next({ name: 'Login', query: { redirect: to.fullPath } })
      return
    }

    if (!userStore.user) {
      try {
        const authSuccess = await userStore.checkAuth()
        if (!authSuccess) {
          next({ name: 'Login', query: { redirect: to.fullPath } })
          return
        }
      } catch {
        next({ name: 'Login', query: { redirect: to.fullPath } })
        return
      }
    }

    const currentUser = userStore.userInfo || userStore.user
    if (
      to.meta.requiredFeature &&
      !hasFeature(currentUser, to.meta.requiredFeature)
    ) {
      next(getLandingPath(currentUser))
      return
    }

    if (
      to.meta.requiredOperationPermission &&
      !hasOperationPermission(
        currentUser,
        to.meta.requiredOperationPermission
      )
    ) {
      next(getLandingPath(currentUser))
      return
    }

    if (to.meta.requiresModuleFlag && !userStore.hasModuleFlag(to.meta.requiresModuleFlag)) {
      next(getLandingPath(currentUser))
      return
    }

    next()
  } else if (to.meta.requiresGuest && userStore.isAuthenticated) {
    next(getLandingPath(userStore.userInfo))
  } else {
    next()
  }
})

export default router
