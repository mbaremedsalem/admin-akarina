from rest_framework import serializers

from .models import Quartier, Ville


class QuartierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Quartier
        fields = ["id", "ville", "nom", "nom_ar"]


class VilleSerializer(serializers.ModelSerializer):
    quartiers = QuartierSerializer(many=True, read_only=True)

    class Meta:
        model = Ville
        fields = ["id", "nom", "nom_ar", "region", "pays", "quartiers"]
