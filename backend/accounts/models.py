"""
This module defines the Profile model for extending the built-in User model
using a one-to-one relationship. The Profile model adds additional fields
to store personal details, preferences, and registration state.

For OAuth/Social authentication, this project uses django-allauth's
SocialAccount model instead of storing provider-specific IDs in Profile.
See: allauth.socialaccount.models.SocialAccount

Django's default User model includes the following fields:
    - username: A unique identifier for the user.
    - first_name: The user's first name.
    - last_name: The user's last name.
    - email: The user's email address.
    - password: The user's hashed password.
    - is_staff: Boolean indicating if the user can access the admin site.
    - is_active: Boolean indicating if the user account is active.
    - date_joined: The date when the user account was created.
    - last_login: The last time the user logged in.

Other methods to extend the User model:
    - Proxy model: Modify behavior without changing the schema.
    - Subclassing User: Create a custom user model with your own fields.
    - Using a ForeignKey: Establish a many-to-one relationship for extensions.
"""
from django.contrib.auth.models import Group, User
from django.db import models
from django.utils.text import slugify
from django.utils import timezone

from accounts.access import (
    normalize_feature_keys,
    normalize_operation_permission_keys,
    normalize_platform_key,
)


class Role(models.Model):
    """Role-based visibility definition for consoles and route groups."""

    name = models.CharField(
        max_length=120,
        unique=True,
        help_text="Human-readable role name.",
    )
    visible_features = models.JSONField(
        default=list,
        blank=True,
        help_text="Feature keys visible to users who hold this role.",
    )
    operation_permissions = models.JSONField(default=list, blank=True)
    preferred_platform = models.CharField(
        max_length=50,
        blank=True,
        default='',
        help_text="Default platform to open after login.",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this role participates in access calculation.",
    )
    users = models.ManyToManyField(
        User,
        blank=True,
        related_name='platform_roles',
        help_text="Users directly bound to this role.",
    )
    groups = models.ManyToManyField(
        'auth.Group',
        blank=True,
        related_name='platform_roles',
        help_text="Groups whose members inherit this role.",
    )

    class Meta:
        ordering = ['name', 'id']

    def save(self, *args, **kwargs):
        """Normalize stored feature and platform values."""
        self.visible_features = normalize_feature_keys(self.visible_features)
        self.operation_permissions = normalize_operation_permission_keys(
            self.operation_permissions
        )
        self.preferred_platform = normalize_platform_key(
            self.preferred_platform
        )
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Profile(models.Model):
    """
    The Profile model extends the built-in User model using a one-to-one
    relationship. It stores personal information, preferences, and
    registration state.

    Note: OAuth/Social authentication uses django-allauth's SocialAccount
    model. To query social accounts:
        from allauth.socialaccount.models import SocialAccount
        social_accounts = SocialAccount.objects.filter(user=user)
        google_account = SocialAccount.objects.get(
            user=user,
            provider='google'
        )
    """

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE
    )

    AUTH_SOURCE_LOCAL = "local"
    AUTH_SOURCE_LDAP = "ldap"
    AUTH_SOURCE_OAUTH = "oauth"
    AUTH_SOURCE_CHOICES = [
        (AUTH_SOURCE_LOCAL, "Local"),
        (AUTH_SOURCE_LDAP, "LDAP"),
        (AUTH_SOURCE_OAUTH, "OAuth"),
    ]

    registration_completed = models.BooleanField(
        default=False,
        help_text=(
            "Indicates whether user has completed the registration process "
            "(set password, virtual email, scene selection)."
        )
    )

    registration_token = models.CharField(
        max_length=255,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        help_text=(
            "Temporary token for email registration verification. "
            "Expires after REGISTRATION_TOKEN_EXPIRY_HOURS."
        )
    )

    registration_token_expires = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Expiration datetime for registration_token."
    )

    nickname = models.CharField(
        max_length=30,
        blank=True,
        help_text="User nickname."
    )

    avatar_url = models.URLField(
        blank=True,
        help_text="URL link to the user's avatar."
    )

    bio = models.TextField(
        max_length=500,
        blank=True,
        help_text="Personal biography or description."
    )

    language = models.CharField(
        max_length=10,
        default='zh-CN',
        choices=[
            ('en-US', 'English'),
            ('zh-CN', '简体中文'),
            ('es', 'Español'),
            ('ja-JP', '日本語'),
            ('ko-KR', '한국어'),
        ],
        help_text=(
            "Specifies the language used by AI when generating summaries, "
            "titles, and metadata. This is a global setting shared across "
            "all applications."
        )
    )

    timezone = models.CharField(
        max_length=50,
        default='Asia/Shanghai',
        help_text=(
            "User's timezone for displaying dates and times. "
            "Common values: 'UTC', 'Asia/Shanghai', 'America/New_York', etc."
        )
    )

    preferred_platform = models.CharField(
        max_length=50,
        blank=True,
        default='',
        help_text=(
            "Optional user-level preferred platform. "
            "If empty, the effective role preference is used."
        )
    )

    auth_source = models.CharField(
        max_length=16,
        choices=AUTH_SOURCE_CHOICES,
        default=AUTH_SOURCE_LOCAL,
        help_text="Primary authentication source for the user.",
    )

    ldap_uid = models.CharField(
        max_length=255,
        blank=True,
        default="",
        db_index=True,
        help_text="Directory uid used for LDAP login.",
    )

    ldap_instance = models.ForeignKey(
        "LdapAuthConfig",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="profiles",
        help_text="LDAP instance that owns this directory identity.",
    )

    ldap_dn = models.CharField(
        max_length=512,
        blank=True,
        default="",
        help_text="Resolved LDAP distinguished name for the user.",
    )

    ldap_last_synced_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last successful LDAP profile/group sync time.",
    )

    ldap_group_dns_snapshot = models.JSONField(
        default=list,
        blank=True,
        help_text="Last LDAP group DNS returned during successful sync.",
    )

    jenkins_notification_strategy = models.CharField(
        max_length=32,
        default='user_only',
        choices=[
            ('user_only', '仅个人'),
            ('group_only', '仅群组'),
            ('user_first_fallback_group', '个人优先，无个人则群组'),
            ('user_and_group', '个人 + 群组'),
        ],
        help_text="How Jenkins completion notifications resolve recipients.",
    )

    jenkins_notification_emails = models.JSONField(
        default=list,
        blank=True,
        help_text="Extra email recipients for Jenkins notifications.",
    )

    jenkins_notification_webhooks = models.JSONField(
        default=list,
        blank=True,
        help_text="Webhook URLs for Jenkins notifications.",
    )

    def __str__(self):
        """
        Returns the username of the associated User model for a readable
        representation of the Profile instance.
        """
        return self.user.username


