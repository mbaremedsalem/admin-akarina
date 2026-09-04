from rest_framework import permissions, viewsets

from .models import Quartier, Ville
from .serializers import QuartierSerializer, VilleSerializer


class VilleViewSet(viewsets.ModelViewSet):
    queryset = Ville.objects.prefetch_related("quartiers").all()
    serializer_class = VilleSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filterset_fields = ["region", "pays"]
    search_fields = ["nom"]


class QuartierViewSet(viewsets.ModelViewSet):
    queryset = Quartier.objects.select_related("ville").all()
    serializer_class = QuartierSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filterset_fields = ["ville"]
    search_fields = ["nom"]
