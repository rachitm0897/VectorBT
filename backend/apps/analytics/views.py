from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.analytics.services import analytics_status


class AnalyticsStatusAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, _request):
        return Response(analytics_status(), status=status.HTTP_200_OK)
