from pathlib import Path

from django.conf import settings
from django.db import models


def monitoring_ssh_dir() -> Path:
    configured = getattr(settings, "MONITORING_SSH_DIR", "")
    if configured:
        return Path(configured)
    root = getattr(settings, "MONITORING_STACK_ROOT", "")
    if root:
        return Path(root) / "ssh"
    return Path(getattr(settings, "STORAGE_ROOT", "/opt/storage")) / "monitoring_stack" / "ssh"


class MonitoringProfile(models.Model):
    """Categraf collection profile definition."""

    id = models.CharField(max_length=80, primary_key=True)
    name = models.CharField(max_length=160)
    category = models.CharField(max_length=80, blank=True, default="")
    description = models.TextField(blank=True, default="")
    plugins = models.JSONField(default=list, blank=True)
    is_builtin = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["category", "id"]

    def __str__(self):
        return self.name


class MonitoringIntegrationConfig(models.Model):
    """Runtime monitoring integration configuration managed from HyperOps."""

    n9e_url = models.CharField(max_length=512, blank=True, default="")
    n9e_username = models.CharField(max_length=120, blank=True, default="")
    n9e_password = models.CharField(max_length=512, blank=True, default="")
    prometheus_url = models.CharField(max_length=512, blank=True, default="")
    prometheus_http_sd_token = models.CharField(max_length=255, blank=True, default="")
    grafana_url = models.CharField(max_length=512, blank=True, default="")
    installer_base_url = models.CharField(max_length=512, blank=True, default="")
    categraf_install_dir = models.CharField(max_length=255, blank=True, default="")
    blackbox_install_dir = models.CharField(max_length=255, blank=True, default="")
    blackbox_port = models.CharField(max_length=16, blank=True, default="")
    blackbox_image = models.CharField(max_length=255, blank=True, default="")
    updated_by = models.ForeignKey(
        "auth.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="updated_monitoring_configs",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Monitoring integration config"
        verbose_name_plural = "Monitoring integration configs"

    def __str__(self):
        return "monitoring integration config"

    @classmethod
    def current(cls):
        obj, _created = cls.objects.get_or_create(pk=1)
        return obj


class ProbeTarget(models.Model):
    """Prometheus HTTP SD target for blackbox exporter probes."""

    TYPE_HTTP = "http"
    TYPE_TCP = "tcp"
    TYPE_ICMP = "icmp"
    TYPE_CHOICES = [
        (TYPE_HTTP, "HTTP"),
        (TYPE_TCP, "TCP"),
        (TYPE_ICMP, "ICMP"),
    ]

    external_id = models.CharField(max_length=80, unique=True, null=True, blank=True)
    type = models.CharField(max_length=16, choices=TYPE_CHOICES)
    target = models.CharField(max_length=512)
    probe_node = models.ForeignKey(
        "BlackboxProbeNode",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="probe_targets",
    )
    enabled = models.BooleanField(default=True)
    labels = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["type", "target", "id"]
        indexes = [
            models.Index(
                fields=["type", "enabled"], name="monitoring__type_846303_idx"
            ),
        ]

    def __str__(self):
        return f"{self.type}:{self.target}"


class BlackboxProbeNode(models.Model):
    """blackbox-exporter instance used to execute probe targets."""

    SOURCE_MANUAL = "manual"
    SOURCE_INSTALL = "install"
    SOURCE_CHOICES = [
        (SOURCE_MANUAL, "Manual"),
        (SOURCE_INSTALL, "HyperOps install"),
    ]

    name = models.CharField(max_length=120, unique=True)
    address = models.CharField(max_length=255)
    port = models.CharField(max_length=16, default="9115")
    source = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        default=SOURCE_MANUAL,
    )
    host = models.ForeignKey(
        "MonitoringHost",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="blackbox_probe_nodes",
    )
    install_dir = models.CharField(max_length=255, blank=True, default="")
    labels = models.JSONField(default=dict, blank=True)
    enabled = models.BooleanField(default=True)
    last_job = models.ForeignKey(
        "AnsibleInstallJob",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="blackbox_probe_nodes",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "id"]
        indexes = [
            models.Index(
                fields=["enabled", "source"],
                name="monitoring__probe_n_4f7fb1_idx",
            ),
        ]

    def __str__(self):
        return self.name

    @property
    def endpoint(self):
        address = str(self.address or "").strip()
        port = str(self.port or "").strip()
        return f"{address}:{port}" if address and port else address


