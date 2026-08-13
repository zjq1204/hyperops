"""Management portal views for users, groups, and role visibility."""

from functools import partial

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.http import Http404
from django.db.models import Count, Prefetch
from platformkit.api import build_paginated_payload, parse_bounded_int
from platformkit.management import (
    build_group_payload,
    build_role_payload,
    build_role_summary,
    build_user_payload,
)
from platformkit.users import upsert_profile_preferences
from rest_framework.status import HTTP_200_OK
from rest_framework.response import Response
from rest_framework.status import HTTP_201_CREATED, HTTP_400_BAD_REQUEST
from rest_framework.views import APIView

from accounts.access import (
    get_access_profile,
    get_effective_roles,
    normalize_feature_keys,
    normalize_operation_permission_keys,
    normalize_platform_key,
    serialize_feature_options,
    serialize_operation_permission_options,
    serialize_platform_options,
)
from accounts.models import GroupNotificationConfig, Profile, Role
from accounts.permissions import HasRequiredFeature

User = get_user_model()

ROLE_SUMMARY_SERIALIZER = partial(
    build_role_summary,
    normalize_features=normalize_feature_keys,
    normalize_platform=normalize_platform_key,
    normalize_operations=normalize_operation_permission_keys,
)

ROLE_PAYLOAD_SERIALIZER = partial(
    build_role_payload,
    normalize_features=normalize_feature_keys,
    normalize_platform=normalize_platform_key,
    normalize_operations=normalize_operation_permission_keys,
)


def _resolve_user_payload_context(user):
    """Resolve pre-fetched user context required for payload assembly."""
    try:
        profile = user.profile
    except Profile.DoesNotExist:
        profile = None

    ordered_groups = getattr(user, 'ordered_groups', None)
    if ordered_groups is None:
        ordered_groups = user.groups.all().order_by('name')

    direct_roles = getattr(user, 'ordered_roles', None)
    if direct_roles is None:
        direct_roles = user.platform_roles.filter(is_active=True).order_by(
            'name',
            'id',
        )

    effective_roles = get_effective_roles(
        user,
        direct_roles=direct_roles,
        groups=ordered_groups,
    )
    return {
        'profile': profile,
        'groups': ordered_groups,
        'direct_roles': direct_roles,
        'effective_roles': effective_roles,
    }


def _resolve_group_roles(group):
    """Resolve pre-fetched group roles or fall back to ordered query."""
    direct_roles = getattr(group, 'ordered_roles', None)
    if direct_roles is None:
        direct_roles = group.platform_roles.filter(is_active=True).order_by(
            'name',
            'id',
        )
    return direct_roles


