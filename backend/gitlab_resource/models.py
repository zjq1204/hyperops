"""
GitLab Resource models.
"""

from django.conf import settings
from django.db import models
from django.utils.text import slugify


class GitLabInstance(models.Model):
    """GitLab instance configuration (admin only)."""

    name = models.CharField(max_length=255, verbose_name="名称")
    url = models.URLField(verbose_name="GitLab URL")
    private_token = models.CharField(max_length=512, verbose_name="Private Token")
    is_active = models.BooleanField(default=True, verbose_name="是否启用")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "GitLab 实例"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class RegisteredGroup(models.Model):
    """Groups registered for management (admin configured)."""

    instance = models.ForeignKey(
        GitLabInstance,
        on_delete=models.CASCADE,
        related_name="registered_groups",
        verbose_name="GitLab 实例",
    )
    gitlab_id = models.IntegerField(verbose_name="GitLab Group ID")
    name = models.CharField(max_length=255, verbose_name="名称")
    path = models.CharField(max_length=512, verbose_name="路径")
    description = models.TextField(blank=True, verbose_name="描述")
    is_active = models.BooleanField(default=True, verbose_name="是否启用")
    collected_at = models.DateTimeField(null=True, blank=True, verbose_name="采集时间")

    class Meta:
        verbose_name = "注册的群组"
        verbose_name_plural = verbose_name
        ordering = ["name"]
        unique_together = ["instance", "gitlab_id"]

    def __str__(self):
        return f"{self.instance.name} - {self.name}"


class RegisteredProject(models.Model):
    """Projects registered for management (admin configured)."""

    instance = models.ForeignKey(
        GitLabInstance,
        on_delete=models.CASCADE,
        related_name="registered_projects",
        verbose_name="GitLab 实例",
    )
    group = models.ForeignKey(
        RegisteredGroup,
        on_delete=models.CASCADE,
        related_name="registered_projects",
        verbose_name="所属群组",
    )
    gitlab_id = models.IntegerField(verbose_name="GitLab Project ID")
    name = models.CharField(max_length=255, verbose_name="名称")
    path = models.CharField(max_length=512, verbose_name="路径")
    default_branch = models.CharField(max_length=255, verbose_name="默认分支", blank=True)
    labels = models.ManyToManyField(
        "GitLabProjectLabel",
        blank=True,
        related_name="projects",
        verbose_name="资源标签",
    )
    is_active = models.BooleanField(default=True, verbose_name="是否启用")
    collected_at = models.DateTimeField(null=True, blank=True, verbose_name="采集时间")

    class Meta:
        verbose_name = "注册的项目"
        verbose_name_plural = verbose_name
        ordering = ["name"]
        unique_together = ["instance", "gitlab_id"]

    def __str__(self):
        return f"{self.instance.name} - {self.path}"


class GitLabCollectionRecord(models.Model):
    """Audit record for GitLab project resource collection."""

    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_SUCCESS, "成功"),
        (STATUS_FAILED, "失败"),
    ]

    project = models.ForeignKey(
        RegisteredProject,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="collection_records",
        verbose_name="项目",
    )
    project_name = models.CharField(max_length=255, verbose_name="项目名称")
    project_path = models.CharField(max_length=512, verbose_name="项目路径")
    status = models.CharField(
        max_length=24,
        choices=STATUS_CHOICES,
        default=STATUS_SUCCESS,
        verbose_name="状态",
    )
    branches_count = models.PositiveIntegerField(default=0, verbose_name="分支数量")
    tags_count = models.PositiveIntegerField(default=0, verbose_name="标签数量")
    webhooks_count = models.PositiveIntegerField(default=0, verbose_name="Webhook 数量")
    message = models.CharField(max_length=255, blank=True, verbose_name="消息")
    error = models.TextField(blank=True, verbose_name="错误信息")
    started_at = models.DateTimeField(auto_now_add=True, verbose_name="开始时间")
    finished_at = models.DateTimeField(null=True, blank=True, verbose_name="完成时间")

    class Meta:
        verbose_name = "GitLab 采集记录"
        verbose_name_plural = verbose_name
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.project_path} - {self.status}"