class MonitoringSshKey(models.Model):
    """Reusable SSH private key saved for monitoring asset installation."""

    name = models.CharField(max_length=120, unique=True)
    file_name = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "id"]

    def __str__(self):
        return self.name

    @property
    def storage_path(self):
        return monitoring_ssh_dir() / self.file_name


class MonitoringHost(models.Model):
    """Host asset used to install Categraf through Ansible."""

    SSH_AUTH_KEY = "key"
    SSH_AUTH_PASSWORD = "password"
    SSH_AUTH_CHOICES = [
        (SSH_AUTH_KEY, "SSH key"),
        (SSH_AUTH_PASSWORD, "Password"),
    ]

    external_id = models.CharField(max_length=80, unique=True, null=True, blank=True)
    hostname = models.CharField(max_length=160)
    address = models.CharField(max_length=255)
    ssh_user = models.CharField(max_length=80, default="root", blank=True)
    ssh_port = models.PositiveIntegerField(default=22)
    ssh_auth_type = models.CharField(
        max_length=16, choices=SSH_AUTH_CHOICES, default=SSH_AUTH_KEY
    )
    ssh_password = models.CharField(max_length=512, blank=True, default="")
    ssh_key_credential = models.ForeignKey(
        MonitoringSshKey,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="hosts",
    )
    ssh_key = models.CharField(max_length=255, blank=True, default="")
    profiles = models.JSONField(default=list, blank=True)
    labels = models.JSONField(default=dict, blank=True)
    params = models.JSONField(default=dict, blank=True)
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["hostname", "id"]
        indexes = [
            models.Index(fields=["enabled"], name="monitoring__enabled_940a22_idx"),
        ]

    def __str__(self):
        return self.hostname


class AnsibleInstallJob(models.Model):
    """Recorded monitoring component installation job."""

    COMPONENT_CATEGRAF = "categraf"
    COMPONENT_BLACKBOX = "blackbox"
    COMPONENT_CHOICES = [
        (COMPONENT_CATEGRAF, "Categraf"),
        (COMPONENT_BLACKBOX, "blackbox-exporter"),
    ]

    STATUS_QUEUED = "queued"
    STATUS_RUNNING = "running"
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_QUEUED, "Queued"),
        (STATUS_RUNNING, "Running"),
        (STATUS_SUCCESS, "Success"),
        (STATUS_FAILED, "Failed"),
    ]

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_QUEUED,
    )
    component = models.CharField(
        max_length=20,
        choices=COMPONENT_CHOICES,
        default=COMPONENT_CATEGRAF,
    )
    profiles = models.JSONField(default=list, blank=True)
    labels = models.JSONField(default=dict, blank=True)
    params = models.JSONField(default=dict, blank=True)
    host_ids = models.JSONField(default=list, blank=True)
    hosts_snapshot = models.JSONField(default=list, blank=True)
    base_url = models.URLField(max_length=512)
    n9e_url = models.URLField(max_length=512, blank=True, default="")
    install_dir = models.CharField(max_length=255, default="/opt/categraf")
    image = models.CharField(max_length=255, default="flashcatcloud/categraf:latest")
    probe_name = models.CharField(max_length=120, blank=True, default="")
    blackbox_port = models.CharField(max_length=16, blank=True, default="9115")
    returncode = models.IntegerField(null=True, blank=True)
    logs = models.JSONField(default=list, blank=True)
    results = models.JSONField(default=list, blank=True)
    retry_of = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="retry_jobs",
    )
    created_by = models.ForeignKey(
        "auth.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="monitoring_ansible_jobs",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"monitoring install job #{self.pk}"


class MonitoringComponentStatus(models.Model):
    """Current installation state for a monitoring component on one host."""

    STATUS_UNKNOWN = "unknown"
    STATUS_INSTALLING = "installing"
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_UNKNOWN, "Unknown"),
        (STATUS_INSTALLING, "Installing"),
        (STATUS_SUCCESS, "Success"),
        (STATUS_FAILED, "Failed"),
    ]

    host = models.ForeignKey(
        MonitoringHost,
        on_delete=models.CASCADE,
        related_name="component_statuses",
    )
    component = models.CharField(
        max_length=20,
        choices=AnsibleInstallJob.COMPONENT_CHOICES,
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_UNKNOWN,
    )
    version = models.CharField(max_length=80, blank=True, default="")
    install_dir = models.CharField(max_length=255, blank=True, default="")
    last_job = models.ForeignKey(
        AnsibleInstallJob,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="component_statuses",
    )
    last_error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["host__hostname", "component"]
        constraints = [
            models.UniqueConstraint(
                fields=["host", "component"],
                name="unique_monitoring_component_status",
            )
        ]
        indexes = [
            models.Index(
                fields=["component", "status"],
                name="monitoring__compone_51d3e5_idx",
            ),
        ]

    def __str__(self):
        return f"{self.host_id}:{self.component}:{self.status}"


