from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from accounts.models import LdapAuthConfig, LdapGroupMapping, Profile
from accounts.services.ldap_sync import LdapUserRecord

User = get_user_model()


def _payload(response):
    body = response.json()
    if isinstance(body, dict) and "data" in body:
        return body["data"]
    return body


@pytest.mark.django_db
class TestLdapLoginFlow:
    @pytest.fixture(autouse=True)
    def _settings(self, settings):
        settings.ROOT_URLCONF = "accounts.urls"
        settings.AUTHENTICATION_BACKENDS = (
            "accounts.auth_backends.DirectoryAwareBackend",
        )

    def test_local_user_authenticates_with_local_password(self):
        user = User.objects.create_user(
            username="local-user",
            email="local@example.com",
            password="password123",
        )
        profile = user.profile
        profile.auth_source = Profile.AUTH_SOURCE_LOCAL
        profile.save(update_fields=["auth_source"])

        client = APIClient()
        response = client.post(
            "/api/v1/auth/login",
            {"username": "local-user", "password": "password123"},
            format="json",
        )

        assert response.status_code == 200
        data = _payload(response)
        assert data["access"]
        assert data["refresh"]
        assert data["user"]["username"] == "local-user"

    @patch("accounts.auth_backends.authenticate_ldap_user")
    def test_selected_ldap_instance_creates_prefixed_local_user(
        self,
        mock_authenticate_ldap,
    ):
        config = LdapAuthConfig.objects.create(
            name="OneProCloud LDAP",
            slug="oneprocloud",
            enabled=True,
            host="ldap.oneprocloud.example",
        )
        mock_authenticate_ldap.return_value = LdapUserRecord(
            username="zhangsan",
            dn="uid=zhangsan,ou=people,dc=example,dc=com",
            email="zhangsan@example.com",
            first_name="Ldap",
            last_name="User",
            display_name="Zhang San",
            group_dns=[
                "cn=ops,ou=groups,dc=example,dc=com",
            ],
        )

        client = APIClient()
        response = client.post(
            "/api/v1/auth/login",
            {
                "auth_source": "ldap",
                "ldap_instance_id": config.id,
                "username": "zhangsan",
                "password": "directory-secret",
            },
            format="json",
        )

        assert response.status_code == 200
        created_user = User.objects.get(username="oneprocloud_zhangsan")
        profile = created_user.profile
        assert profile.auth_source == Profile.AUTH_SOURCE_LDAP
        assert profile.ldap_instance == config
        assert profile.ldap_uid == "zhangsan"
        assert profile.ldap_dn == "uid=zhangsan,ou=people,dc=example,dc=com"
        assert profile.nickname == "Zhang San"
        assert profile.ldap_group_dns_snapshot == [
            "cn=ops,ou=groups,dc=example,dc=com"
        ]
        mock_authenticate_ldap.assert_called_once()
        assert mock_authenticate_ldap.call_args.args[0] == config
        data = _payload(response)
        assert data["user"]["display_name"] == "Zhang San"

    @patch("accounts.auth_backends.authenticate_ldap_user")
    def test_ldap_all_user_mapping_applies_without_group_dns(
        self,
        mock_authenticate_ldap,
    ):
        config = LdapAuthConfig.objects.create(
            name="OneProCloud LDAP",
            slug="oneprocloud",
            enabled=True,
            host="ldap.oneprocloud.example",
        )
        default_group = Group.objects.create(name="Directory Users")
        LdapGroupMapping.objects.create(
            ldap_config=config,
            mapping_scope="all",
            target_group=default_group,
        )
        mock_authenticate_ldap.return_value = LdapUserRecord(
            username="zhangjiaqi",
            dn="uid=zhangjiaqi,ou=people,dc=example,dc=com",
            email="zhangjiaqi@example.com",
            display_name="Zhang Jiaqi",
            group_dns=[],
        )

        client = APIClient()
        response = client.post(
            "/api/v1/auth/login",
            {
                "auth_source": "ldap",
                "ldap_instance_id": config.id,
                "username": "zhangjiaqi",
                "password": "directory-secret",
            },
            format="json",
        )

        assert response.status_code == 200
        created_user = User.objects.get(username="oneprocloud_zhangjiaqi")
        assert list(created_user.groups.values_list("name", flat=True)) == [
            "Directory Users"
        ]

    @patch("accounts.auth_backends.authenticate_ldap_user")
    def test_same_uid_in_different_ldap_instances_creates_distinct_users(
        self,
        mock_authenticate_ldap,
    ):
        config_a = LdapAuthConfig.objects.create(
            name="LDAP A",
            slug="a",
            enabled=True,
            host="ldap-a.example.com",
        )
        config_b = LdapAuthConfig.objects.create(
            name="LDAP B",
            slug="b",
            enabled=True,
            host="ldap-b.example.com",
        )
        mock_authenticate_ldap.return_value = LdapUserRecord(
            username="shared",
            dn="uid=shared,ou=people,dc=example,dc=com",
            email="shared@example.com",
            display_name="Shared User",
            group_dns=[],
        )

        client = APIClient()
        response_a = client.post(
            "/api/v1/auth/login",
            {
                "auth_source": "ldap",
                "ldap_instance_id": config_a.id,
                "username": "shared",
                "password": "secret-a",
            },
            format="json",
        )
        response_b = client.post(
            "/api/v1/auth/login",
            {
                "auth_source": "ldap",
                "ldap_instance_id": config_b.id,
                "username": "shared",
                "password": "secret-b",
            },
            format="json",
        )

        assert response_a.status_code == 200
        assert response_b.status_code == 200
        assert User.objects.filter(username__in=["a_shared", "b_shared"]).count() == 2
        assert User.objects.get(username="a_shared").profile.ldap_instance == config_a
        assert User.objects.get(username="b_shared").profile.ldap_instance == config_b

    @patch("accounts.auth_backends.authenticate_ldap_user")
    def test_generated_ldap_username_conflict_rejects_takeover(
        self,
        mock_authenticate_ldap,
    ):
        config = LdapAuthConfig.objects.create(
            name="LDAP A",
            slug="a",
            enabled=True,
            host="ldap-a.example.com",
        )
        user = User.objects.create_user(
            username="a_shared-user",
            email="shared@example.com",
            password="password123",
        )
        profile = user.profile
        profile.auth_source = Profile.AUTH_SOURCE_LOCAL
        profile.save(update_fields=["auth_source"])

        mock_authenticate_ldap.return_value = LdapUserRecord(
            username="shared-user",
            dn="uid=shared-user,ou=people,dc=example,dc=com",
            email="shared-ldap@example.com",
            first_name="Shared",
            last_name="Directory",
            display_name="Shared Directory",
            group_dns=[],
        )

        client = APIClient()
        response = client.post(
            "/api/v1/auth/login",
            {
                "auth_source": "ldap",
                "ldap_instance_id": config.id,
                "username": "shared-user",
                "password": "directory-secret",
            },
            format="json",
        )

        assert response.status_code == 400
        payload = response.json()
        assert payload["code"] == "ldap_account_conflict"

    @patch("accounts.auth_backends.authenticate_ldap_user")
    def test_ldap_user_does_not_fallback_to_local_password(self, mock_authenticate_ldap):
        config = LdapAuthConfig.objects.create(
            name="Directory",
            slug="directory",
            enabled=True,
            host="ldap.example.com",
        )
        user = User.objects.create_user(
            username="directory_directory-only",
            email="directory@example.com",
            password="local-password",
        )
        profile = user.profile
        profile.auth_source = Profile.AUTH_SOURCE_LDAP
        profile.ldap_uid = "directory-only"
        profile.ldap_instance = config
        profile.save(update_fields=["auth_source", "ldap_uid", "ldap_instance"])

        mock_authenticate_ldap.return_value = None

        client = APIClient()
        response = client.post(
            "/api/v1/auth/login",
            {
                "auth_source": "ldap",
                "ldap_instance_id": config.id,
                "username": "directory-only",
                "password": "local-password",
            },
            format="json",
        )

        assert response.status_code == 400
        payload = response.json()
        assert payload["code"] == "ldap_auth_failed"


    def test_local_user_authenticates_with_email(self):
        user = User.objects.create_user(
            username="local-by-email",
            email="local-by-email@example.com",
            password="password123",
        )
        profile = user.profile
        profile.auth_source = Profile.AUTH_SOURCE_LOCAL
        profile.save(update_fields=["auth_source"])

        client = APIClient()
        response = client.post(
            "/api/v1/auth/login",
            {"username": "local-by-email@example.com", "password": "password123"},
            format="json",
        )

        assert response.status_code == 200
        data = _payload(response)
        assert data["user"]["username"] == "local-by-email"
