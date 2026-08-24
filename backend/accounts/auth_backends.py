"""Authentication backends for local, OAuth, and LDAP users."""

from __future__ import annotations

import logging

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db import IntegrityError

from accounts.models import LdapAuthConfig, Profile
from accounts.services.ldap_client import (
    LdapServiceError,
    authenticate_ldap_user,
)
from accounts.services.ldap_sync import (
    build_ldap_local_username,
    create_ldap_user,
    sync_ldap_user,
)

User = get_user_model()
logger = logging.getLogger(__name__)


def _set_auth_error(request, *, code, detail):
    if request is not None:
        request._auth_error = {"code": code, "detail": detail}


class DirectoryAwareBackend(ModelBackend):
    """Authenticate local users locally and LDAP users against the directory."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        resolved_username = (username or kwargs.get(User.USERNAME_FIELD) or "").strip()
        if not resolved_username or password is None:
            return None

        auth_source = kwargs.get("auth_source") or Profile.AUTH_SOURCE_LOCAL
        if auth_source == Profile.AUTH_SOURCE_LDAP:
            return self._authenticate_selected_ldap(
                request,
                resolved_username,
                password,
                kwargs.get("ldap_instance_id"),
            )

        identifier = resolved_username
        user = (
            User.objects.select_related("profile")
            .filter(username=identifier)
            .first()
        )
        if user is None and "@" in identifier:
            user = (
                User.objects.select_related("profile")
                .filter(email__iexact=identifier)
                .first()
            )

        if user is None:
            _set_auth_error(
                request,
                code="local_auth_failed",
                detail="The local account does not exist.",
            )
            return None

        profile = getattr(user, "profile", None)
        user_auth_source = (
            profile.auth_source
            if profile is not None
            else Profile.AUTH_SOURCE_LOCAL
        )

        if user_auth_source == Profile.AUTH_SOURCE_LDAP:
            _set_auth_error(
                request,
                code="ldap_auth_required",
                detail="Select the LDAP provider for this directory account.",
            )
            return None

        local_user = super().authenticate(
            request,
            username=user.get_username(),
            password=password,
            **kwargs,
        )
        if local_user is not None:
            return local_user

        _set_auth_error(
            request,
            code="local_auth_failed",
            detail="The local account password is incorrect.",
        )
        return None

    def _authenticate_selected_ldap(
        self,
        request,
        username,
        password,
        ldap_instance_id,
    ):
        try:
            ldap_config = LdapAuthConfig.objects.get(
                pk=ldap_instance_id,
                enabled=True,
            )
        except (LdapAuthConfig.DoesNotExist, TypeError, ValueError):
            _set_auth_error(
                request,
                code="ldap_config_unavailable",
                detail="LDAP login is not configured or currently disabled.",
            )
            return None

        try:
            ldap_record = authenticate_ldap_user(ldap_config, username, password)
        except LdapServiceError as exc:
            logger.warning(
                "LDAP 认证服务不可用 | operation=authenticate "
                "ldap_instance_id=%s error_code=%s error_type=%s",
                ldap_config.id,
                exc.code,
                type(exc).__name__,
            )
            _set_auth_error(request, code=exc.code, detail=exc.detail)
            return None
        if ldap_record is None:
            _set_auth_error(
                request,
                code="ldap_auth_failed",
                detail="LDAP authentication failed for the supplied uid.",
            )
            return None

        user = (
            User.objects.select_related("profile")
            .filter(
                profile__auth_source=Profile.AUTH_SOURCE_LDAP,
                profile__ldap_instance=ldap_config,
                profile__ldap_uid=ldap_record.username,
            )
            .first()
        )
        if user is not None:
            sync_ldap_user(user, ldap_record, ldap_config)
            return user if self.user_can_authenticate(user) else None

        local_username = build_ldap_local_username(ldap_config, ldap_record.username)
        if User.objects.filter(username=local_username).exists():
            _set_auth_error(
                request,
                code="ldap_account_conflict",
                detail=(
                    "A local account already uses this username. "
                    "Rename or reconcile the local account first."
                ),
            )
            return None

        try:
            created_user = create_ldap_user(ldap_record, ldap_config)
        except IntegrityError:
            _set_auth_error(
                request,
                code="ldap_account_conflict",
                detail=(
                    "A local account already uses this username. "
                    "Rename or reconcile the local account first."
                ),
            )
            return None

        return created_user if self.user_can_authenticate(created_user) else None
