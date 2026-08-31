from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


class ObjectStorageOverviewView(APIView):
    """Reserve the authenticated phase-one overview contract."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(
            {
                "detail": "Object storage is not configured",
                "error_code": "OBJECT_STORAGE_NOT_CONFIGURED",
            },
            status=503,
        )
