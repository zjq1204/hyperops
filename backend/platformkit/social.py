"""Shared social-account lookup and provider-display helpers."""

from __future__ import annotations

from allauth.socialaccount import providers
from allauth.socialaccount.models import SocialAccount

PROVIDER_NAME_MAP = {
    "google": "Google",
    "github": "GitHub",
    "facebook": "Facebook",
    "twitter": "Twitter",
}


def get_social_accounts(user):
    """Return all linked social accounts for a user."""
    return SocialAccount.objects.filter(user=user)


def get_social_account(user, provider: str):
    """Return a linked social account for a specific provider, if any."""
    return get_social_accounts(user).filter(provider=provider).first()


def get_primary_social_account(user, *, social_accounts=None):
    """Return the first linked social account for auth display purposes."""
    resolved_accounts = social_accounts
    if resolved_accounts is None:
        resolved_accounts = get_social_accounts(user)
    return resolved_accounts.first()


def has_provider(user, provider: str) -> bool:
    """Return whether the user has linked the given provider."""
    return get_social_accounts(user).filter(provider=provider).exists()


def get_provider_uid(user, provider: str):
    """Return the provider UID when a linked account exists."""
    account = get_social_account(user, provider)
    return account.uid if account else None


def get_provider_display_name(provider_id: str) -> str:
    """Resolve a human-friendly provider name with registry fallback."""
    if provider_id in PROVIDER_NAME_MAP:
        return PROVIDER_NAME_MAP[provider_id]

    try:
        provider_class = providers.registry.by_id(provider_id)
        return provider_class.name
    except Exception:
        return str(provider_id).title()


def get_social_provider_names(accounts) -> list[str]:
    """Return display names for a collection of social accounts."""
    return [get_provider_display_name(account.provider) for account in accounts]


def build_social_login_identifier(account) -> str:
    """Build a human-friendly login identifier for an OAuth account."""
    provider_name = get_provider_display_name(account.provider)
    provider_email = account.extra_data.get("email")
    return f"{provider_name} ({provider_email or account.uid})"
