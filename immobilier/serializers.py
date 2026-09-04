from django.db import transaction
from rest_framework import serializers

from comptes.serializers import UtilisateurPublicSerializer
from localisation.models import Quartier, Ville

from .models import (
    Bien,
    DetailCeremonie,
    DetailTerrain,
    Equipement,
    Indisponibilite,
    MediaBien,
)


class EquipementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Equipement
        fields = ["id", "nom", "nom_ar", "icone"]


class VilleNomSerializer(serializers.ModelSerializer):
    """Version allegee de Ville, utilisee pour l'affichage dans les listes de biens."""

    class Meta:
        model = Ville
        fields = ["id", "nom", "nom_ar"]


class QuartierNomSerializer(serializers.ModelSerializer):
    """Version allegee de Quartier, utilisee pour l'affichage dans les listes de biens."""

    class Meta:
        model = Quartier
        fields = ["id", "nom", "nom_ar"]


class MediaBienSerializer(serializers.ModelSerializer):
    class Meta:
        model = MediaBien
        fields = ["id", "bien", "type_media", "fichier", "legende", "ordre"]
        read_only_fields = ["bien"]


# class IndisponibiliteSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Indisponibilite
#         fields = ["id", "bien", "date_debut", "date_fin", "motif", "date_creation"]
#         read_only_fields = ["date_creation"]

#     def validate(self, data):
#         if data["date_fin"] < data["date_debut"]:
#             raise serializers.ValidationError("La date de fin doit etre posterieure a la date de debut.")
#         return data


class IndisponibiliteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Indisponibilite
        fields = ["id", "bien", "date_debut", "date_fin", "motif", "date_creation"]
        read_only_fields = ["date_creation"]

    def validate(self, data):
        # Vérifier que les dates sont présentes avant de les comparer
        date_debut = data.get('date_debut')
        date_fin = data.get('date_fin')
        
        # Si les deux dates sont présentes, vérifier leur ordre
        if date_debut and date_fin and date_fin < date_debut:
            raise serializers.ValidationError(
                "La date de fin doit être postérieure à la date de début."
            )
        
        # Validation des permissions
        request = self.context.get('request')
        bien = data.get('bien')
        
        if bien and request and not request.user.is_staff:
            if bien.gestionnaire_id != request.user.id:
                raise serializers.ValidationError(
                    "Seul le gestionnaire du bien peut modifier son calendrier."
                )
        
        return data


class DetailCeremonieSerializer(serializers.ModelSerializer):
    class Meta:
        model = DetailCeremonie
        fields = ["avec_service", "description_service", "description_service_ar", "capacite_personnes"]


class DetailTerrainSerializer(serializers.ModelSerializer):
    class Meta:
        model = DetailTerrain
        fields = ["superficie_m2", "longueur_m", "largeur_m", "titre_foncier", "borne"]


class BienListSerializer(serializers.ModelSerializer):
    """Version allegee pour les listes/recherches."""

    ville = VilleNomSerializer(read_only=True)
    quartier = QuartierNomSerializer(read_only=True)
    photo_principale = serializers.SerializerMethodField()

    class Meta:
        model = Bien
        fields = [
            "id", "reference", "titre", "titre_ar", "type_bien", "type_transaction",
            "prix", "unite_prix", "meuble", "nb_chambres", "nb_salles_bain",
            "ville", "quartier", "latitude", "longitude", "photo_principale", "actif",
        ]

    def get_photo_principale(self, obj):
        media = obj.medias.filter(type_media=MediaBien.TypeMedia.IMAGE).first()
        if media and media.fichier:
            request = self.context.get("request")
            url = media.fichier.url
            return request.build_absolute_uri(url) if request else url
        return None


