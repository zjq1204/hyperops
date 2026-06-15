from django.urls import path
from rest_framework.routers import DefaultRouter

from action_orchestration.views import (
    ActionRunViewSet,
    AdminActionTemplateViewSet,
    WorkspaceActionTemplateView,
)

router = DefaultRouter()
router.register(r"templates", AdminActionTemplateViewSet, basename="action-template")
router.register(r"runs", ActionRunViewSet, basename="action-run")

urlpatterns = [
    path(
        "workspace/templates/",
        WorkspaceActionTemplateView.as_view(),
        name="workspace-action-templates",
    ),
]
urlpatterns += router.urls
