from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import override_settings
from rest_framework.test import APIClient

from accounts.models import LdapAuthConfig, LdapGroupMapping
from accounts.services.ldap_client import (
    LdapServiceError,
    test_ldap_connection as run_ldap_connection_test,
)
from accounts.services.ldap_sync import LdapUserRecord

User = get_user_model()


def _payload(response):
    body = response.json()
    if isinstance(body, dict) and "data" in body:
        return body["data"]
    return body


class _FakeLdapConnection:
    def __init__(self, entries=None):
        self.search_calls = []
        self.entries = entries or []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def search(self, **kwargs):
        self.search_calls.append(kwargs)
        return True


@pytest.mark.django_db
class TestLdapManagementApi:
    @pytest.fixture(autouse=True)
    def _settings(self, settings):
        settings.ROOT_URLCONF = "accounts.urls"

    def test_config_round_trip_masks_bind_password(self):
        admin = User.objects.create_user(
            username="ldap-admin",
            password="password123",
            is_staff=True,
        )
        client = APIClient()
        client.force_authenticate(user=admin)

        put_response = client.put(
            "/api/v1/management/ldap/config/",
            {
                "enabled": True,
                "host": "ldap.example.com",
                "port": 636,
                "use_ssl": True,
                "start_tls": False,
                "bind_dn": "uid=svc,ou=system,dc=example,dc=com",
                "bind_password": "super-secret",
                "user_base_dn": "ou=people,dc=example,dc=com",
                "user_filter_template": "(&(objectClass=person)(uid={username}))",
                "group_base_dn": "ou=groups,dc=example,dc=com",
                "group_filter_template": "(&(objectClass=groupOfNames)(member={user_dn}))",
                "uid_attr": "uid",
                "email_attr": "mail",
                "first_name_attr": "givenName",
                "last_name_attr": "sn",
                "display_name_attr": "displayName",
            },
            format="json",
        )

        assert put_response.status_code == 200
        config = LdapAuthConfig.objects.get()
        assert config.bind_password_encrypted
        assert config.get_bind_password() == "super-secret"

        get_response = client.get("/api/v1/management/ldap/config/")
        assert get_response.status_code == 200
        data = _payload(get_response)
        assert data["host"] == "ldap.example.com"
        assert data["has_bind_password"] is True
        assert "bind_password" not in data

    def test_ldap_instances_crud_and_public_providers(self):
        admin = User.objects.create_user(
            username="ldap-admin-instances",
            password="password123",
            is_staff=True,
        )
        client = APIClient()
        client.force_authenticate(user=admin)

        create_a = client.post(
            "/api/v1/management/ldap/instances/",
            {
                "name": "OneProCloud LDAP",
                "slug": "oneprocloud",
                "enabled": True,
                "host": "ldap.oneprocloud.example",
                "port": 389,
            },
            format="json",
        )
        create_b = client.post(
            "/api/v1/management/ldap/instances/",
            {
                "name": "Disabled LDAP",
                "slug": "disabled",
                "enabled": False,
                "host": "ldap-disabled.example",
                "port": 389,
            },
            format="json",
        )

        assert create_a.status_code == 201
        assert create_b.status_code == 201
        list_response = client.get("/api/v1/management/ldap/instances/")
        assert list_response.status_code == 200
        list_payload = _payload(list_response)
        assert [item["slug"] for item in list_payload["results"]] == [
            "oneprocloud",
            "disabled",
        ]

        public_client = APIClient()
        providers_response = public_client.get("/api/v1/auth/ldap-providers")
        assert providers_response.status_code == 200
        providers = _payload(providers_response)
        assert providers == [
            {
                "id": _payload(create_a)["id"],
                "name": "OneProCloud LDAP",
                "slug": "oneprocloud",
            }
        ]

    @override_settings(
        LDAP_CONFIG_ENCRYPTION_KEY="",
        SECRET_KEY="fallback-secret-for-ldap-tests",
    )
    def test_config_save_uses_secret_key_when_ldap_key_is_unset(self):
        admin = User.objects.create_user(
            username="ldap-admin-fallback-key",
            password="password123",
            is_staff=True,
        )
        client = APIClient()
        client.force_authenticate(user=admin)

        response = client.put(
            "/api/v1/management/ldap/config/",
            {
                "enabled": True,
                "host": "ldap.example.com",
                "port": 389,
                "bind_dn": "uid=svc,ou=system,dc=example,dc=com",
                "bind_password": "super-secret",
            },
            format="json",
        )

        assert response.status_code == 200
        config = LdapAuthConfig.objects.get()
        assert config.bind_password_encrypted
        assert config.get_bind_password() == "super-secret"

    @patch("accounts.views.ldap.test_ldap_connection")
    def test_test_connection_returns_preview(self, mock_test_connection):
        admin = User.objects.create_user(
            username="ldap-admin-connection",
            password="password123",
            is_staff=True,
        )
        client = APIClient()
        client.force_authenticate(user=admin)
        mock_test_connection.return_value = {
            "reachable": True,
            "bind_succeeded": True,
            "base_dns_checked": [
                "ou=people,dc=example,dc=com",
                "ou=groups,dc=example,dc=com",
            ],
        }

        response = client.post("/api/v1/management/ldap/test-connection/", {}, format="json")

        assert response.status_code == 200
        data = _payload(response)
        assert data["reachable"] is True
        assert data["bind_succeeded"] is True

    @patch("accounts.views.ldap.test_ldap_connection")
    def test_test_connection_failure_returns_preview_payload(self, mock_test_connection):
        admin = User.objects.create_user(
            username="ldap-admin-connection-failure",
            password="password123",
            is_staff=True,
        )
        client = APIClient()
        client.force_authenticate(user=admin)
        mock_test_connection.side_effect = LdapServiceError(
            "ldap_config_unavailable",
            "LDAP server is not reachable.",
        )

        response = client.post(
            "/api/v1/management/ldap/test-connection/",
            {},
            format="json",
        )

        assert response.status_code == 200
        data = _payload(response)
        assert data["reachable"] is False
        assert data["bind_succeeded"] is False
        assert data["base_dns_checked"] == []
        assert data["code"] == "ldap_config_unavailable"
        assert data["detail"] == "LDAP server is not reachable."

    @patch("accounts.services.ldap_client._create_connection")
    def test_connection_check_uses_object_class_for_base_dn_probe(
        self,
        mock_create_connection,
    ):
        fake_connection = _FakeLdapConnection()
        mock_create_connection.return_value = fake_connection

        result = run_ldap_connection_test(
            {
                "host": "ldap.example.com",
                "port": 389,
                "user_base_dn": "ou=People,dc=example,dc=com",
                "group_base_dn": "ou=Groups,dc=example,dc=com",
            }
        )

        assert result["reachable"] is True
        assert result["base_dns_checked"] == [
            "ou=People,dc=example,dc=com",
            "ou=Groups,dc=example,dc=com",
        ]
        assert fake_connection.search_calls
        assert all(
            call["attributes"] == ["objectClass"]
            for call in fake_connection.search_calls
        )

    @patch("accounts.views.ldap.preview_ldap_user")
    def test_test_user_returns_group_mapping_preview(self, mock_preview_ldap_user):
        admin = User.objects.create_user(
            username="ldap-admin-user-preview",
            password="password123",
            is_staff=True,
        )
        ops_group = Group.objects.create(name="Ops")
        config = LdapAuthConfig.objects.create(
            name="Preview LDAP",
            slug="preview",
            enabled=True,
            host="ldap-preview.example.com",
        )
        LdapGroupMapping.objects.create(
            ldap_config=config,
            ldap_group_dn="cn=ops,ou=groups,dc=example,dc=com",
            target_group=ops_group,
        )
        client = APIClient()
        client.force_authenticate(user=admin)

        mock_preview_ldap_user.return_value = {
            "user": LdapUserRecord(
                username="person-a",
                dn="uid=person-a,ou=people,dc=example,dc=com",
                email="person-a@example.com",
                first_name="Person",
                last_name="A",
                display_name="Person A",
                group_dns=["cn=ops,ou=groups,dc=example,dc=com"],
            ),
            "mapped_groups": [{"id": ops_group.id, "name": "Ops"}],
        }

        response = client.post(
            "/api/v1/management/ldap/test-user/",
            {"username": "person-a", "ldap_config": config.id},
            format="json",
        )

        assert response.status_code == 200
        data = _payload(response)
        assert data["user"]["dn"] == "uid=person-a,ou=people,dc=example,dc=com"
        assert data["mapped_groups"] == [{"id": ops_group.id, "name": "Ops"}]

    def test_group_mapping_crud_round_trip(self):
        admin = User.objects.create_user(
            username="ldap-admin-mapping",
            password="password123",
            is_staff=True,
        )
        config = LdapAuthConfig.objects.create(
            name="LDAP A",
            slug="ldap-a",
            enabled=True,
            host="ldap-a.example.com",
        )
        ops_group = Group.objects.create(name="Ops")
        client = APIClient()
        client.force_authenticate(user=admin)

        create_response = client.post(
            "/api/v1/management/ldap/group-mappings/",
            {
                "ldap_config": config.id,
                "ldap_group_dn": "cn=ops,ou=groups,dc=example,dc=com",
                "target_group": ops_group.id,
                "is_active": True,
            },
            format="json",
        )
        assert create_response.status_code == 201
        mapping_id = _payload(create_response)["id"]

        list_response = client.get("/api/v1/management/ldap/group-mappings/")
        assert list_response.status_code == 200
        list_payload = _payload(list_response)
        assert list_payload["results"][0]["target_group"]["name"] == "Ops"
        assert list_payload["results"][0]["ldap_config"] == config.id

        patch_response = client.patch(
            f"/api/v1/management/ldap/group-mappings/{mapping_id}/",
            {"is_active": False},
            format="json",
        )
        assert patch_response.status_code == 200
        assert _payload(patch_response)["is_active"] is False

        delete_response = client.delete(
            f"/api/v1/management/ldap/group-mappings/{mapping_id}/"
        )
        assert delete_response.status_code == 204

    def test_all_user_mapping_crud_round_trip(self):
        admin = User.objects.create_user(
            username="ldap-admin-all-mapping",
            password="password123",
            is_staff=True,
        )
        config = LdapAuthConfig.objects.create(
            name="LDAP All",
            slug="ldap-all",
            enabled=True,
            host="ldap-all.example.com",
        )
        directory_group = Group.objects.create(name="Directory Users")
        client = APIClient()
        client.force_authenticate(user=admin)

        create_response = client.post(
            "/api/v1/management/ldap/group-mappings/",
            {
                "ldap_config": config.id,
                "mapping_scope": "all",
                "target_group": directory_group.id,
                "is_active": True,
            },
            format="json",
        )

        assert create_response.status_code == 201
        payload = _payload(create_response)
        assert payload["mapping_scope"] == "all"
        assert payload["ldap_group_dn"] == ""
        assert payload["target_group"]["name"] == "Directory Users"


