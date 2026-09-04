from rest_framework import serializers

from immobilier.models import Bien, Indisponibilite

from .models import Transaction


class TransactionSerializer(serializers.ModelSerializer):
    bien_reference = serializers.CharField(source="bien.reference", read_only=True)

    class Meta:
        model = Transaction
        fields = [
            "id", "reference", "bien", "bien_reference", "client", "type_transaction",
            "date_debut", "date_fin", "montant_total", "statut",
            "date_creation", "date_modification",
        ]
        read_only_fields = ["reference", "client", "date_creation", "date_modification"]

    def validate(self, data):
        bien = data.get("bien", getattr(self.instance, "bien", None))
        type_transaction = data.get("type_transaction", getattr(self.instance, "type_transaction", None))
        date_debut = data.get("date_debut", getattr(self.instance, "date_debut", None))
        date_fin = data.get("date_fin", getattr(self.instance, "date_fin", None))

        if type_transaction == Bien.TypeTransaction.LOCATION:
            if not (date_debut and date_fin):
                raise serializers.ValidationError("Une location necessite une date de debut et une date de fin.")
            if date_fin < date_debut:
                raise serializers.ValidationError("La date de fin doit etre posterieure a la date de debut.")
            if bien and not Indisponibilite.est_disponible(bien, date_debut, date_fin):
                raise serializers.ValidationError("Le bien n'est pas disponible sur cette periode.")
        return data

    def create(self, validated_data):
        validated_data["client"] = self.context["request"].user
        return super().create(validated_data)
