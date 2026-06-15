from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _

from rest_framework import serializers

from allauth.socialaccount.models import SocialAccount
from platformkit.auth import (
    AuthTokenResponseSerializer,
    PasswordResetConfirmSerializer,
    SuccessResponseSerializer,
    TokenVerificationResponseSerializer,
    UsernameAvailabilityResponseSerializer,
    get_password_reset_eligible_user,
    validate_password_strength,
)
from platformkit.identifiers import validate_virtual_email_username
from platformkit.i18n import normalize_language_code
from platformkit.social import get_social_provider_names
from platformkit.users import (
    build_auth_info,
    build_display_name,
    build_profile_snapshot,
    get_virtual_email,
    upsert_profile_preferences,
)

from accounts.access import (
    get_access_profile,
    get_effective_roles,
    normalize_feature_keys,
    normalize_platform_key,
    serialize_feature_options,
    serialize_platform_options,
)
from accounts.models import Profile


class SceneSerializer(serializers.Serializer):
    """
    Scene information serializer.
    """
    key = serializers.CharField(
        help_text=_("Scene key (e.g., 'chat', 'product_issue')")
    )
    name = serializers.CharField(
        help_text=_("Scene display name in requested language")
    )
    description = serializers.CharField(
        help_text=_("Scene description in requested language")
    )


class SendRegistrationEmailSerializer(serializers.Serializer):
    """
    Serializer for sending registration email.
    """
    email = serializers.EmailField(
        required=True,
        help_text=_("User's email address")
    )

    def validate_email(self, value):
        """
        Validate email is not already registered and completed.

        Check if user registered via OAuth and provide friendly hint.
        Allow re-sending email if user exists but registration not completed.
        """
        value = value.lower().strip()

        try:
            user = User.objects.get(email=value)

            try:
                profile = user.profile
                if profile.registration_completed:
                    social_accounts = SocialAccount.objects.filter(
                        user=user
                    )

                    if social_accounts.exists():
                        provider_names = get_social_provider_names(
                            social_accounts
                        )
                        providers_str = ' or '.join(provider_names)

                        raise serializers.ValidationError(
                            _(
                                "This email is already registered "
                                "via %(providers)s. "
                                "Please use %(providers)s to "
                                "login instead."
                            ) % {'providers': providers_str}
                        )
                    else:
                        raise serializers.ValidationError(
                            _(
                                "This email address is already "
                                "registered. Please login instead."
                            )
                        )
            except Profile.DoesNotExist:
                pass

        except User.DoesNotExist:
            pass

        return value


class VirtualEmailUsernameSerializer(serializers.Serializer):
    """
    Serializer for validating virtual email username.
    """
    username = serializers.CharField(
        min_length=3,
        max_length=64,
        required=True,
        help_text=_(
            "Virtual email username "
            "(will become username@domain)"
        )
    )

    def validate_username(self, value):
        """
        Validate virtual email username format and uniqueness.
        """
        return validate_virtual_email_username(value)


class CompleteRegistrationSerializer(serializers.Serializer):
    """
    Serializer for completing user registration.
    """
    token = serializers.CharField(
        required=True,
        help_text=_("Registration verification token")
    )

    password = serializers.CharField(
        min_length=8,
        max_length=32,
        write_only=True,
        style={'input_type': 'password'},
        help_text=_(
            "User password (8-32 characters, "
            "must contain letters and numbers)"
        )
    )

    virtual_email_username = serializers.CharField(
        min_length=3,
        max_length=64,
        required=True,
        help_text=_("Virtual email username")
    )

    scene = serializers.CharField(
        required=False,
        help_text=_(
            "User's selected scene "
            "(e.g., 'chat', 'product_issue')"
        )
    )

    language = serializers.CharField(
        required=True,
        help_text=_(
            "Specifies the language used by AI when generating "
            "summaries, titles, and metadata."
        )
    )

    timezone = serializers.CharField(
        required=True,
        help_text=_(
            "User's timezone "
            "(e.g., 'UTC', 'Asia/Shanghai')"
        )
    )

    def validate_password(self, value):
        """
        Validate password strength: 8-32 characters,
        must contain letters and numbers.
        """
        return validate_password_strength(value)

    def validate_virtual_email_username(self, value):
        """
        Validate virtual email username.

        Reuse validation logic from VirtualEmailUsernameSerializer.
        """
        username_serializer = VirtualEmailUsernameSerializer(
            data={'username': value}
        )

        if not username_serializer.is_valid():
            raise serializers.ValidationError(
                username_serializer.errors['username']
            )

        return username_serializer.validated_data['username']

    def validate_language(self, value):
        """
        Normalize language to supported value.
        """
        return normalize_language_code(value)


