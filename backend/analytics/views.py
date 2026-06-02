"""Lookmypart analytics — market scrape results are exposed on vehicle APIs."""

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


class AnalyticsHealthView(APIView):
    """Lightweight check that the analytics app is wired (auth required)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"status": "ok", "service": "analytics"})
