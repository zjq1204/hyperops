"""
Jenkins Trigger models.
"""

from django.conf import settings
from django.db import models


class JenkinsInstance(models.Model):
    """Jenkins instance configuration (admin only)."""

    name = models.CharField(max_length=255, verbose_name="名称")
    url = models.URLField(verbose_name="Jenkins URL")
    username = models.CharField(max_length=255, verbose_name="用户名")
    token = models.CharField(max_length=512, verbose_name="API Token")
    job_catalog_cache_ttl_days = models.PositiveIntegerField(
        default=1,
        verbose_name="Job 列表缓存时长（天）",
    )
    is_active = models.BooleanField(default=True, verbose_name="是否启用")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "Jenkins 实例"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class JenkinsGlobalConfig(models.Model):
    """Global Jenkins-related runtime configuration."""

    job_catalog_cache_ttl_seconds = models.PositiveIntegerField(
        default=86400,
        verbose_name="Job 列表缓存时长（秒）",
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "Jenkins 全局配置"
        verbose_name_plural = verbose_name

    def __str__(self):
        return "Jenkins Global Config"


class TriggerEntry(models.Model):
    """Trigger entry for a Jenkins job."""

    PARAM_MODE_CHOICES = [
        ("hidden", "隐藏（管理员预设，用户不可见）"),
        ("readonly", "只读（管理员预设，用户只读）"),
        ("editable", "可编辑（用户填写）"),
    ]

    instance = models.ForeignKey(
        JenkinsInstance,
        on_delete=models.CASCADE,
        related_name="trigger_entries",
        verbose_name="Jenkins 实例",
    )
    name = models.CharField(max_length=255, verbose_name="显示名称")
    job_name = models.CharField(max_length=512, verbose_name="Jenkins Job 名称")
    description = models.TextField(blank=True, verbose_name="描述")
    params_config = models.JSONField(
        default=dict,
        verbose_name="参数配置",
        help_text="每个参数的 mode 和预设值，格式: {param_name: {mode: 'hidden'|'readonly'|'editable', default_value: 'xxx'}}",
    )
    notify_enabled = models.BooleanField(default=False, verbose_name="是否发送通知")
    notify_emails = models.JSONField(
        default=list,
        verbose_name="通知人邮箱",
        help_text="通知人邮箱列表",
    )
    is_active = models.BooleanField(default=True, verbose_name="是否启用")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "触发入口"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.instance.name} - {self.name}"


class UserEntryNotificationPreference(models.Model):
    """Per-user notification settings for a trigger entry."""

    entry = models.ForeignKey(
        TriggerEntry,
        on_delete=models.CASCADE,
        related_name="user_notification_preferences",
        verbose_name="触发入口",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="jenkins_entry_notification_preferences",
        verbose_name="用户",
    )
    notify_personal_email = models.BooleanField(default=False, verbose_name="通知个人邮箱")
    notify_personal_webhook = models.BooleanField(default=False, verbose_name="通知个人 Webhook")
    notify_group_email = models.BooleanField(default=False, verbose_name="通知群组邮箱")
    notify_group_webhook = models.BooleanField(default=False, verbose_name="通知群组 Webhook")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "用户触发入口通知偏好"
        verbose_name_plural = verbose_name
        unique_together = [("entry", "user")]

    def __str__(self):
        return f"{self.user_id}-{self.entry_id}"


class TriggerRecord(models.Model):
    """Record of a triggered build."""

    STATUS_CHOICES = [
        ("pending", "等待中"),
        ("running", "构建中"),
        ("success", "成功"),
        ("failure", "失败"),
        ("aborted", "取消"),
    ]

    entry = models.ForeignKey(
        TriggerEntry,
        on_delete=models.CASCADE,
        related_name="records",
        verbose_name="触发入口",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="trigger_records",
        verbose_name="触发用户",
    )
    params = models.JSONField(default=dict, verbose_name="触发参数")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
        verbose_name="状态",
    )
    build_number = models.IntegerField(null=True, blank=True, verbose_name="Build Number")
    queue_url = models.URLField(
        max_length=1024,
        blank=True,
        default="",
        verbose_name="Jenkins Queue URL",
    )
    artifacts = models.JSONField(default=list, verbose_name="构建产物")
    notification_result = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="通知结果",
    )
    progress_percent = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name="Pipeline 进度百分比",
    )
    current_stage = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name="当前 Pipeline 阶段",
    )
    stage_summary = models.JSONField(
        null=True,
        blank=True,
        default=None,
        verbose_name="Pipeline 阶段摘要",
    )
    pipeline_supported = models.BooleanField(
        default=False,
        verbose_name="是否支持 Pipeline 阶段进度",
    )
    triggered_at = models.DateTimeField(auto_now_add=True, verbose_name="触发时间")
    finished_at = models.DateTimeField(null=True, blank=True, verbose_name="完成时间")

    class Meta:
        verbose_name = "触发记录"
        verbose_name_plural = verbose_name
        ordering = ["-triggered_at"]

    def __str__(self):
        return f"{self.entry.name} - #{self.build_number} ({self.status})"