class TestLdapServerTls:
    def test_build_server_requires_cert_for_ldaps(self):
        import ssl

        from ldap3 import Tls

        from accounts.services.ldap_client import _build_server

        server = _build_server(
            {
                "host": "ldap.example.com",
                "port": 636,
                "use_ssl": True,
            }
        )

        assert isinstance(server.tls, Tls)
        assert server.tls.validate == ssl.CERT_REQUIRED

    def test_build_server_uses_supplied_ca_bundle(self, tmp_path):
        from accounts.services.ldap_client import _build_server

        ca_file = tmp_path / "ca.pem"
        ca_file.write_bytes(b"")

        server = _build_server(
            {
                "host": "ldap.example.com",
                "port": 636,
                "use_ssl": True,
                "tls_ca_bundle": str(ca_file),
            }
        )

        assert server.tls.ca_certs_file == str(ca_file)

    def test_build_server_allow_no_cert(self):
        import ssl

        from accounts.services.ldap_client import _build_server

        server = _build_server(
            {
                "host": "ldap.example.com",
                "port": 636,
                "use_ssl": True,
                "tls_require_cert": False,
            }
        )

        assert server.tls.validate == ssl.CERT_NONE

    def test_build_server_skips_tls_when_plain(self):
        from accounts.services.ldap_client import _build_server

        server = _build_server(
            {
                "host": "ldap.example.com",
                "port": 389,
                "use_ssl": False,
            }
        )

        assert server.tls is None