class RuleImportRecord(models.Model):
    """History for importing local rule templates into n9e."""

    STATUS_SUCCESS = "success"
    STATUS_PARTIAL = "partial"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_SUCCESS, "Success"),
        (STATUS_PARTIAL, "Partial"),
        (STATUS_FAILED, "Failed"),
    ]

    rule_file = models.CharField(max_length=255)
    template_category = models.CharField(max_length=40, blank=True, default="")
    group_id = models.IntegerField()
    datasource_id = models.IntegerField()
    enabled = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    summary = models.JSONField(default=dict, blank=True)
    result = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(
        "auth.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="monitoring_rule_imports",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(
                fields=["rule_file", "status"], name="monitoring__rule_fi_2f0a34_idx"
            ),
        ]

    def __str__(self):
        return f"{self.rule_file}:{self.status}"


class MonitoringSnapshotRun(models.Model):
    """One read-only synchronization run against external monitoring systems."""

    SOURCE_ALL = "all"
    SOURCE_N9E = "n9e"
    SOURCE_PROMETHEUS = "prometheus"
    SOURCE_CHOICES = [
        (SOURCE_ALL, "All"),
        (SOURCE_N9E, "n9e"),
        (SOURCE_PROMETHEUS, "Prometheus"),
    ]

    STATUS_RUNNING = "running"
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_RUNNING, "Running"),
        (STATUS_SUCCESS, "Success"),
        (STATUS_FAILED, "Failed"),
    ]

    source = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        default=SOURCE_ALL,
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_RUNNING,
    )
    started_at = models.DateTimeField()
    finished_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True, default="")
    summary = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-started_at", "-id"]
        indexes = [
            models.Index(fields=["source", "status"], name="monitoring__snapsho_91c2d1_idx"),
        ]

    def __str__(self):
        return f"{self.source}:{self.status}:{self.pk}"


class N9eBusinessGroupSnapshot(models.Model):
    """Latest known n9e business group from a snapshot run."""

    external_id = models.CharField(max_length=120, unique=True)
    name = models.CharField(max_length=255, blank=True, default="")
    raw = models.JSONField(default=dict, blank=True)
    last_seen_run = models.ForeignKey(
        MonitoringSnapshotRun,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="n9e_business_groups",
    )
    last_seen_at = models.DateTimeField()

    class Meta:
        ordering = ["name", "external_id"]

    def __str__(self):
        return self.name or self.external_id


class N9eDatasourceSnapshot(models.Model):
    """Latest known n9e datasource from a snapshot run."""

    external_id = models.CharField(max_length=120, unique=True)
    name = models.CharField(max_length=255, blank=True, default="")
    type = models.CharField(max_length=80, blank=True, default="")
    raw = models.JSONField(default=dict, blank=True)
    last_seen_run = models.ForeignKey(
        MonitoringSnapshotRun,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="n9e_datasources",
    )
    last_seen_at = models.DateTimeField()

    class Meta:
        ordering = ["type", "name", "external_id"]

    def __str__(self):
        return self.name or self.external_id