class GroupNotificationConfig(models.Model):
    """Notification endpoints owned by a Django group."""

    group = models.OneToOneField(
        Group,
        on_delete=models.CASCADE,
        related_name='jenkins_notification_config',
    )
    notification_emails = models.JSONField(
        default=list,
        blank=True,
        help_text="Group-level email recipients for Jenkins notifications.",
    )
    notification_webhooks = models.JSONField(
        default=list,
        blank=True,
        help_text="Group-level webhook URLs for Jenkins notifications.",
    )

    def __str__(self):
        return f"Jenkins notifications for {self.group.name}"


class LdapAuthConfig(models.Model):
    """LDAP connection and attribute mapping settings."""

    name = models.CharField(max_length=120, default="Default LDAP")
    slug = models.SlugField(max_length=64, unique=True, default="default")
    is_default = models.BooleanField(default=False)
    enabled = models.BooleanField(default=False)
    host = models.CharField(max_length=255, blank=True, default="")
    port = models.PositiveIntegerField(default=389)
    use_ssl = models.BooleanField(default=False)
    start_tls = models.BooleanField(default=False)
    bind_dn = models.CharField(max_length=512, blank=True, default="")
    bind_password_encrypted = models.TextField(blank=True, default="")
    user_base_dn = models.CharField(max_length=512, blank=True, default="")
    user_filter_template = models.CharField(
        max_length=512,
        blank=True,
        default="(&(objectClass=person)(uid={username}))",
    )
    group_base_dn = models.CharField(max_length=512, blank=True, default="")
    group_filter_template = models.CharField(
        max_length=512,
        blank=True,
        default="(&(objectClass=groupOfNames)(member={user_dn}))",
    )
    uid_attr = models.CharField(max_length=128, blank=True, default="uid")
    email_attr = models.CharField(max_length=128, blank=True, default="mail")
    first_name_attr = models.CharField(
        max_length=128,
        blank=True,
        default="givenName",
    )
    last_name_attr = models.CharField(max_length=128, blank=True, default="sn")
    display_name_attr = models.CharField(
        max_length=128,
        blank=True,
        default="displayName",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_default", "id"]
        verbose_name = "LDAP configuration"
        verbose_name_plural = "LDAP configurations"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name or self.host or "ldap") or "ldap"
        if self.is_default:
            # Enforce a single default by clearing the flag on every other row
            # in the same atomic block. We avoid model-level constraints to
            # stay compatible with the existing data and admin UIs.
            from django.db import transaction

            with transaction.atomic():
                super().save(*args, **kwargs)
                LdapAuthConfig.objects.exclude(pk=self.pk).filter(
                    is_default=True
                ).update(is_default=False)
            return
        super().save(*args, **kwargs)

    @property
    def has_bind_password(self):
        return bool(self.bind_password_encrypted)

    def get_bind_password(self):
        from accounts.services.ldap_crypto import decrypt_secret

        return decrypt_secret(self.bind_password_encrypted)

    def set_bind_password(self, value):
        from accounts.services.ldap_crypto import encrypt_secret

        self.bind_password_encrypted = encrypt_secret(value)

    def to_runtime_settings(self, overrides=None):
        data = {
            "enabled": self.enabled,
            "host": self.host,
            "port": self.port,
            "use_ssl": self.use_ssl,
            "start_tls": self.start_tls,
            "bind_dn": self.bind_dn,
            "bind_password": self.get_bind_password(),
            "user_base_dn": self.user_base_dn,
            "user_filter_template": self.user_filter_template,
            "group_base_dn": self.group_base_dn,
            "group_filter_template": self.group_filter_template,
            "uid_attr": self.uid_attr,
            "email_attr": self.email_attr,
            "first_name_attr": self.first_name_attr,
            "last_name_attr": self.last_name_attr,
            "display_name_attr": self.display_name_attr,
        }
        if overrides:
            data.update(overrides)
        return data

    def __str__(self):
        return f"{self.name} ({self.host or 'unconfigured'})"


