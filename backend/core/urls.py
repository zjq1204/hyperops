from django.contrib import admin
from core import views as core_views
from django.conf import settings
from django.http import JsonResponse
from django.urls import path, include

from accounts.views import OAuthCallbackRedirectView
from .swagger import schema_view, swagger_view, redoc_view

# Define project URL routing configuration
urlpatterns = [
    # Health check endpoint
    # Used by Docker/Kubernetes for container health monitoring
    # Returns a simple 'OK' response to indicate the application is running
    path('health', lambda _: JsonResponse({'health': 'OK'}, status=200)),

    # API Schema endpoint
    # Provides the OpenAPI schema in JSON format
    path('api/schema', schema_view, name='schema'),

    # Swagger UI documentation route
    # Displays the API documentation using Swagger UI.
    path('swagger', swagger_view, name='swagger-ui'),

    # ReDoc documentation route
    # Displays the API documentation using ReDoc.
    path('redoc', redoc_view, name='redoc'),

    # Django admin site route
    # Provides access to the Django Admin interface for managing models and
    # data.
    path('admin', admin.site.urls),

    # Authentication routes
    # Includes authentication endpoints provided by custom accounts.urls
    path('', include('accounts.urls')),

    # Jenkins Trigger routes
    path('api/v1/jenkins/', include('jenkins_trigger.urls')),

    # GitLab Resource routes
    path('api/v1/gitlab/', include('gitlab_resource.urls')),

    # Action orchestration routes
    path('api/v1/actions/', include('action_orchestration.urls')),

    # Custom OAuth callback redirect with JWT tokens
    # This must come BEFORE allauth.urls to intercept the redirect
    path(
        'accounts/oauth/callback/',
        OAuthCallbackRedirectView.as_view(),
        name='oauth_callback_redirect'
    ),

    # Django-allauth OAuth callback routes
    # Required for OAuth provider callbacks (e.g., Google)
    # Even with Headless API, these endpoints are needed for OAuth handshake
    path('accounts/', include('allauth.urls')),

    # Django-allauth Headless API endpoints
    # REST API for frontend-backend separation (allauth >= 65.0.0)
    # Provides authentication APIs without Django form views
    path('_allauth/', include('allauth.headless.urls')),
]

if settings.ENABLE_AGENTCORE_TASK:
    urlpatterns.append(
        path('api/v1/tasks/', include('agentcore_task.adapters.django.urls'))
    )

if settings.ENABLE_NOTIFIER:
    urlpatterns.append(
        path(
            'api/v1/admin/notifications/',
            include('agentcore_notifier.adapters.django.urls')
        )
    )

if settings.ENABLE_AGENTCORE_METERING:
    urlpatterns.append(
        path('api/v1/admin/', include('agentcore_metering.adapters.django.urls'))
    )

if getattr(settings, 'ENABLE_MONITORING', True):
    urlpatterns.append(
        path('api/v1/monitoring/', include('monitoring_stack.urls'))
    )

# SPA bootstrap meta (feature flags). Authenticated only.
urlpatterns.append(
    path('api/v1/meta/', core_views.PlatformMetaView.as_view(), name='platform_meta')
)
