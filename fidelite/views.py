from rest_framework import permissions, viewsets

from .models import Cadeau, EchangeCadeau
from .serializers import CadeauSerializer, EchangeCadeauSerializer


class CadeauViewSet(viewsets.ModelViewSet):
    queryset = Cadeau.objects.filter(actif=True)
    serializer_class = CadeauSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]


class EchangeCadeauViewSet(viewsets.ModelViewSet):
    """Un utilisateur convertit ses points en cadeau/argent."""

    serializer_class = EchangeCadeauSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "head"]

    def get_queryset(self):
        if self.request.user.is_staff:
            return EchangeCadeau.objects.all()
        return EchangeCadeau.objects.filter(utilisateur=self.request.user)