class TestLdapFilterEscaping:
    @patch("accounts.services.ldap_client._create_connection")
    def test_search_user_escapes_username(self, mock_create_connection):
        from accounts.services.ldap_client import _search_user

        fake = _FakeLdapConnection()
        mock_create_connection.return_value = fake

        _search_user(
            fake,
            {
                "user_base_dn": "ou=people,dc=example,dc=com",
                "user_filter_template": "(&(objectClass=person)(uid={username}))",
                "uid_attr": "uid",
                "email_attr": "mail",
                "first_name_attr": "givenName",
                "last_name_attr": "sn",
                "display_name_attr": "displayName",
            },
            "evil)(uid=*",
        )

        sent = fake.search_calls[-1]["search_filter"]
        assert "evil)(uid=*" not in sent
        assert "objectClass=person" in sent

    @patch("accounts.services.ldap_client._create_connection")
    def test_search_group_dns_escapes_user_dn(self, mock_create_connection):
        from accounts.services.ldap_client import _search_group_dns

        fake = _FakeLdapConnection()
        mock_create_connection.return_value = fake

        _search_group_dns(
            fake,
            {
                "group_base_dn": "ou=groups,dc=example,dc=com",
                "group_filter_template": "(&(objectClass=groupOfNames)(member={user_dn}))",
            },
            "safe-user",
            "uid=evil,ou=people,dc=example,dc=com)(uid=*",
        )

        sent = fake.search_calls[-1]["search_filter"]
        assert "uid=evil,ou=people,dc=example,dc=com)(uid=*" not in sent
        assert "objectClass=groupOfNames" in sent


