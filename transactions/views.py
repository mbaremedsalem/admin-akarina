from rest_framework import permissions, viewsets

from .models import Transaction
from .serializers import TransactionSerializer


class TransactionViewSet(viewsets.ModelViewSet):
    """
    Creation d'une vente/location par un client. Le passage au statut
    'confirmee' declenche automatiquement (via signal) le credit de
    points de fidelite au parrain et le blocage du calendrier du bien.
    """

    serializer_class = TransactionSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["statut", "type_transaction", "bien"]

    def get_queryset(self):
        qs = Transaction.objects.select_related("bien", "client")
        if self.request.user.is_staff:
            return qs
        # un client voit ses transactions, un gestionnaire voit celles de ses biens
        from django.db.models import Q
        return qs.filter(Q(client=self.request.user) | Q(bien__gestionnaire=self.request.user))
