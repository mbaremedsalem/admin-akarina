from rest_framework import serializers

from immobilier.models import Bien, Indisponibilite

from .models import Transaction


class TransactionSerializer(serializers.ModelSerializer):
    bien_reference = serializers.CharField(source="bien.reference", read_only=True)
    bien_titre = serializers.CharField(source="bien.titre", read_only=True)
    bien_titre_ar = serializers.CharField(source="bien.titre_ar", read_only=True)
    client_username = serializers.CharField(source="client.username", read_only=True)
    client_nom = serializers.SerializerMethodField()
    client_email = serializers.CharField(source="client.email", read_only=True)
    client_telephone = serializers.CharField(source="client.telephone", read_only=True)

    class Meta:
        model = Transaction
        fields = [
            "id", "reference", "bien", "bien_reference", "bien_titre", "bien_titre_ar", "client",
            "client_username", "client_nom", "client_email", "client_telephone", "type_transaction",
            "date_debut", "date_fin", "montant_total", "statut",
            "date_creation", "date_modification",
        ]
        read_only_fields = ["reference", "client", "date_creation", "date_modification"]

    def get_client_nom(self, obj):
        return obj.client.get_full_name() or obj.client.username

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
            if bien and bien.unite_prix == Bien.UnitePrix.MOIS:
                if bien.statut_disponibilite != Bien.StatutDisponibilite.DISPONIBLE:
                    raise serializers.ValidationError("Le bien n'est pas disponible actuellement.")
            elif bien and not Indisponibilite.est_disponible(bien, date_debut, date_fin):
                raise serializers.ValidationError("Le bien n'est pas disponible sur cette periode.")
        return data

    def create(self, validated_data):
        validated_data["client"] = self.context["request"].user
        return super().create(validated_data)