class GitLabOperationRecord(models.Model):
    """Unified audit record for GitLab management write operations."""

    STATUS_SUCCESS = "success"
    STATUS_PARTIAL_SUCCESS = "partial_success"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_SUCCESS, "成功"),
        (STATUS_PARTIAL_SUCCESS, "部分成功"),
        (STATUS_FAILED, "失败"),
    ]

    ACTION_COLLECT_PROJECTS = "collect_projects"
    ACTION_COLLECT_RESOURCES = "collect_resources"
    ACTION_BRANCH_CREATE = "branch_create"
    ACTION_BRANCH_DELETE = "branch_delete"
    ACTION_BRANCH_PROTECT = "branch_protect"
    ACTION_BRANCH_UNPROTECT = "branch_unprotect"
    ACTION_TAG_CREATE = "tag_create"
    ACTION_TAG_DELETE = "tag_delete"
    ACTION_WEBHOOK_CREATE = "webhook_create"
    ACTION_WEBHOOK_UPDATE = "webhook_update"
    ACTION_WEBHOOK_DELETE = "webhook_delete"
    ACTION_PROJECT_LABEL_UPDATE = "project_label_update"
    ACTION_PROJECT_LABEL_DELETE = "project_label_delete"
    ACTION_CHOICES = [
        (ACTION_COLLECT_PROJECTS, "采集项目"),
        (ACTION_COLLECT_RESOURCES, "采集项目资源"),
        (ACTION_BRANCH_CREATE, "新增分支"),
        (ACTION_BRANCH_DELETE, "删除分支"),
        (ACTION_BRANCH_PROTECT, "保护分支"),
        (ACTION_BRANCH_UNPROTECT, "取消保护分支"),
        (ACTION_TAG_CREATE, "新增标签"),
        (ACTION_TAG_DELETE, "删除标签"),
        (ACTION_WEBHOOK_CREATE, "新增 Webhook"),
        (ACTION_WEBHOOK_UPDATE, "编辑 Webhook"),
        (ACTION_WEBHOOK_DELETE, "删除 Webhook"),
        (ACTION_PROJECT_LABEL_UPDATE, "项目标签变更"),
        (ACTION_PROJECT_LABEL_DELETE, "删除资源标签"),
    ]

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="gitlab_operation_records",
        verbose_name="操作人",
    )
    action = models.CharField(max_length=64, choices=ACTION_CHOICES, verbose_name="操作类型")
    status = models.CharField(
        max_length=24,
        choices=STATUS_CHOICES,
        default=STATUS_SUCCESS,
        verbose_name="状态",
    )
    instance = models.ForeignKey(
        GitLabInstance,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="operation_records",
        verbose_name="GitLab 实例",
    )
    group = models.ForeignKey(
        RegisteredGroup,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="operation_records",
        verbose_name="群组",
    )
    project = models.ForeignKey(
        RegisteredProject,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="operation_records",
        verbose_name="项目",
    )
    target_summary = models.CharField(max_length=512, blank=True, verbose_name="目标摘要")
    request_data = models.JSONField(default=dict, blank=True, verbose_name="请求参数")
    result_data = models.JSONField(default=dict, blank=True, verbose_name="执行结果")
    total_count = models.PositiveIntegerField(default=0, verbose_name="总数")
    success_count = models.PositiveIntegerField(default=0, verbose_name="成功数")
    failed_count = models.PositiveIntegerField(default=0, verbose_name="失败数")
    error = models.TextField(blank=True, verbose_name="错误信息")
    started_at = models.DateTimeField(auto_now_add=True, verbose_name="开始时间")
    finished_at = models.DateTimeField(null=True, blank=True, verbose_name="完成时间")

    class Meta:
        verbose_name = "GitLab 操作记录"
        verbose_name_plural = verbose_name
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["action", "-started_at"]),
            models.Index(fields=["status", "-started_at"]),
        ]

    def __str__(self):
        return f"{self.get_action_display()} - {self.status}"