class ManagementUserListView(APIView):
    """
    GET: List all users for management console (with profile and groups).
    POST: Create user (username, email, password, is_staff, group_ids, etc).
    Admin-only.
    """

    permission_classes = [HasRequiredFeature]
    required_feature = 'admin_users'

    def get(self, request):
        page = parse_bounded_int(request.query_params.get('page'), default=1)
        page_size = parse_bounded_int(
            request.query_params.get('page_size'),
            default=20,
        )
        user_role_prefetch = Prefetch(
            'platform_roles',
            queryset=Role.objects.filter(is_active=True).order_by('name', 'id'),
            to_attr='ordered_roles',
        )
        group_role_prefetch = Prefetch(
            'platform_roles',
            queryset=Role.objects.filter(is_active=True).order_by('name', 'id'),
            to_attr='ordered_roles',
        )
        groups_prefetch = Prefetch(
            'groups',
            queryset=Group.objects.order_by('name').prefetch_related(
                group_role_prefetch
            ),
            to_attr='ordered_groups',
        )
        qs = User.objects.select_related('profile').prefetch_related(
            groups_prefetch,
            user_role_prefetch,
        ).order_by('id')
        total = qs.count()
        start = (page - 1) * page_size
        end = start + page_size
        items = [
            build_user_payload(
                user,
                role_serializer=ROLE_SUMMARY_SERIALIZER,
                access_profile_builder=get_access_profile,
                normalize_platform=normalize_platform_key,
                **_resolve_user_payload_context(user),
            )
            for user in qs[start:end]
        ]
        return Response(
            build_paginated_payload(items, total, page, page_size)
        )

    def post(self, request):
        username = (request.data.get('username') or '').strip()
        email = (request.data.get('email') or '').strip()
        password = request.data.get('password') or ''
        is_staff = bool(request.data.get('is_staff', False))
        group_ids = request.data.get('group_ids') or []
        role_ids = request.data.get('role_ids') or []
        if not isinstance(group_ids, list):
            group_ids = []
        if not isinstance(role_ids, list):
            role_ids = []
        language = (request.data.get('language') or '').strip() or 'zh-CN'
        timezone = (request.data.get('timezone') or '').strip() or 'Asia/Shanghai'
        preferred_platform = normalize_platform_key(
            request.data.get('preferred_platform')
        )

        if not username:
            return Response(
                {'detail': 'Username is required.', 'code': 'username_required'},
                status=HTTP_400_BAD_REQUEST
            )
        if not password:
            return Response(
                {'detail': 'Password is required.', 'code': 'password_required'},
                status=HTTP_400_BAD_REQUEST
            )
        if User.objects.filter(username=username).exists():
            return Response(
                {
                    'detail': 'A user with that username already exists.',
                    'code': 'username_taken',
                },
                status=HTTP_400_BAD_REQUEST
            )
        if email and User.objects.filter(email=email).exists():
            return Response(
                {
                    'detail': 'A user with that email already exists.',
                    'code': 'email_taken',
                },
                status=HTTP_400_BAD_REQUEST
            )

        user = User.objects.create_user(
            username=username,
            email=email or '',
            password=password,
        )
        if is_staff:
            user.is_staff = True
            user.save(update_fields=['is_staff'])
        if group_ids:
            valid_ids = list(
                Group.objects.filter(pk__in=group_ids).values_list(
                    'pk', flat=True
                )
            )
            if valid_ids:
                user.groups.set(valid_ids)
        if role_ids:
            valid_role_ids = list(
                Role.objects.filter(pk__in=role_ids).values_list('pk', flat=True)
            )
            if valid_role_ids:
                user.platform_roles.set(valid_role_ids)
        upsert_profile_preferences(
            user,
            profile_model=Profile,
            profile_language=language,
            profile_timezone=timezone,
            preferred_platform=preferred_platform,
            normalize_platform=normalize_platform_key,
        )
        return Response(
            build_user_payload(
                user,
                role_serializer=ROLE_SUMMARY_SERIALIZER,
                access_profile_builder=get_access_profile,
                normalize_platform=normalize_platform_key,
                **_resolve_user_payload_context(user),
            ),
            status=HTTP_201_CREATED,
        )


class ManagementUserDetailView(APIView):
    """PATCH: Update user group and role bindings."""

    permission_classes = [HasRequiredFeature]
    required_feature = 'admin_users'

    def patch(self, request, user_id):
        user = _get_user_or_404(user_id)

        username = request.data.get('username')
        email = request.data.get('email')
        is_staff = request.data.get('is_staff')
        is_active = request.data.get('is_active')
        group_ids = request.data.get('group_ids')
        role_ids = request.data.get('role_ids')
        language = request.data.get('language')
        timezone = request.data.get('timezone')
        preferred_platform = request.data.get('preferred_platform')

        update_fields = []
        if username is not None:
            username = str(username).strip()
            if not username:
                return Response(
                    {
                        'detail': 'Username is required.',
                        'code': 'username_required',
                    },
                    status=HTTP_400_BAD_REQUEST,
                )
            if User.objects.exclude(pk=user.pk).filter(username=username).exists():
                return Response(
                    {
                        'detail': 'A user with that username already exists.',
                        'code': 'username_taken',
                    },
                    status=HTTP_400_BAD_REQUEST,
                )
            user.username = username
            update_fields.append('username')

        if email is not None:
            email = str(email).strip()
            if email and User.objects.exclude(pk=user.pk).filter(email=email).exists():
                return Response(
                    {
                        'detail': 'A user with that email already exists.',
                        'code': 'email_taken',
                    },
                    status=HTTP_400_BAD_REQUEST,
                )
            user.email = email
            update_fields.append('email')

        if is_staff is not None:
            user.is_staff = bool(is_staff)
            update_fields.append('is_staff')

        if is_active is not None:
            user.is_active = bool(is_active)
            update_fields.append('is_active')

        if update_fields:
            user.save(update_fields=update_fields)

        if group_ids is not None:
            if not isinstance(group_ids, list):
                group_ids = []
            valid_group_ids = list(
                Group.objects.filter(pk__in=group_ids).values_list('pk', flat=True)
            )
            user.groups.set(valid_group_ids)

        if role_ids is not None:
            if not isinstance(role_ids, list):
                role_ids = []
            valid_role_ids = list(
                Role.objects.filter(pk__in=role_ids).values_list('pk', flat=True)
            )
            user.platform_roles.set(valid_role_ids)

        upsert_profile_preferences(
            user,
            profile_model=Profile,
            profile_language=language,
            profile_timezone=timezone,
            preferred_platform=preferred_platform,
            normalize_platform=normalize_platform_key,
        )

        return Response(
            build_user_payload(
                user,
                role_serializer=ROLE_SUMMARY_SERIALIZER,
                access_profile_builder=get_access_profile,
                normalize_platform=normalize_platform_key,
                **_resolve_user_payload_context(user),
            ),
            status=HTTP_200_OK,
        )


