"""Lightweight meta endpoints for the SPA bootstrap."""

from django.conf import settings
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


class PlatformMetaView(APIView):
    """Expose platform feature flags to the SPA bootstrap."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(
            {
                "enable_notifier": bool(
                    getattr(settings, "ENABLE_NOTIFIER", False)
                ),
                "enable_agentcore_task": bool(
                    getattr(settings, "ENABLE_AGENTCORE_TASK", False)
                ),
                "enable_agentcore_metering": bool(
                    getattr(settings, "ENABLE_AGENTCORE_METERING", False)
                ),
                "enable_monitoring": bool(
                    getattr(settings, "ENABLE_MONITORING", False)
                ),
            }
        )