class CompleteGoogleSetupSerializer(serializers.Serializer):
    """
    Serializer for completing Google user setup.

    Google users are already authenticated via OAuth,
    so they don't need to provide a password.
    They only need to complete virtual email and preferences setup.
    """

    virtual_email_username = serializers.CharField(
        min_length=3,
        max_length=64,
        required=True,
        help_text=_("Virtual email username")
    )

    scene = serializers.CharField(
        required=False,
        help_text=_("User's selected scene")
    )

    language = serializers.CharField(
        required=True,
        help_text=_(
            "Specifies the language used by AI when generating "
            "summaries, titles, and metadata."
        )
    )

    timezone = serializers.CharField(
        required=True,
        help_text=_("User's timezone")
    )

    def validate_scene(self, value):
        """
        Validate scene is valid.
        """
        if not value:
            return None
        return value

    def validate_virtual_email_username(self, value):
        """
        Validate virtual email username.

        Reuse validation logic from VirtualEmailUsernameSerializer.
        """
        username_serializer = VirtualEmailUsernameSerializer(
            data={'username': value}
        )

        if not username_serializer.is_valid():
            raise serializers.ValidationError(
                username_serializer.errors['username']
            )

        return username_serializer.validated_data['username']

    def validate_language(self, value):
        """
        Normalize language to supported value.
        """
        return normalize_language_code(value)


