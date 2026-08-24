"""
Django signals for automatic user setup

This module provides signals to automatically create EmailAlias and
Profile when a user is created, regardless of how the user was created
(Django admin, API, management commands, etc.)
"""

import logging

from django.contrib.auth.models import Group, User
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from accounts.models import GroupNotificationConfig, Profile

# Note: EmailAlias is from threadline
# If you have EmailAlias, import it here:
try:
    from threadline.models import EmailAlias
except ImportError:
    EmailAlias = None

logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def create_user_resources(sender, instance, created, **kwargs):
    """
    Automatically create EmailAlias and Profile when a user is created

    This signal ensures that all users have the necessary resources
    regardless of how they were created (Django admin, API, etc.)
    """
    if not created:
        return

    try:
        with transaction.atomic():
            create_email_alias(instance)
            create_profile(instance)
    except Exception as e:
        logger.warning(
            "用户关联资源创建失败 | operation=create_user_resources "
            "user_id=%s error_type=%s",
            instance.id,
            type(e).__name__,
            exc_info=True,
        )


@receiver(post_save, sender=Group)
def create_group_notification_config(sender, instance, created, **kwargs):
    """Ensure every group has a Jenkins notification config row."""
    if not created:
        return

    try:
        GroupNotificationConfig.objects.get_or_create(group=instance)
    except Exception as exc:
        logger.warning(
            "用户组通知配置创建失败 | operation=create_group_notification_config "
            "group_id=%s error_type=%s",
            instance.id,
            type(exc).__name__,
        )


def create_email_alias(user):
    """
    Create EmailAlias for user if it doesn't exist.

    Only creates EmailAlias for users who have completed registration.
    This prevents temporary users (created during registration token
    generation) from reserving email aliases that users might want
    to use later.

    Note: Temporary users have registration_completed=False and will
    be deleted when user completes registration. We don't want to
    create EmailAlias for them as it would block the desired username.
    """
    if EmailAlias is None:
        return None

    try:
        try:
            profile = user.profile
            if not profile.registration_completed:
                return None
        except Profile.DoesNotExist:
            return None

        existing_alias = EmailAlias.objects.filter(
            user=user,
            is_active=True
        ).first()

        if existing_alias:
            return existing_alias

        if EmailAlias.objects.filter(alias=user.username).exists():
            return None

        alias = EmailAlias.objects.create(
            user=user,
            alias=user.username,
            is_active=True
        )
        return alias
    except Exception as e:
        logger.warning(
            "用户邮件别名创建失败 | operation=create_email_alias "
            "user_id=%s error_type=%s",
            user.id,
            type(e).__name__,
        )
        return None


def create_profile(user):
    """
    Create Profile for user if it doesn't exist
    """
    if Profile is None:
        return None

    try:
        profile, _ = Profile.objects.get_or_create(
            user=user,
            defaults={
                'registration_completed': False,
                'language': 'zh-CN',
                'timezone': 'Asia/Shanghai'
            }
        )
        return profile
    except Exception as e:
        logger.warning(
            "用户资料创建失败 | operation=create_profile user_id=%s error_type=%s",
            user.id,
            type(e).__name__,
        )
        return None
