from django.db import transaction as db_transaction
from rest_framework import permissions, viewsets

from .models import Cadeau, EchangeCadeau
from .serializers import CadeauSerializer, EchangeCadeauSerializer, EchangeCadeauUpdateSerializer


class CadeauViewSet(viewsets.ModelViewSet):
    queryset = Cadeau.objects.filter(actif=True)
    serializer_class = CadeauSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]


class EchangeCadeauViewSet(viewsets.ModelViewSet):
    """Un utilisateur convertit ses points en cadeau/argent ; seul l'admin peut
    ensuite changer le statut de l'echange (valide/refuse) ou le supprimer."""

    serializer_class = EchangeCadeauSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "patch", "delete", "head"]
    search_fields = ["reference", "utilisateur__username", "cadeau__nom"]

    def get_queryset(self):
        if self.request.user.is_staff:
            return EchangeCadeau.objects.all()
        return EchangeCadeau.objects.filter(utilisateur=self.request.user)

    def get_serializer_class(self):
        if self.action in ("update", "partial_update"):
            return EchangeCadeauUpdateSerializer
        return EchangeCadeauSerializer

    def get_permissions(self):
        if self.action in ("update", "partial_update", "destroy"):
            return [permissions.IsAdminUser()]
        return super().get_permissions()

    @db_transaction.atomic
    def perform_destroy(self, instance):
        if instance.statut != EchangeCadeau.Statut.REFUSE:
            instance.rembourser(f"Remboursement suite a la suppression de l'echange: {instance.cadeau.nom}")
        instance.delete()
