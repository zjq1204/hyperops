"""Authentication views with directory-aware login behavior."""

from __future__ import annotations

from django.contrib.auth import authenticate
from django.utils.translation import gettext_lazy as _

from drf_spectacular.utils import extend_schema

from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.serializers import UserDetailsSerializer
from platformkit.auth import AuthTokenResponseSerializer


class LoginRequestSerializer(serializers.Serializer):
    """Minimal username/password login request serializer."""

    AUTH_SOURCE_LOCAL = "local"
    AUTH_SOURCE_LDAP = "ldap"
    AUTH_SOURCE_CHOICES = [
        (AUTH_SOURCE_LOCAL, "Local"),
        (AUTH_SOURCE_LDAP, "LDAP"),
    ]

    username = serializers.CharField()
    password = serializers.CharField(write_only=True)
    auth_source = serializers.ChoiceField(
        choices=AUTH_SOURCE_CHOICES,
        default=AUTH_SOURCE_LOCAL,
        required=False,
    )
    ldap_instance_id = serializers.IntegerField(required=False, allow_null=True)

    def validate(self, attrs):
        if (
            attrs.get("auth_source") == self.AUTH_SOURCE_LDAP
            and not attrs.get("ldap_instance_id")
        ):
            raise serializers.ValidationError(
                {"ldap_instance_id": _("LDAP provider is required.")}
            )
        return attrs


class CustomLoginView(APIView):
    """JWT login endpoint backed by the directory-aware authentication backend."""

    permission_classes = [AllowAny]

    @extend_schema(
        tags=["auth"],
        summary=_("Login with local or LDAP credentials"),
        request=LoginRequestSerializer,
        responses={200: AuthTokenResponseSerializer},
    )
    def post(self, request):
        serializer = LoginRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "detail": _("Username and password are required."),
                    "code": "invalid_credentials_payload",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = authenticate(
            request,
            username=serializer.validated_data["username"],
            password=serializer.validated_data["password"],
            auth_source=serializer.validated_data.get("auth_source"),
            ldap_instance_id=serializer.validated_data.get("ldap_instance_id"),
        )
        if user is None:
            auth_error = getattr(request, "_auth_error", None) or {}
            return Response(
                {
                    "detail": auth_error.get(
                        "detail",
                        _("Unable to log in with the provided credentials."),
                    ),
                    "code": auth_error.get("code", "invalid_credentials"),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        refresh = RefreshToken.for_user(user)
        user.refresh_from_db()
        user_data = UserDetailsSerializer(user).data
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": user_data,
            },
            status=status.HTTP_200_OK,
        )
