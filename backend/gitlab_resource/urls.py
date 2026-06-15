"""
GitLab Resource URL configuration.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    GitLabBranchViewSet,
    GitLabCollectionRecordViewSet,
    GitLabInstanceViewSet,
    GitLabOperationRecordViewSet,
    GitLabProjectLabelViewSet,
    GitLabTagViewSet,
    GitLabWebhookViewSet,
    RegisteredGroupViewSet,
    RegisteredProjectViewSet,
)

router = DefaultRouter()
router.register(r"instances", GitLabInstanceViewSet, basename="gitlab-instance")
router.register(r"groups", RegisteredGroupViewSet, basename="gitlab-group")
router.register(r"projects", RegisteredProjectViewSet, basename="gitlab-project")
router.register(r"project-labels", GitLabProjectLabelViewSet, basename="gitlab-project-label")
router.register(r"collection-records", GitLabCollectionRecordViewSet, basename="gitlab-collection-record")
router.register(r"operation-records", GitLabOperationRecordViewSet, basename="gitlab-operation-record")
router.register(r"branches", GitLabBranchViewSet, basename="gitlab-branch")
router.register(r"tags", GitLabTagViewSet, basename="gitlab-tag")
router.register(r"webhooks", GitLabWebhookViewSet, basename="gitlab-webhook")

urlpatterns = [
    path("", include(router.urls)),
]
