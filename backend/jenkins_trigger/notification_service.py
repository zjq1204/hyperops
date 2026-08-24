"""Jenkins notification resolution and delivery helpers."""

from __future__ import annotations

import logging

from django.contrib.auth.models import Group

logger = logging.getLogger(__name__)

SOURCE_LABELS = {
    "user": "个人配置",
    "group": "群组配置",
    "group_fallback": "群组兜底",
    "user_and_group": "个人 + 群组",
    "none": "未命中配置",
}


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys([value for value in values if value]))


def _merge_group_after_user(
    user_values: list[str], group_values: list[str]
) -> list[str]:
    group_set = set(group_values)
    user_only = [value for value in user_values if value not in group_set]
    return _dedupe(user_only + group_values)


def get_user_notification_channels(user) -> dict[str, list[str]]:
    profile = user.profile
    return {
        "emails": _dedupe(
            [getattr(user, "email", "")] + list(profile.jenkins_notification_emails or [])
        ),
        "webhooks": _dedupe(list(profile.jenkins_notification_webhooks or [])),
    }


def get_group_notification_channels(user) -> dict[str, list[str]]:
    groups = (
        Group.objects.filter(user=user)
        .select_related("jenkins_notification_config")
        .order_by("name")
    )
    emails: list[str] = []
    webhooks: list[str] = []
    group_names: list[str] = []
    for group in groups:
        config = getattr(group, "jenkins_notification_config", None)
        if config is None:
            continue
        group_names.append(group.name)
        emails.extend(config.notification_emails or [])
        webhooks.extend(config.notification_webhooks or [])
    return {
        "group_names": group_names,
        "emails": _dedupe(emails),
        "webhooks": _dedupe(webhooks),
    }


def resolve_notification_targets(user, entry) -> dict[str, object]:
    user_channels = get_user_notification_channels(user)
    group_channels = get_group_notification_channels(user)
    preference = entry.user_notification_preferences.filter(user=user).first()
    if preference is None:
        return {
            "source": "none",
            "emails": [],
            "webhooks": [],
            "group_names": group_channels["group_names"],
            "selected_channels": [],
        }

    emails: list[str] = []
    webhooks: list[str] = []
    selected_channels: list[str] = []
    if preference.notify_personal_email:
        emails.extend(user_channels["emails"])
        selected_channels.append("personal_email")
    if preference.notify_personal_webhook:
        webhooks.extend(user_channels["webhooks"])
        selected_channels.append("personal_webhook")
    if preference.notify_group_email:
        emails.extend(group_channels["emails"])
        selected_channels.append("group_email")
    if preference.notify_group_webhook:
        webhooks.extend(group_channels["webhooks"])
        selected_channels.append("group_webhook")

    return {
        "source": "entry_channels" if selected_channels else "none",
        "emails": _merge_group_after_user(user_channels["emails"], group_channels["emails"])
        if preference.notify_personal_email and preference.notify_group_email
        else _dedupe(emails),
        "webhooks": _merge_group_after_user(user_channels["webhooks"], group_channels["webhooks"])
        if preference.notify_personal_webhook and preference.notify_group_webhook
        else _dedupe(webhooks),
        "group_names": group_channels["group_names"],
        "selected_channels": selected_channels,
    }


def build_notification_result(user, entry, sent_at_iso: str) -> dict[str, object]:
    resolved = resolve_notification_targets(user, entry)
    email_status = "sent" if resolved["emails"] else "skipped"
    webhook_status = "sent" if resolved["webhooks"] else "skipped"
    return {
        **resolved,
        "sent_at": sent_at_iso,
        "email_status": email_status,
        "webhook_status": webhook_status,
        "summary": (
            f"{'入口通知' if resolved['source'] == 'entry_channels' else SOURCE_LABELS[resolved['source']]} · "
            f"{len(resolved['emails'])} 邮箱 / {len(resolved['webhooks'])} Webhook"
        ),
    }


def deliver_build_notifications(record, status_text: str) -> None:
    """Send configured notifications for a completed build."""
    notification_result = record.notification_result or {}
    emails = list(notification_result.get("emails") or [])
    webhooks = list(notification_result.get("webhooks") or [])
    if not emails and not webhooks:
        return

    try:
        from agentcore_notifier.adapters.django.services.email_service import (
            EmailService,
        )
        from agentcore_notifier.adapters.django.services.webhook_service import (
            WebhookService,
            build_text_payload,
        )
    except ImportError:
        logger.warning(
            "Jenkins 通知已降级 | integration=agentcore_notifier "
            "operation=send_notification reason_code=NOTIFIER_UNAVAILABLE"
        )
        return

    username = record.user.username if record.user else "未知"
    triggered_at = (
        record.triggered_at.strftime("%Y-%m-%d %H:%M:%S")
        if record.triggered_at
        else "-"
    )
    body = (
        "Jenkins 构建通知\n"
        f"项目: {record.entry.name}\n"
        f"Job: {record.entry.job_name}\n"
        f"Build: #{record.build_number}\n"
        f"状态: {status_text}\n"
        f"触发人: {username}\n"
        f"时间: {triggered_at}"
    )
    if record.artifacts:
        body += "\n产物:\n" + "\n".join(
            f"- {artifact.get('name') or artifact.get('path') or 'unknown'}"
            for artifact in record.artifacts
        )

    if emails:
        EmailService().send(
            subject=f"[HyperOps] Jenkins 构建{status_text}: {record.entry.name}",
            body=body,
            to=emails,
            source_app="hyperops",
            source_type="jenkins_build",
            source_id=str(record.id),
            user=record.user,
        )

    if webhooks:
        webhook_service = WebhookService()
        for webhook_url in webhooks:
            webhook_service.send(
                payload=build_text_payload("feishu", body),
                provider_type="feishu",
                source_app="hyperops",
                source_type="jenkins_build",
                source_id=str(record.id),
                user=record.user,
                channel_config={"url": webhook_url, "provider_type": "feishu"},
            )
