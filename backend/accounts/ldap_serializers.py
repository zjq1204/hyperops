"""Serializers for LDAP configuration and previews."""

from __future__ import annotations

from django.contrib.auth.models import Group
from rest_framework import serializers

from accounts.models import LdapAuthConfig, LdapGroupMapping


class LdapProviderSerializer(serializers.ModelSerializer):
    """Public enabled LDAP provider metadata for login page."""

    class Meta:
        model = LdapAuthConfig
        fields = ["id", "name", "slug"]


class LdapAuthConfigSerializer(serializers.ModelSerializer):
    """Serializer for LDAP instance configuration."""

    bind_password = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
    )
    has_bind_password = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = LdapAuthConfig
        exclude = ["bind_password_encrypted"]
        read_only_fields = ["id", "created_at", "updated_at", "has_bind_password"]

    def get_has_bind_password(self, obj):
        return obj.has_bind_password

    def create(self, validated_data):
        bind_password = validated_data.pop("bind_password", None)
        instance = LdapAuthConfig(**validated_data)
        if bind_password is not None:
            instance.set_bind_password(bind_password)
        instance.save()
        return instance

    def update(self, instance, validated_data):
        bind_password = validated_data.pop("bind_password", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        if bind_password is not None:
            instance.set_bind_password(bind_password)
        instance.save()
        return instance


class LdapGroupMappingSerializer(serializers.ModelSerializer):
    """Serializer for LDAP group to Django group mappings."""

    ldap_config = serializers.PrimaryKeyRelatedField(queryset=LdapAuthConfig.objects.all())
    target_group = serializers.PrimaryKeyRelatedField(queryset=Group.objects.all())

    class Meta:
        model = LdapGroupMapping
        fields = [
            "id",
            "ldap_config",
            "mapping_scope",
            "ldap_group_dn",
            "target_group",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        mapping_scope = attrs.get(
            "mapping_scope",
            getattr(self.instance, "mapping_scope", LdapGroupMapping.SCOPE_GROUP),
        )
        ldap_group_dn = attrs.get(
            "ldap_group_dn",
            getattr(self.instance, "ldap_group_dn", ""),
        )
        if mapping_scope == LdapGroupMapping.SCOPE_GROUP and not (
            ldap_group_dn or ""
        ).strip():
            raise serializers.ValidationError(
                {
                    "ldap_group_dn": (
                        "LDAP group DN is required for group mappings."
                    )
                }
            )
        if mapping_scope == LdapGroupMapping.SCOPE_ALL:
            attrs["ldap_group_dn"] = ""
        return attrs

    def to_representation(self, instance):
        payload = super().to_representation(instance)
        payload["ldap_config"] = instance.ldap_config_id
        payload["target_group"] = {
            "id": instance.target_group_id,
            "name": instance.target_group.name,
        }
        return payload


class LdapTestUserSerializer(serializers.Serializer):
    """Request serializer for LDAP user preview endpoint."""

    username = serializers.CharField()
