from django.conf import settings
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.analytics.services import analytics_enabled, get_analytics_connection


class AnalyticsStatusAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        enabled = analytics_enabled()
        connected = False

        if enabled:
            try:
                with get_analytics_connection() as connection:
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT 1")
                        connected = cursor.fetchone()[0] == 1
            except Exception:
                connected = False

        return Response(
            {
                "enabled": enabled,
                "connected": connected,
                "metabase_url": settings.METABASE_URL,
            }
        )