@pytest.mark.django_db
class TestLdapInstanceDeletion:
    @pytest.fixture(autouse=True)
    def _settings(self, settings):
        settings.ROOT_URLCONF = "accounts.urls"
        from accounts.models import Profile

        admin = User.objects.create_user(
            username="ldap-admin-del",
            password="password123",
            is_staff=True,
        )
        config = LdapAuthConfig.objects.create(
            name="LDAP Del",
            slug="del",
            enabled=True,
            host="ldap-del.example.com",
        )
        User.objects.create_user(
            username="linked-user",
            email="linked@example.com",
            password="password123",
        )
        profile = User.objects.get(username="linked-user").profile
        profile.ldap_instance = config
        profile.ldap_uid = "linked"
        profile.auth_source = Profile.AUTH_SOURCE_LDAP
        profile.save(update_fields=["ldap_instance", "ldap_uid", "auth_source"])

        client = APIClient()
        client.force_authenticate(user=admin)

        response = client.delete(
            f"/api/v1/management/ldap/instances/{config.id}/"
        )

        assert response.status_code == 400
        body = response.json()
        assert body["code"] == "ldap_in_use"
        assert LdapAuthConfig.objects.filter(id=config.id).exists()

    def test_delete_allowed_when_no_profile_reference(self):
        admin = User.objects.create_user(
            username="ldap-admin-clean-del",
            password="password123",
            is_staff=True,
        )
        config = LdapAuthConfig.objects.create(
            name="LDAP Clean",
            slug="clean",
            enabled=True,
            host="ldap-clean.example.com",
        )
        client = APIClient()
        client.force_authenticate(user=admin)

        response = client.delete(
            f"/api/v1/management/ldap/instances/{config.id}/"
        )

        assert response.status_code == 204
        assert not LdapAuthConfig.objects.filter(id=config.id).exists()


@pytest.mark.django_db
class TestLdapDefaultUniqueness:
    @pytest.fixture(autouse=True)
    def _settings(self, settings):
        # The default uniqueness behaviour lives in save() which does not
        # require the URL conf, but pinning to the real accounts.urls avoids
        # any future cross-test settings drift.
        settings.ROOT_URLCONF = "accounts.urls"

    def _make_config(self, slug_suffix, is_default, host):
        return LdapAuthConfig.objects.create(
            name=f"LDAP {slug_suffix}",
            slug=f"uniq-{slug_suffix}",
            enabled=True,
            host=host,
            is_default=is_default,
        )

    def test_marking_default_clears_other_defaults(self):
        first = self._make_config("first", is_default=True, host="ldap-first.example.com")
        second = self._make_config("second", is_default=False, host="ldap-second.example.com")

        second.is_default = True
        second.save()

        first.refresh_from_db()
        second.refresh_from_db()
        assert second.is_default is True
        assert first.is_default is False

    def test_create_with_default_true_does_not_make_existing_default(self):
        first = self._make_config("third", is_default=True, host="ldap-third.example.com")
        self._make_config("fourth", is_default=True, host="ldap-fourth.example.com")

        first.refresh_from_db()
        assert first.is_default is False

    def test_create_with_default_true_does_not_make_existing_default(self):
        first = LdapAuthConfig.objects.create(
            name="LDAP A",
            slug="uniq-a",
            enabled=True,
            host="ldap-a.example.com",
            is_default=True,
        )
        LdapAuthConfig.objects.create(
            name="LDAP B",
            slug="uniq-d",
            enabled=True,
            host="ldap-b.example.com",
            is_default=True,
        )

        first.refresh_from_db()
        assert first.is_default is False