class ManagementGroupListView(APIView):
    """
    GET: List all Django auth groups for management console.
    POST: Create a new group (name).
    Admin-only.
    """

    permission_classes = [HasRequiredFeature]
    required_feature = 'admin_users'

    def get(self, request):
        page = parse_bounded_int(request.query_params.get('page'), default=1)
        page_size = parse_bounded_int(
            request.query_params.get('page_size'),
            default=20,
        )
        role_prefetch = Prefetch(
            'platform_roles',
            queryset=Role.objects.filter(is_active=True).order_by('name', 'id'),
            to_attr='ordered_roles',
        )
        qs = Group.objects.annotate(
            user_count=Count('user', distinct=True),
            permission_count=Count('permissions', distinct=True),
        ).select_related('jenkins_notification_config').prefetch_related(role_prefetch).order_by('name')
        total = qs.count()
        start = (page - 1) * page_size
        end = start + page_size
        items = [
            build_group_payload(
                group,
                roles=_resolve_group_roles(group),
                role_serializer=ROLE_SUMMARY_SERIALIZER,
            )
            for group in qs[start:end]
        ]
        return Response(
            build_paginated_payload(items, total, page, page_size)
        )

    def post(self, request):
        name = (request.data.get('name') or '').strip()
        notification_settings = request.data.get(
            'jenkins_notification_settings'
        )
        if not name:
            return Response(
                {'detail': 'Group name is required.', 'code': 'name_required'},
                status=HTTP_400_BAD_REQUEST
            )
        if Group.objects.filter(name=name).exists():
            return Response(
                {
                    'detail': 'A group with that name already exists.',
                    'code': 'name_taken',
                },
                status=HTTP_400_BAD_REQUEST
            )
        group = Group.objects.create(name=name)
        if notification_settings is not None:
            config, _ = GroupNotificationConfig.objects.get_or_create(group=group)
            config.notification_emails = [
                str(email).strip()
                for email in (notification_settings.get('notification_emails') or [])
                if str(email).strip()
            ]
            config.notification_webhooks = [
                str(url).strip()
                for url in (notification_settings.get('notification_webhooks') or [])
                if str(url).strip()
            ]
            config.save(
                update_fields=['notification_emails', 'notification_webhooks']
            )
        return Response(
            build_group_payload(
                Group.objects.select_related('jenkins_notification_config').get(pk=group.pk),
                roles=_resolve_group_roles(group),
                role_serializer=ROLE_SUMMARY_SERIALIZER,
            ),
            status=HTTP_201_CREATED,
        )


class ManagementGroupDetailView(APIView):
    """PATCH: Update group name and role bindings."""

    permission_classes = [HasRequiredFeature]
    required_feature = 'admin_users'

    def patch(self, request, group_id):
        group = _get_group_or_404(group_id)
        name = request.data.get('name')
        role_ids = request.data.get('role_ids')
        notification_settings = request.data.get(
            'jenkins_notification_settings'
        )

        if name is not None:
            name = str(name).strip()
            if not name:
                return Response(
                    {'detail': 'Group name is required.', 'code': 'name_required'},
                    status=HTTP_400_BAD_REQUEST,
                )
            if Group.objects.exclude(pk=group.pk).filter(name=name).exists():
                return Response(
                    {
                        'detail': 'A group with that name already exists.',
                        'code': 'name_taken',
                    },
                    status=HTTP_400_BAD_REQUEST,
                )
            group.name = name
            group.save(update_fields=['name'])

        if role_ids is not None:
            if not isinstance(role_ids, list):
                role_ids = []
            valid_role_ids = list(
                Role.objects.filter(pk__in=role_ids).values_list('pk', flat=True)
                )
            group.platform_roles.set(valid_role_ids)

        if notification_settings is not None:
            config, _ = GroupNotificationConfig.objects.get_or_create(group=group)
            emails = notification_settings.get('notification_emails') or []
            webhooks = notification_settings.get('notification_webhooks') or []
            config.notification_emails = [
                str(email).strip()
                for email in emails
                if str(email).strip()
            ]
            config.notification_webhooks = [
                str(url).strip()
                for url in webhooks
                if str(url).strip()
            ]
            config.save(
                update_fields=['notification_emails', 'notification_webhooks']
            )

        group = Group.objects.select_related('jenkins_notification_config').get(
            pk=group.pk
        )

        return Response(
            build_group_payload(
                group,
                roles=_resolve_group_roles(group),
                role_serializer=ROLE_SUMMARY_SERIALIZER,
            ),
            status=HTTP_200_OK,
        )