class UserDetailsSerializer(serializers.ModelSerializer):
    """
    Custom user details serializer for dj-rest-auth.
    Includes virtual email address from EmailAlias and profile information.
    Also includes authentication method information and password change
    capability.
    """
    display_name = serializers.SerializerMethodField(
        read_only=True,
        help_text=_(
            "User-friendly display name, prioritizing "
            "first_name + last_name from OAuth providers, "
            "falling back to username"
        )
    )

    virtual_email = serializers.SerializerMethodField(
        read_only=True,
        help_text=_(
            "Primary virtual email address for receiving emails"
        )
    )

    profile = serializers.SerializerMethodField(
        help_text=_("User profile information")
    )
    profile_language = serializers.CharField(
        write_only=True,
        required=False,
        help_text=_(
            "User's preferred language for AI generation "
            "and backend logic (not UI display)"
        )
    )
    profile_timezone = serializers.CharField(
        write_only=True,
        required=False,
        help_text=_(
            "User's timezone for backend logic "
            "and date/time display"
        )
    )

    auth_info = serializers.SerializerMethodField(
        read_only=True,
        help_text=_("Authentication method and related information")
    )
    groups = serializers.SerializerMethodField(
        read_only=True,
        help_text=_("Current group memberships"),
    )
    access_profile = serializers.SerializerMethodField(
        read_only=True,
        help_text=_("Resolved platform visibility and landing route"),
    )
    roles = serializers.SerializerMethodField(
        read_only=True,
        help_text=_("Effective roles resolved from direct and group bindings."),
    )
    auth_source = serializers.SerializerMethodField(read_only=True)
    ldap_last_synced_at = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'display_name',
            'virtual_email',
            'profile',
            'profile_language',
            'profile_timezone',
            'auth_info',
            'groups',
            'is_staff',
            'roles',
            'access_profile',
            'auth_source',
            'ldap_last_synced_at',
        ]
        read_only_fields = [
            'id',
            'username',
            'email',
            'virtual_email',
            'profile',
            'auth_info',
            'display_name',
            'groups',
            'is_staff',
            'roles',
            'access_profile',
        ]

    def get_display_name(self, obj):
        """Get a user-friendly display name."""
        return build_display_name(obj)

    def get_virtual_email(self, obj):
        """Get the primary virtual email address for the user."""
        return get_virtual_email(obj)

    def get_profile(self, obj):
        """Get user profile information."""
        try:
            profile = obj.profile
        except Profile.DoesNotExist:
            profile = None
        return build_profile_snapshot(profile)

    def get_auth_info(self, obj):
        """Get authentication method information."""
        return build_auth_info(obj)

    def get_auth_source(self, obj):
        try:
            profile = obj.profile
        except Profile.DoesNotExist:
            profile = None
        if profile is not None and profile.auth_source == Profile.AUTH_SOURCE_LDAP:
            return Profile.AUTH_SOURCE_LDAP
        social_accounts = SocialAccount.objects.filter(user=obj)
        if social_accounts.exists():
            return Profile.AUTH_SOURCE_OAUTH
        return getattr(profile, "auth_source", Profile.AUTH_SOURCE_LOCAL)

    def get_ldap_last_synced_at(self, obj):
        try:
            profile = obj.profile
        except Profile.DoesNotExist:
            return None
        if profile.ldap_last_synced_at is None:
            return None
        return profile.ldap_last_synced_at.isoformat()

    def get_groups(self, obj):
        """Serialize Django group memberships."""
        return [
            self._serialize_group(group)
            for group in obj.groups.select_related(
                'jenkins_notification_config'
            ).order_by('name')
        ]

    @staticmethod
    def _serialize_group(group):
        try:
            notification_config = group.jenkins_notification_config
        except Exception:
            notification_config = None
        return {
            'id': group.pk,
            'name': group.name,
            'jenkins_notification_settings': {
                'notification_emails': (
                    getattr(notification_config, 'notification_emails', [])
                    or []
                ),
                'notification_webhooks': (
                    getattr(notification_config, 'notification_webhooks', [])
                    or []
                ),
            },
        }

    def get_roles(self, obj):
        """Serialize effective roles for the current user."""
        effective_roles = get_effective_roles(obj)
        return [
            {
                'id': role.pk,
                'name': role.name,
                'visible_features': normalize_feature_keys(
                    role.visible_features
                ),
                'preferred_platform': normalize_platform_key(
                    role.preferred_platform
                ),
                'is_active': role.is_active,
            }
            for role in effective_roles
        ]

    def get_access_profile(self, obj):
        """Serialize resolved access information for the current user."""
        return get_access_profile(obj)

    def update(self, instance, validated_data):
        """
        Update user instance and profile language/timezone if provided.
        """
        profile_language = validated_data.pop('profile_language', None)
        profile_timezone = validated_data.pop('profile_timezone', None)
        notification_strategy = self.initial_data.get(
            'jenkins_notification_strategy'
        )
        notification_emails = self.initial_data.get(
            'jenkins_notification_emails'
        )
        notification_webhooks = self.initial_data.get(
            'jenkins_notification_webhooks'
        )

        # Update user fields
        instance = super().update(instance, validated_data)

        if profile_language is not None or profile_timezone is not None:
            profile, _ = upsert_profile_preferences(
                instance,
                profile_model=Profile,
                profile_language=profile_language,
                profile_timezone=profile_timezone,
            )
        else:
            profile, _ = Profile.objects.get_or_create(
                user=instance,
                defaults={
                    'language': 'zh-CN',
                    'timezone': 'Asia/Shanghai',
                },
            )

        update_fields = []
        if notification_strategy is not None:
            profile.jenkins_notification_strategy = str(notification_strategy)
            update_fields.append('jenkins_notification_strategy')
        if notification_emails is not None:
            profile.jenkins_notification_emails = [
                str(email).strip()
                for email in notification_emails
                if str(email).strip()
            ]
            update_fields.append('jenkins_notification_emails')
        if notification_webhooks is not None:
            profile.jenkins_notification_webhooks = [
                str(url).strip()
                for url in notification_webhooks
                if str(url).strip()
            ]
            update_fields.append('jenkins_notification_webhooks')

        if update_fields:
            profile.save(update_fields=update_fields)
        return instance


class CustomPasswordResetSerializer(serializers.Serializer):
    """
    Custom password reset serializer that only allows email-registered users.
    OAuth users are rejected with appropriate error message.
    """
    email = serializers.EmailField()

    def validate_email(self, value):
        """
        Validate that the email belongs to an email-registered user.
        """
        user = get_password_reset_eligible_user(value)
        self.user = user
        return user.email.lower().strip()