class GitLabProjectLabel(models.Model):
    """Business labels for grouping registered GitLab projects."""

    name = models.CharField(max_length=255, verbose_name="标签名称")
    slug = models.SlugField(max_length=255, unique=True, verbose_name="标签标识", allow_unicode=True)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "GitLab 项目标签"
        verbose_name_plural = verbose_name
        ordering = ["name"]

    def save(self, *args, **kwargs):
        normalized_name = (self.name or "").strip()
        self.name = normalized_name
        self.slug = slugify(normalized_name, allow_unicode=True)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class GitLabBranch(models.Model):
    """GitLab branch (collected)."""

    project = models.ForeignKey(
        RegisteredProject,
        on_delete=models.CASCADE,
        related_name="branches",
        verbose_name="项目",
    )
    name = models.CharField(max_length=255, verbose_name="分支名称")
    protected = models.BooleanField(default=False, verbose_name="是否保护")
    last_commit_date = models.DateTimeField(null=True, blank=True, verbose_name="最后提交时间")
    last_commit_sha = models.CharField(max_length=64, blank=True, verbose_name="最后提交 SHA")
    collected_at = models.DateTimeField(auto_now=True, verbose_name="采集时间")

    class Meta:
        verbose_name = "GitLab 分支"
        verbose_name_plural = verbose_name
        ordering = ["name"]
        unique_together = ["project", "name"]

    def __str__(self):
        return f"{self.project.path} - {self.name}"


class GitLabTag(models.Model):
    """GitLab tag (collected)."""

    project = models.ForeignKey(
        RegisteredProject,
        on_delete=models.CASCADE,
        related_name="tags",
        verbose_name="项目",
    )
    name = models.CharField(max_length=255, verbose_name="Tag 名称")
    commit_sha = models.CharField(max_length=64, blank=True, verbose_name="Commit SHA")
    released_at = models.DateTimeField(null=True, blank=True, verbose_name="发布日期")
    collected_at = models.DateTimeField(auto_now=True, verbose_name="采集时间")

    class Meta:
        verbose_name = "GitLab Tag"
        verbose_name_plural = verbose_name
        ordering = ["name"]
        unique_together = ["project", "name"]

    def __str__(self):
        return f"{self.project.path} - {self.name}"


class GitLabWebhook(models.Model):
    """GitLab webhook (managed)."""

    project = models.ForeignKey(
        RegisteredProject,
        on_delete=models.CASCADE,
        related_name="webhooks",
        verbose_name="项目",
    )
    webhook_id = models.IntegerField(null=True, blank=True, verbose_name="GitLab Webhook ID")
    url = models.URLField(verbose_name="Webhook URL")
    token = models.CharField(max_length=255, blank=True, default="", verbose_name="Secret Token")
    push_events = models.BooleanField(default=True, verbose_name="Push 事件")
    push_events_branch_filter = models.CharField(max_length=255, blank=True, default="", verbose_name="Push 事件分支过滤")
    tag_push_events = models.BooleanField(default=False, verbose_name="Tag 推送事件")
    merge_requests_events = models.BooleanField(default=False, verbose_name="合并请求事件")
    issues_events = models.BooleanField(default=False, verbose_name="Issue 事件")
    confidential_issues_events = models.BooleanField(default=False, verbose_name="保密 Issue 事件")
    note_events = models.BooleanField(default=False, verbose_name="备注事件")
    confidential_note_events = models.BooleanField(default=False, verbose_name="保密备注事件")
    pipeline_events = models.BooleanField(default=False, verbose_name="Pipeline 事件")
    job_events = models.BooleanField(default=False, verbose_name="Job 事件")
    wiki_page_events = models.BooleanField(default=False, verbose_name="Wiki 页面事件")
    deployment_events = models.BooleanField(default=False, verbose_name="部署事件")
    releases_events = models.BooleanField(default=False, verbose_name="Release 事件")
    feature_flag_events = models.BooleanField(default=False, verbose_name="Feature Flag 事件")
    repository_update_events = models.BooleanField(default=False, verbose_name="仓库更新事件")
    resource_access_token_events = models.BooleanField(default=False, verbose_name="资源访问令牌事件")
    enable_ssl_verification = models.BooleanField(default=True, verbose_name="启用 SSL 验证")
    created_at = models.DateTimeField(null=True, blank=True, verbose_name="GitLab 创建时间")
    collected_at = models.DateTimeField(auto_now=True, verbose_name="采集时间")

    class Meta:
        verbose_name = "GitLab Webhook"
        verbose_name_plural = verbose_name
        ordering = ["-collected_at"]

    def __str__(self):
        return f"{self.project.path} - {self.url}"
