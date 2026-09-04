import django_filters as filters

from .models import Bien, Indisponibilite


class BienFilter(filters.FilterSet):
    prix_min = filters.NumberFilter(field_name="prix", lookup_expr="gte")
    prix_max = filters.NumberFilter(field_name="prix", lookup_expr="lte")
    ville = filters.NumberFilter(field_name="ville_id")
    quartier = filters.NumberFilter(field_name="quartier_id")
    disponible_du = filters.DateFilter(method="filtrer_disponibilite")
    disponible_au = filters.DateFilter(method="filtrer_disponibilite")

    class Meta:
        model = Bien
        fields = [
            "type_bien", "type_transaction", "meuble", "unite_prix",
            "nb_chambres", "nb_salles_bain", "ville", "quartier", "actif",
        ]

    def filtrer_disponibilite(self, queryset, name, value):
        # Necessite les 2 parametres disponible_du et disponible_au ensemble.
        date_debut = self.data.get("disponible_du")
        date_fin = self.data.get("disponible_au")
        if date_debut and date_fin:
            biens_indisponibles = Indisponibilite.objects.filter(
                date_debut__lte=date_fin, date_fin__gte=date_debut
            ).values_list("bien_id", flat=True)
            return queryset.exclude(id__in=biens_indisponibles)
        return queryset