class LdapGroupMapping(models.Model):
    """Map LDAP group DNs to local Django groups."""

    SCOPE_GROUP = "group"
    SCOPE_ALL = "all"
    MAPPING_SCOPE_CHOICES = [
        (SCOPE_GROUP, "Specific LDAP group"),
        (SCOPE_ALL, "All LDAP users"),
    ]

    ldap_config = models.ForeignKey(
        LdapAuthConfig,
        on_delete=models.CASCADE,
        related_name="group_mappings",
    )
    mapping_scope = models.CharField(
        max_length=16,
        choices=MAPPING_SCOPE_CHOICES,
        default=SCOPE_GROUP,
    )
    ldap_group_dn = models.CharField(
        max_length=512,
        blank=True,
        default="",
        db_index=True,
    )
    target_group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name="ldap_group_mappings",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = [
            "ldap_config__name",
            "mapping_scope",
            "ldap_group_dn",
            "target_group__name",
            "id",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "ldap_config",
                    "mapping_scope",
                    "ldap_group_dn",
                    "target_group",
                ],
                name="accounts_ldap_group_mapping_unique_pair",
            )
        ]

    def save(self, *args, **kwargs):
        if self.mapping_scope == self.SCOPE_ALL:
            self.ldap_group_dn = ""
        self.ldap_group_dn = (self.ldap_group_dn or "").strip()
        super().save(*args, **kwargs)

    def __str__(self):
        source = (
            "all LDAP users"
            if self.mapping_scope == self.SCOPE_ALL
            else self.ldap_group_dn
        )
        return f"{source} -> {self.target_group.name}"