class N9eTargetSnapshot(models.Model):
    """Latest known host or target object visible in n9e."""

    identity = models.CharField(max_length=255, unique=True)
    hostname = models.CharField(max_length=255, blank=True, default="")
    address = models.CharField(max_length=255, blank=True, default="")
    labels = models.JSONField(default=dict, blank=True)
    raw = models.JSONField(default=dict, blank=True)
    last_seen_run = models.ForeignKey(
        MonitoringSnapshotRun,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="n9e_targets",
    )
    last_seen_at = models.DateTimeField()

    class Meta:
        ordering = ["hostname", "address", "identity"]

    def __str__(self):
        return self.hostname or self.address or self.identity


class N9eRuleSnapshot(models.Model):
    """Latest known n9e alert rule from a snapshot run."""

    identity = models.CharField(max_length=255, unique=True)
    group_id = models.CharField(max_length=120, blank=True, default="")
    name = models.CharField(max_length=255, blank=True, default="")
    enabled = models.BooleanField(default=True)
    severity = models.CharField(max_length=80, blank=True, default="")
    raw = models.JSONField(default=dict, blank=True)
    last_seen_run = models.ForeignKey(
        MonitoringSnapshotRun,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="n9e_rules",
    )
    last_seen_at = models.DateTimeField()

    class Meta:
        ordering = ["group_id", "name", "identity"]

    def __str__(self):
        return self.name or self.identity


class PrometheusTargetSnapshot(models.Model):
    """Latest known Prometheus active target from a snapshot run."""

    identity = models.CharField(max_length=512, unique=True)
    job = models.CharField(max_length=255, blank=True, default="")
    instance = models.CharField(max_length=512, blank=True, default="")
    scrape_pool = models.CharField(max_length=255, blank=True, default="")
    health = models.CharField(max_length=40, blank=True, default="unknown")
    probe_type = models.CharField(max_length=16, blank=True, default="")
    probe_target = models.CharField(max_length=512, blank=True, default="")
    last_error = models.TextField(blank=True, default="")
    raw = models.JSONField(default=dict, blank=True)
    last_seen_run = models.ForeignKey(
        MonitoringSnapshotRun,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="prometheus_targets",
    )
    last_seen_at = models.DateTimeField()

    class Meta:
        ordering = ["scrape_pool", "instance", "identity"]
        indexes = [
            models.Index(fields=["health"], name="monitoring__health_123508_idx"),
            models.Index(fields=["probe_type"], name="monitoring__probe_t_178f9e_idx"),
        ]

    def __str__(self):
        return self.identity


class MonitoringGovernanceFinding(models.Model):
    """Actionable drift between HyperOps config and real monitoring state."""

    SEVERITY_CRITICAL = "critical"
    SEVERITY_WARNING = "warning"
    SEVERITY_INFO = "info"
    SEVERITY_CHOICES = [
        (SEVERITY_CRITICAL, "Critical"),
        (SEVERITY_WARNING, "Warning"),
        (SEVERITY_INFO, "Info"),
    ]

    STATUS_OPEN = "open"
    STATUS_RESOLVED = "resolved"
    STATUS_IGNORED = "ignored"
    STATUS_CHOICES = [
        (STATUS_OPEN, "Open"),
        (STATUS_RESOLVED, "Resolved"),
        (STATUS_IGNORED, "Ignored"),
    ]

    category = models.CharField(max_length=80)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_OPEN,
    )
    title = models.CharField(max_length=255)
    subject_type = models.CharField(max_length=40)
    subject_key = models.CharField(max_length=512)
    source = models.CharField(max_length=40, blank=True, default="")
    details = models.JSONField(default=dict, blank=True)
    recommended_action = models.CharField(max_length=80, blank=True, default="")
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["severity", "category", "subject_key", "-updated_at"]
        indexes = [
            models.Index(fields=["status", "severity"], name="monitoring__status_1d4814_idx"),
            models.Index(fields=["subject_type", "status"], name="monitoring__subject_7c2d6c_idx"),
        ]

    def __str__(self):
        return f"{self.category}:{self.subject_key}:{self.status}"
