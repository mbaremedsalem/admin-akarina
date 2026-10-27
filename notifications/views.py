from rest_framework import mixins, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import DeviceToken
from .serializers import DeviceTokenSerializer


class DeviceTokenViewSet(mixins.CreateModelMixin, viewsets.GenericViewSet):
    """Enregistrement des jetons FCM (web/Android/iOS) depuis les frontends.
    Ouvert aux visiteurs non connectes : ils doivent pouvoir recevoir les
    notifications de nouveaux biens/offres sans etre inscrits."""

    queryset = DeviceToken.objects.all()
    serializer_class = DeviceTokenSerializer
    permission_classes = [permissions.AllowAny]

    @action(detail=False, methods=["post"])
    def unregister(self, request):
        token = request.data.get("token")
        if token:
            DeviceToken.objects.filter(token=token).update(actif=False)
        return Response(status=204)
