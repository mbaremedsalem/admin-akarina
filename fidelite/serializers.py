from django.db import transaction as db_transaction
from rest_framework import serializers

from comptes.models import TransactionPoints

from .models import Cadeau, EchangeCadeau


class CadeauSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cadeau
        fields = ["id", "nom", "description", "points_necessaires", "valeur_argent", "image", "stock", "actif"]


class EchangeCadeauSerializer(serializers.ModelSerializer):
    class Meta:
        model = EchangeCadeau
        fields = ["id", "utilisateur", "cadeau", "points_utilises", "statut", "date_creation"]
        read_only_fields = ["utilisateur", "points_utilises", "statut", "date_creation"]

    @db_transaction.atomic
    def create(self, validated_data):
        utilisateur = self.context["request"].user
        cadeau = validated_data["cadeau"]

        if not cadeau.actif or cadeau.stock <= 0:
            raise serializers.ValidationError("Ce cadeau n'est plus disponible.")
        if utilisateur.points_fidelite < cadeau.points_necessaires:
            raise serializers.ValidationError("Points de fidelite insuffisants.")

        utilisateur.points_fidelite -= cadeau.points_necessaires
        utilisateur.save(update_fields=["points_fidelite"])

        cadeau.stock -= 1
        cadeau.save(update_fields=["stock"])

        TransactionPoints.objects.create(
            utilisateur=utilisateur,
            type_mouvement=TransactionPoints.TypeMouvement.CONVERTI,
            points=-cadeau.points_necessaires,
            description=f"Conversion contre le cadeau: {cadeau.nom}",
        )

        return EchangeCadeau.objects.create(
            utilisateur=utilisateur,
            cadeau=cadeau,
            points_utilises=cadeau.points_necessaires,
        )
