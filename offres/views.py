from django.utils import timezone
from rest_framework import permissions, viewsets

from .models import Offre
from .serializers import OffreSerializer


class OffreViewSet(viewsets.ModelViewSet):
    """
    'Panier' des publicites/offres Agharina. Lecture publique (le panier
    affiche uniquement les offres actives et en cours de validite),
    ecriture reservee au staff (equipe Agharina).
    """

    serializer_class = OffreSerializer
    filterset_fields = ["type_offre", "bien", "actif"]

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [permissions.IsAdminUser()]
        return [permissions.AllowAny()]

    def get_queryset(self):
        qs = Offre.objects.select_related("bien").all()
        if self.action == "list" and not self.request.user.is_staff:
            aujourdhui = timezone.now().date()
            qs = qs.filter(actif=True, date_debut__lte=aujourdhui, date_fin__gte=aujourdhui)
        return qs
