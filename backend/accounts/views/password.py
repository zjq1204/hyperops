"""
Password-related views.

Handles password reset functionality including sending reset emails
and confirming password resets.
"""

import logging

from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.utils.decorators import method_decorator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_exempt

from drf_spectacular.utils import extend_schema

from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from platformkit.auth import ensure_password_auth_enabled

from ..serializers import (
    PasswordResetConfirmSerializer,
    CustomPasswordResetSerializer,
    SuccessResponseSerializer,
)
from ..services import PasswordResetEmailService

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class SendPasswordResetEmailView(APIView):
    """
    Send password reset email with verification link.

    This endpoint is used for both:
    1. Forgot password (unauthenticated users provide email)
    2. Change password (authenticated users, email from request.user)

    Only email-registered users can use this feature.
    OAuth users will be rejected.
    """
    permission_classes = [AllowAny]

    @extend_schema(
        tags=['auth'],
        summary=_("Send password reset email"),
        request=CustomPasswordResetSerializer,
        responses={200: SuccessResponseSerializer}
    )
    def post(self, request):
        """
        Send password reset verification email.
        """
        if request.user.is_authenticated:
            email = request.user.email
            user = request.user

            try:
                ensure_password_auth_enabled(user)
            except serializers.ValidationError as exc:
                return Response(
                    {
                        'success': False,
                        'error': exc.detail[0],
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            serializer = CustomPasswordResetSerializer(data=request.data)

            if not serializer.is_valid():
                return Response(
                    {
                        'success': False,
                        'errors': serializer.errors
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            email = serializer.validated_data['email']
            user = serializer.user

        try:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)

            language = user.profile.language

            success = PasswordResetEmailService.send_password_reset_email(
                email=email,
                uid=uid,
                token=token,
                language=language
            )

            if success:
                logger.info(
                    f"Sent password reset email to {email}"
                )
                return Response(
                    {
                        'success': True,
                        'message': _(
                            'Password reset email sent successfully'
                        )
                    },
                    status=status.HTTP_200_OK
                )
            else:
                logger.error(
                    f"Password reset email send failed - "
                    f"Email: {email}",
                    extra={
                        'email': email,
                        'endpoint': 'password_reset_send',
                        'error_type': 'email_send_failed',
                    }
                )
                return Response(
                    {
                        'success': False,
                        'error': _('Failed to send password reset email'),
                        'error_detail': (
                            'Email service returned failure. '
                            'Check email configuration and SMTP settings.'
                        ),
                        'error_code': 'EMAIL_SEND_FAILED'
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        except User.DoesNotExist:
            logger.warning(
                f"Password reset email failed: User not found - "
                f"Email: {email}",
                extra={
                    'email': email,
                    'endpoint': 'password_reset_send',
                    'error_type': 'user_not_found',
                }
            )
            return Response(
                {
                    'success': False,
                    'error': _('User with this email does not exist'),
                    'error_code': 'USER_NOT_FOUND'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            error_type = type(e).__name__
            error_message = str(e)
            client_ip = request.META.get('REMOTE_ADDR', 'unknown')
            logger.error(
                f"Error in password reset email flow - "
                f"IP: {client_ip}, "
                f"Email: {email}, "
                f"Error: {error_type}: {error_message}",
                exc_info=True,
                extra={
                    'client_ip': client_ip,
                    'email': email,
                    'exception_type': error_type,
                    'exception_message': error_message,
                    'endpoint': 'password_reset_send',
                    'error_type': 'password_reset_error',
                }
            )

            if 'email' in error_message.lower() or 'SMTP' in error_message:
                error_code = 'EMAIL_SEND_ERROR'
            else:
                error_code = 'PASSWORD_RESET_ERROR'

            return Response(
                {
                    'success': False,
                    'error': _('Failed to process password reset request'),
                    'error_detail': f'{error_type}: {error_message}',
                    'error_code': error_code
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@method_decorator(csrf_exempt, name='dispatch')
class ConfirmPasswordResetView(APIView):
    """
    Confirm password reset with uid, token, and new password.

    This is the final step where user submits new password
    after clicking the link in the email.
    """
    permission_classes = [AllowAny]

    @extend_schema(
        tags=['auth'],
        summary=_("Confirm password reset"),
        request=PasswordResetConfirmSerializer,
        responses={200: SuccessResponseSerializer}
    )
    def post(self, request):
        """
        Confirm password reset.
        """
        serializer = PasswordResetConfirmSerializer(data=request.data)
        if not serializer.is_valid():
            error_detail = serializer.errors
            if 'non_field_errors' in error_detail:
                message = error_detail['non_field_errors'][0]
            else:
                first_error = next(iter(error_detail.values()))
                message = (
                    first_error[0]
                    if isinstance(first_error, list)
                    else first_error
                )
            return Response(
                {
                    'success': False,
                    'error': message,
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        uid = serializer.validated_data['uid']
        token = serializer.validated_data['token']
        new_password1 = serializer.validated_data['new_password1']

        try:
            user_id = urlsafe_base64_decode(uid).decode()
            user = User.objects.get(pk=user_id)
        except (
            TypeError,
            ValueError,
            OverflowError,
            User.DoesNotExist
        ) as e:
            error_type = type(e).__name__
            error_message = str(e)
            client_ip = request.META.get('REMOTE_ADDR', 'unknown')
            logger.warning(
                f"Password reset confirmation failed: Invalid reset link - "
                f"IP: {client_ip}, "
                f"Error: {error_type}: {error_message}",
                extra={
                    'client_ip': client_ip,
                    'exception_type': error_type,
                    'exception_message': error_message,
                    'endpoint': 'password_reset_confirm',
                    'error_type': 'invalid_reset_link',
                }
            )
            return Response(
                {
                    'success': False,
                    'error': _('Invalid reset link'),
                    'error_detail': f'{error_type}: {error_message}',
                    'error_code': 'INVALID_RESET_LINK'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if not default_token_generator.check_token(user, token):
            return Response(
                {
                    'success': False,
                    'error': _(
                        'Invalid or expired reset link'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user.set_password(new_password1)
            user.save()

            logger.info(
                f"Password reset successful for user: {user.email}"
            )

            return Response(
                {
                    'success': True,
                    'message': _(
                        'Password has been reset successfully'
                    )
                },
                status=status.HTTP_200_OK
            )

        except Exception as e:
            error_type = type(e).__name__
            error_message = str(e)
            client_ip = request.META.get('REMOTE_ADDR', 'unknown')
            logger.error(
                f"Error resetting password - "
                f"IP: {client_ip}, "
                f"Email: {user.email}, "
                f"Error: {error_type}: {error_message}",
                exc_info=True,
                extra={
                    'client_ip': client_ip,
                    'email': user.email,
                    'user_id': user.id,
                    'exception_type': error_type,
                    'exception_message': error_message,
                    'endpoint': 'password_reset_confirm',
                    'error_type': 'password_reset_failed',
                }
            )

            if isinstance(e, ValueError):
                error_code = 'VALIDATION_ERROR'
            elif 'password' in error_message.lower():
                error_code = 'PASSWORD_ERROR'
            else:
                error_code = 'PASSWORD_RESET_FAILED'

            return Response(
                {
                    'success': False,
                    'error': _('Failed to reset password'),
                    'error_detail': f'{error_type}: {error_message}',
                    'error_code': error_code
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