class ManagementRoleListView(APIView):
    """GET/POST role definitions used for visibility control."""

    permission_classes = [HasRequiredFeature]
    required_feature = 'admin_users'

    def get(self, request):
        page = parse_bounded_int(request.query_params.get('page'), default=1)
        page_size = parse_bounded_int(
            request.query_params.get('page_size'),
            default=20,
        )
        qs = Role.objects.annotate(
            user_count=Count('users', distinct=True),
            group_count=Count('groups', distinct=True),
        ).order_by('name', 'id')
        total = qs.count()
        start = (page - 1) * page_size
        end = start + page_size
        items = [
            ROLE_PAYLOAD_SERIALIZER(role)
            for role in qs[start:end]
        ]
        payload = build_paginated_payload(
            items,
            total,
            page,
            page_size,
            feature_options=serialize_feature_options(),
            operation_permission_options=serialize_operation_permission_options(),
            platform_options=serialize_platform_options(),
        )
        return Response(payload)

    def post(self, request):
        name = str(request.data.get('name') or '').strip()
        visible_features = normalize_feature_keys(
            request.data.get('visible_features')
        )
        preferred_platform = normalize_platform_key(
            request.data.get('preferred_platform')
        )
        operation_permissions = normalize_operation_permission_keys(
            request.data.get('operation_permissions')
        )
        is_active = bool(request.data.get('is_active', True))

        if not name:
            return Response(
                {'detail': 'Role name is required.', 'code': 'name_required'},
                status=HTTP_400_BAD_REQUEST,
            )
        if Role.objects.filter(name=name).exists():
            return Response(
                {
                    'detail': 'A role with that name already exists.',
                    'code': 'name_taken',
                },
                status=HTTP_400_BAD_REQUEST,
            )

        role = Role.objects.create(
            name=name,
            visible_features=visible_features,
            operation_permissions=operation_permissions,
            preferred_platform=preferred_platform,
            is_active=is_active,
        )
        return Response(
            ROLE_PAYLOAD_SERIALIZER(role),
            status=HTTP_201_CREATED,
        )


class ManagementRoleDetailView(APIView):
    """PATCH role definitions."""

    permission_classes = [HasRequiredFeature]
    required_feature = 'admin_users'

    def patch(self, request, role_id):
        role = _get_role_or_404(role_id)

        name = request.data.get('name')
        visible_features = request.data.get('visible_features')
        preferred_platform = request.data.get('preferred_platform')
        is_active = request.data.get('is_active')
        operation_permissions = request.data.get('operation_permissions')

        update_fields = []

        if name is not None:
            name = str(name).strip()
            if not name:
                return Response(
                    {'detail': 'Role name is required.', 'code': 'name_required'},
                    status=HTTP_400_BAD_REQUEST,
                )
            if Role.objects.exclude(pk=role.pk).filter(name=name).exists():
                return Response(
                    {
                        'detail': 'A role with that name already exists.',
                        'code': 'name_taken',
                    },
                    status=HTTP_400_BAD_REQUEST,
                )
            role.name = name
            update_fields.append('name')

        if visible_features is not None:
            role.visible_features = normalize_feature_keys(visible_features)
            update_fields.append('visible_features')

        if preferred_platform is not None:
            role.preferred_platform = normalize_platform_key(preferred_platform)
            update_fields.append('preferred_platform')

        if operation_permissions is not None:
            role.operation_permissions = normalize_operation_permission_keys(
                operation_permissions
            )
            update_fields.append('operation_permissions')

        if is_active is not None:
            role.is_active = bool(is_active)
            update_fields.append('is_active')

        if update_fields:
            role.save(update_fields=update_fields)

        return Response(
            ROLE_PAYLOAD_SERIALIZER(role),
            status=HTTP_200_OK,
        )


def _get_user_or_404(user_id):
    """Load a user or raise 404."""
    try:
        return User.objects.get(pk=user_id)
    except User.DoesNotExist as exc:
        raise Http404 from exc


def _get_group_or_404(group_id):
    """Load a group or raise 404."""
    try:
        return Group.objects.get(pk=group_id)
    except Group.DoesNotExist as exc:
        raise Http404 from exc


def _get_role_or_404(role_id):
    """Load a role or raise 404."""
    try:
        return Role.objects.get(pk=role_id)
    except Role.DoesNotExist as exc:
        raise Http404 from exc