class BienDetailSerializer(serializers.ModelSerializer):
    """Serializer complet : renvoie toutes les infos du bien via sa reference."""

    gestionnaire = UtilisateurPublicSerializer(read_only=True)
    equipements = EquipementSerializer(many=True, read_only=True)
    equipements_ids = serializers.PrimaryKeyRelatedField(
        source="equipements", queryset=Equipement.objects.all(), many=True, write_only=True, required=False
    )
    medias = MediaBienSerializer(many=True, read_only=True)
    indisponibilites = IndisponibiliteSerializer(many=True, read_only=True)

    detail_ceremonie = DetailCeremonieSerializer(required=False, allow_null=True)
    detail_terrain = DetailTerrainSerializer(required=False, allow_null=True)

    ville = serializers.PrimaryKeyRelatedField(queryset=Ville.objects.all())
    quartier = serializers.PrimaryKeyRelatedField(queryset=Quartier.objects.all(), allow_null=True, required=False)

    class Meta:
        model = Bien
        fields = [
            "id", "reference", "titre", "titre_ar", "description", "description_ar", "type_bien", "type_transaction",
            "meuble", "nb_chambres", "nb_salles_bain", "nb_etages",
            "prix", "unite_prix",
            "ville", "quartier", "adresse_complete", "adresse_complete_ar", "latitude", "longitude",
            "nb_proprietaires", "gestionnaire",
            "equipements", "equipements_ids", "medias", "indisponibilites",
            "detail_ceremonie", "detail_terrain",
            "actif", "date_creation", "date_modification",
        ]
        read_only_fields = ["reference", "gestionnaire", "date_creation", "date_modification"]

    def validate(self, data):
        type_bien = data.get("type_bien", getattr(self.instance, "type_bien", None))
        type_transaction = data.get("type_transaction", getattr(self.instance, "type_transaction", None))
        unite_prix = data.get("unite_prix", getattr(self.instance, "unite_prix", None))

        if type_transaction == Bien.TypeTransaction.VENTE and unite_prix != Bien.UnitePrix.FORFAIT:
            raise serializers.ValidationError(
                {"unite_prix": "Un bien a vendre doit avoir un prix fixe (unite_prix = forfait)."}
            )
        if type_transaction == Bien.TypeTransaction.LOCATION and unite_prix == Bien.UnitePrix.FORFAIT:
            raise serializers.ValidationError(
                {"unite_prix": "Un bien a louer doit avoir une unite de prix jour/3jours/mois."}
            )
        if type_bien == Bien.TypeBien.CEREMONIE and not data.get("detail_ceremonie") and self.instance is None:
            raise serializers.ValidationError(
                {"detail_ceremonie": "Les details de la maison de ceremonie sont requis."}
            )
        if type_bien == Bien.TypeBien.TERRAIN and not data.get("detail_terrain") and self.instance is None:
            raise serializers.ValidationError(
                {"detail_terrain": "Les details du terrain sont requis (superficie, etc.)."}
            )
        return data

    @transaction.atomic
    def create(self, validated_data):
        detail_ceremonie_data = validated_data.pop("detail_ceremonie", None)
        detail_terrain_data = validated_data.pop("detail_terrain", None)
        equipements = validated_data.pop("equipements", [])

        validated_data["gestionnaire"] = self.context["request"].user
        bien = Bien.objects.create(**validated_data)
        bien.equipements.set(equipements)

        if bien.type_bien == Bien.TypeBien.CEREMONIE and detail_ceremonie_data:
            DetailCeremonie.objects.create(bien=bien, **detail_ceremonie_data)
        if bien.type_bien == Bien.TypeBien.TERRAIN and detail_terrain_data:
            DetailTerrain.objects.create(bien=bien, **detail_terrain_data)
        return bien

    @transaction.atomic
    def update(self, instance, validated_data):
        detail_ceremonie_data = validated_data.pop("detail_ceremonie", None)
        detail_terrain_data = validated_data.pop("detail_terrain", None)
        equipements = validated_data.pop("equipements", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if equipements is not None:
            instance.equipements.set(equipements)

        if detail_ceremonie_data is not None:
            DetailCeremonie.objects.update_or_create(bien=instance, defaults=detail_ceremonie_data)
        if detail_terrain_data is not None:
            DetailTerrain.objects.update_or_create(bien=instance, defaults=detail_terrain_data)

        return instance
