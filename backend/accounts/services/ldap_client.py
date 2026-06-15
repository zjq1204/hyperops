"""LDAP connection and directory query helpers."""

from __future__ import annotations

from typing import Any

from ldap3 import ALL, Connection, Server, Tls
from ldap3.core.exceptions import LDAPException

from accounts.models import LdapAuthConfig
from accounts.services.ldap_sync import LdapUserRecord, preview_mapped_groups


class LdapServiceError(Exception):
    """Typed LDAP service error with API-facing code and detail."""

    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail


def _get_default_config():
    return LdapAuthConfig.objects.order_by("-is_default", "id").first()


def resolve_runtime_config(
    config: LdapAuthConfig | None = None,
    overrides: dict[str, Any] | None = None,
    *,
    require_enabled: bool = True,
):
    """Resolve runtime LDAP settings from persisted config plus request overrides."""
    if isinstance(config, dict) and overrides is None:
        overrides = config
        config = None

    config = config or _get_default_config()
    if require_enabled and (config is None or not config.enabled):
        raise LdapServiceError(
            "ldap_config_unavailable",
            "LDAP login is not configured or currently disabled.",
        )

    merged = config.to_runtime_settings() if config is not None else {}
    if overrides:
        candidate = dict(overrides)
        if (
            config is not None
            and not candidate.get("bind_password")
            and config.has_bind_password
        ):
            candidate["bind_password"] = config.get_bind_password()
        merged.update(candidate)
    return merged


def _build_server(runtime_config):
    use_ssl = bool(runtime_config.get("use_ssl"))
    tls = None
    if use_ssl:
        # Default to strict certificate validation for LDAPS. Operators can opt
        # out by explicitly setting ``tls_require_cert=False`` for ad-hoc dev
        # environments. The CA bundle comes from ``tls_ca_bundle`` when set,
        # otherwise we rely on the system trust store.
        import ssl

        require_cert = bool(runtime_config.get("tls_require_cert", True))
        validate = ssl.CERT_REQUIRED if require_cert else ssl.CERT_NONE
        tls_kwargs = {"validate": validate}
        ca_bundle = runtime_config.get("tls_ca_bundle")
        if ca_bundle:
            tls_kwargs["ca_certs_file"] = ca_bundle
        tls = Tls(**tls_kwargs)
    return Server(
        runtime_config.get("host"),
        port=int(runtime_config.get("port") or (636 if use_ssl else 389)),
        use_ssl=use_ssl,
        get_info=ALL,
        tls=tls,
    )


def _create_connection(runtime_config, *, user=None, password=None):
    bind_user = user if user is not None else runtime_config.get("bind_dn") or None
    bind_password = (
        password
        if password is not None
        else runtime_config.get("bind_password") or None
    )
    connection = Connection(
        _build_server(runtime_config),
        user=bind_user,
        password=bind_password,
        auto_bind=False,
        raise_exceptions=True,
    )
    connection.open()
    if runtime_config.get("start_tls") and not runtime_config.get("use_ssl"):
        connection.start_tls()
    connection.bind()
    return connection



def _escape_ldap_filter(value):
    """Escape user-supplied values before substituting them into LDAP filters.

    Uses :func:`ldap3.utils.conv.escape_filter_chars` to neutralise the four
    RFC 4515 metacharacters (``\\*``、``\\(``、``\\)``、``\\\\``、``\\\\``).
    Any ``None`` values fall back to an empty string so the formatted filter
    never contains the literal word ``None``.
    """
    from ldap3.utils.conv import escape_filter_chars

    if value is None:
        return ""
    return escape_filter_chars(str(value))


def _entry_value(entry, attribute_name):
    try:
        value = entry[attribute_name].value
    except Exception:
        return ""
    if isinstance(value, list):
        return value[0] if value else ""
    return value or ""


def _build_user_record(runtime_config, entry, username):
    uid_attr = runtime_config.get("uid_attr") or "uid"
    email_attr = runtime_config.get("email_attr") or "mail"
    first_name_attr = runtime_config.get("first_name_attr") or "givenName"
    last_name_attr = runtime_config.get("last_name_attr") or "sn"
    display_name_attr = runtime_config.get("display_name_attr") or "displayName"

    return LdapUserRecord(
        username=_entry_value(entry, uid_attr) or username,
        dn=str(entry.entry_dn),
        email=_entry_value(entry, email_attr),
        first_name=_entry_value(entry, first_name_attr),
        last_name=_entry_value(entry, last_name_attr),
        display_name=_entry_value(entry, display_name_attr),
        group_dns=[],
    )


