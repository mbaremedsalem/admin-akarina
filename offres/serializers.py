from rest_framework import serializers

from .models import Offre


class OffreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Offre
        fields = [
            "id", "titre", "titre_ar", "description", "description_ar", "type_offre", "image", "bien",
            "reduction_pourcentage", "date_debut", "date_fin", "actif", "date_creation",
        ]
