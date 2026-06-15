"""LDAP management API views."""

from __future__ import annotations

from django.http import Http404

from platformkit.api import build_paginated_payload, parse_bounded_int
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.ldap_serializers import (
    LdapAuthConfigSerializer,
    LdapGroupMappingSerializer,
    LdapProviderSerializer,
    LdapTestUserSerializer,
)
from accounts.models import LdapAuthConfig, LdapGroupMapping, Profile
from accounts.permissions import HasRequiredFeature
from accounts.services.ldap_client import (
    LdapServiceError,
    preview_ldap_user,
    test_ldap_connection,
)


def _get_default_ldap_config():
    config = LdapAuthConfig.objects.order_by("-is_default", "id").first()
    if config is not None:
        return config
    return LdapAuthConfig.objects.create(
        name="Default LDAP",
        slug="default",
        is_default=True,
    )


def _get_request_ldap_config(data):
    config_id = data.get("ldap_config") or data.get("ldap_instance_id") or data.get("id")
    if not config_id:
        return _get_default_ldap_config()
    try:
        return LdapAuthConfig.objects.get(pk=config_id)
    except (LdapAuthConfig.DoesNotExist, TypeError, ValueError) as exc:
        raise Http404 from exc


class PublicLdapProviderListView(APIView):
    """List enabled LDAP providers available on the login page."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        queryset = LdapAuthConfig.objects.filter(enabled=True).order_by(
            "-is_default",
            "id",
        )
        return Response(LdapProviderSerializer(queryset, many=True).data)


class ManagementLdapInstanceListView(APIView):
    """List and create LDAP instances."""

    permission_classes = [HasRequiredFeature]
    required_feature = "admin_users"

    def get(self, request):
        page = parse_bounded_int(request.query_params.get("page"), default=1)
        page_size = parse_bounded_int(
            request.query_params.get("page_size"),
            default=20,
        )
        queryset = LdapAuthConfig.objects.order_by("-is_default", "id")
        total = queryset.count()
        start = (page - 1) * page_size
        end = start + page_size
        serializer = LdapAuthConfigSerializer(queryset[start:end], many=True)
        return Response(build_paginated_payload(serializer.data, total, page, page_size))

    def post(self, request):
        serializer = LdapAuthConfigSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ManagementLdapInstanceDetailView(APIView):
    """Update or delete a single LDAP instance."""

    permission_classes = [HasRequiredFeature]
    required_feature = "admin_users"

    def get_object(self, instance_id):
        try:
            return LdapAuthConfig.objects.get(pk=instance_id)
        except LdapAuthConfig.DoesNotExist as exc:
            raise Http404 from exc

    def get(self, request, instance_id):
        return Response(LdapAuthConfigSerializer(self.get_object(instance_id)).data)

    def patch(self, request, instance_id):
        serializer = LdapAuthConfigSerializer(
            self.get_object(instance_id),
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, instance_id):
        instance = self.get_object(instance_id)
        if Profile.objects.filter(ldap_instance=instance).exists():
            return Response(
                {
                    "code": "ldap_in_use",
                    "detail": (
                        "LDAP instance is referenced by user profiles. "
                        "Unlink or migrate them before deleting."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ManagementLdapConfigView(APIView):
    """Read and update the singleton LDAP configuration."""

    permission_classes = [HasRequiredFeature]
    required_feature = "admin_users"

    def get_object(self):
        return _get_default_ldap_config()

    def get(self, request):
        serializer = LdapAuthConfigSerializer(self.get_object())
        return Response(serializer.data)

    def put(self, request):
        serializer = LdapAuthConfigSerializer(
            self.get_object(),
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class ManagementLdapTestConnectionView(APIView):
    """Validate LDAP connectivity using current or draft settings."""

    permission_classes = [HasRequiredFeature]
    required_feature = "admin_users"

    def post(self, request):
        config = _get_request_ldap_config(request.data)
        try:
            return Response(test_ldap_connection(config, request.data))
        except LdapServiceError as exc:
            return Response(
                {
                    "reachable": False,
                    "bind_succeeded": False,
                    "base_dns_checked": [],
                    "detail": exc.detail,
                    "code": exc.code,
                },
            )


class ManagementLdapTestUserView(APIView):
    """Preview LDAP user lookup and group mapping results."""

    permission_classes = [HasRequiredFeature]
    required_feature = "admin_users"

    def post(self, request):
        serializer = LdapTestUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        config = _get_request_ldap_config(request.data)
        try:
            preview = preview_ldap_user(
                serializer.validated_data["username"],
                config,
                request.data,
            )
        except LdapServiceError as exc:
            return Response(
                {"detail": exc.detail, "code": exc.code},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = preview["user"]
        return Response(
            {
                "user": {
                    "username": user.username,
                    "dn": user.dn,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "display_name": user.display_name,
                    "group_dns": user.group_dns,
                },
                "mapped_groups": preview["mapped_groups"],
            }
        )


class ManagementLdapGroupMappingListView(APIView):
    """List and create LDAP group mappings."""

    permission_classes = [HasRequiredFeature]
    required_feature = "admin_users"

    def get(self, request):
        page = parse_bounded_int(request.query_params.get("page"), default=1)
        page_size = parse_bounded_int(
            request.query_params.get("page_size"),
            default=20,
        )
        queryset = LdapGroupMapping.objects.select_related(
            "ldap_config",
            "target_group",
        ).order_by(
            "ldap_config__name",
            "mapping_scope",
            "ldap_group_dn",
            "target_group__name",
            "id",
        )
        ldap_config_id = request.query_params.get("ldap_config")
        if ldap_config_id:
            queryset = queryset.filter(ldap_config_id=ldap_config_id)
        total = queryset.count()
        start = (page - 1) * page_size
        end = start + page_size
        serializer = LdapGroupMappingSerializer(queryset[start:end], many=True)
        return Response(build_paginated_payload(serializer.data, total, page, page_size))

    def post(self, request):
        payload = request.data.copy()
        if not payload.get("ldap_config"):
            payload["ldap_config"] = _get_default_ldap_config().id
        serializer = LdapGroupMappingSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ManagementLdapGroupMappingDetailView(APIView):
    """Update and delete a single LDAP group mapping."""

    permission_classes = [HasRequiredFeature]
    required_feature = "admin_users"

    def get_object(self, mapping_id):
        try:
            return LdapGroupMapping.objects.select_related("target_group").get(
                pk=mapping_id
            )
        except LdapGroupMapping.DoesNotExist as exc:
            raise Http404 from exc

    def patch(self, request, mapping_id):
        serializer = LdapGroupMappingSerializer(
            self.get_object(mapping_id),
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, mapping_id):
        self.get_object(mapping_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