def _search_user(service_connection, runtime_config, username):
    attributes = list(
        dict.fromkeys(
            [
                runtime_config.get("uid_attr") or "uid",
                runtime_config.get("email_attr") or "mail",
                runtime_config.get("first_name_attr") or "givenName",
                runtime_config.get("last_name_attr") or "sn",
                runtime_config.get("display_name_attr") or "displayName",
            ]
        )
    )
    service_connection.search(
        search_base=runtime_config.get("user_base_dn") or "",
        search_filter=(
            runtime_config.get("user_filter_template")
            or "(&(objectClass=person)(uid={username}))"
        ).format(username=_escape_ldap_filter(username)),
        attributes=attributes,
    )
    if not service_connection.entries:
        return None
    return _build_user_record(runtime_config, service_connection.entries[0], username)


def _search_group_dns(service_connection, runtime_config, username, user_dn):
    group_base_dn = runtime_config.get("group_base_dn") or ""
    if not group_base_dn:
        return []
    group_filter = (
        runtime_config.get("group_filter_template")
        or "(&(objectClass=groupOfNames)(member={user_dn}))"
    ).format(
        username=_escape_ldap_filter(username),
        user_dn=_escape_ldap_filter(user_dn),
    )
    service_connection.search(
        search_base=group_base_dn,
        search_filter=group_filter,
        attributes=["distinguishedName"],
    )
    return [str(entry.entry_dn) for entry in service_connection.entries]


def authenticate_ldap_user(config, username, password):
    """Authenticate a user against LDAP and return normalized directory data."""
    if not password:
        return None
    runtime_config = resolve_runtime_config(config)
    try:
        with _create_connection(runtime_config) as service_connection:
            record = _search_user(service_connection, runtime_config, username)
            if record is None:
                return None
            record.group_dns = _search_group_dns(
                service_connection,
                runtime_config,
                username,
                record.dn,
            )

        with _create_connection(
            runtime_config,
            user=record.dn,
            password=password,
        ):
            return record
    except LDAPException as exc:
        message = str(exc)
        lower_message = message.lower()
        if "invalidcredentials" in lower_message or "invalid credentials" in lower_message:
            return None
        raise LdapServiceError("ldap_config_unavailable", message) from exc


def test_ldap_connection(config=None, overrides=None):
    """Test whether the current LDAP settings can connect and bind."""
    if isinstance(config, dict) and overrides is None:
        overrides = config
        config = None
    runtime_config = resolve_runtime_config(
        config,
        overrides,
        require_enabled=False,
    )
    try:
        with _create_connection(runtime_config) as service_connection:
            base_dns_checked = []
            for base_dn in [
                runtime_config.get("user_base_dn") or "",
                runtime_config.get("group_base_dn") or "",
            ]:
                if not base_dn:
                    continue
                service_connection.search(
                    search_base=base_dn,
                    search_filter="(objectClass=*)",
                    attributes=["objectClass"],
                    size_limit=1,
                )
                base_dns_checked.append(base_dn)
            return {
                "reachable": True,
                "bind_succeeded": True,
                "base_dns_checked": base_dns_checked,
            }
    except LDAPException as exc:
        raise LdapServiceError("ldap_config_unavailable", str(exc)) from exc


def preview_ldap_user(username, config=None, overrides=None):
    """Preview LDAP user attributes and group mappings without local writes."""
    if isinstance(config, dict) and overrides is None:
        overrides = config
        config = None
    runtime_config = resolve_runtime_config(
        config,
        overrides,
        require_enabled=False,
    )
    try:
        with _create_connection(runtime_config) as service_connection:
            record = _search_user(service_connection, runtime_config, username)
            if record is None:
                raise LdapServiceError(
                    "ldap_user_not_found",
                    "No LDAP user matched the supplied uid.",
                )
            record.group_dns = _search_group_dns(
                service_connection,
                runtime_config,
                username,
                record.dn,
            )
        mapped_groups = preview_mapped_groups(record.group_dns, config)
        return {
            "user": record,
            "mapped_groups": [
                {"id": group.id, "name": group.name}
                for group in mapped_groups
            ],
        }
    except LdapServiceError:
        raise
    except LDAPException as exc:
        raise LdapServiceError("ldap_config_unavailable", str(exc)) from exc
