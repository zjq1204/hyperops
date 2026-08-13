from django.urls import path
from monitoring_stack.views import (
    AnsibleInstallJobViewSet,
    AnsiblePreviewView,
    AssetsReconciliationView,
    BlackboxProbeNodeViewSet,
    BlackboxInstancesView,
    InstallerAssetsView,
    InstallerBuildView,
    InstallerDownloadView,
    MonitoringConfigView,
    MonitoringGovernanceFindingResolveView,
    MonitoringGovernanceFindingView,
    MonitoringGovernanceOverviewView,
    MonitoringGovernanceSyncView,
    MonitoringHostViewSet,
    MonitoringProfileViewSet,
    MonitoringCredentialViewSet,
    MonitoringSshKeyCompatibilityViewSet,
    N9eDiscoverView,
    N9eImportRulesView,
    N9ePlatformSummaryView,
    PrometheusHttpSdConfigView,
    PrometheusHttpSdTokenView,
    PrometheusProbeNodeDiscoveryView,
    PrometheusProbeNodeOnboardView,
    ProbeTargetViewSet,
    PrometheusHttpSdView,
    PrometheusTargetsSummaryView,
    RuleDiffView,
    RulesView,
)
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r"profiles", MonitoringProfileViewSet, basename="monitoring-profile")
router.register(
    r"probe-targets", ProbeTargetViewSet, basename="monitoring-probe-target"
)
router.register(r"probe-nodes", BlackboxProbeNodeViewSet, basename="monitoring-probe-node")
router.register(r"hosts", MonitoringHostViewSet, basename="monitoring-host")
router.register(r"credentials", MonitoringCredentialViewSet, basename="monitoring-credential")
router.register(r"ssh-keys", MonitoringSshKeyCompatibilityViewSet, basename="monitoring-ssh-key")
router.register(
    r"ansible/jobs", AnsibleInstallJobViewSet, basename="monitoring-ansible-job"
)

urlpatterns = [
    path("config/", MonitoringConfigView.as_view(), name="monitoring-config"),
    path(
        "governance/sync/",
        MonitoringGovernanceSyncView.as_view(),
        name="monitoring-governance-sync",
    ),
    path(
        "governance/overview/",
        MonitoringGovernanceOverviewView.as_view(),
        name="monitoring-governance-overview",
    ),
    path(
        "governance/findings/",
        MonitoringGovernanceFindingView.as_view(),
        name="monitoring-governance-findings",
    ),
    path(
        "governance/findings/<int:finding_id>/resolve/",
        MonitoringGovernanceFindingResolveView.as_view(),
        name="monitoring-governance-finding-resolve",
    ),
    path(
        "installer/assets/",
        InstallerAssetsView.as_view(),
        name="monitoring-installer-assets",
    ),
    path(
        "installer/build/",
        InstallerBuildView.as_view(),
        name="monitoring-installer-build",
    ),
    path(
        "installer/<str:file_name>",
        InstallerDownloadView.as_view(),
        name="monitoring-installer-download",
    ),
    path(
        "ansible/preview/",
        AnsiblePreviewView.as_view(),
        name="monitoring-ansible-preview",
    ),
    path(
        "prometheus/http-sd/blackbox/<str:target_type>/",
        PrometheusHttpSdView.as_view(),
        name="monitoring-prometheus-http-sd",
    ),
    path(
        "prometheus/http-sd/token/",
        PrometheusHttpSdTokenView.as_view(),
        name="monitoring-prometheus-http-sd-token",
    ),
    path(
        "prometheus/http-sd/config/",
        PrometheusHttpSdConfigView.as_view(),
        name="monitoring-prometheus-http-sd-config",
    ),
    path(
        "prometheus/targets/summary/",
        PrometheusTargetsSummaryView.as_view(),
        name="monitoring-prometheus-targets-summary",
    ),
    path(
        "prometheus/probe-nodes/discoveries/",
        PrometheusProbeNodeDiscoveryView.as_view(),
        name="monitoring-prometheus-probe-node-discoveries",
    ),
    path(
        "prometheus/probe-nodes/onboard/",
        PrometheusProbeNodeOnboardView.as_view(),
        name="monitoring-prometheus-probe-node-onboard",
    ),
    path(
        "blackbox/instances/",
        BlackboxInstancesView.as_view(),
        name="monitoring-blackbox-instances",
    ),
    path(
        "assets/reconciliation/",
        AssetsReconciliationView.as_view(),
        name="monitoring-assets-reconciliation",
    ),
    path("rules/", RulesView.as_view(), name="monitoring-rules"),
    path(
        "rules/<str:rule_file>/diff/",
        RuleDiffView.as_view(),
        name="monitoring-rule-diff",
    ),
    path("rules/<str:rule_file>/", RulesView.as_view(), name="monitoring-rule-detail"),
    path(
        "n9e/summary/", N9ePlatformSummaryView.as_view(), name="monitoring-n9e-summary"
    ),
    path("n9e/discover/", N9eDiscoverView.as_view(), name="monitoring-n9e-discover"),
    path(
        "n9e/import-rules/",
        N9eImportRulesView.as_view(),
        name="monitoring-n9e-import-rules",
    ),
]

urlpatterns += router.urls
