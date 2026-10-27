import re
from decimal import Decimal

import pymupdf
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.db import models, transaction
from PIL import Image
from rest_framework import serializers

from comptes.serializers import UtilisateurPublicSerializer
from localisation.models import Quartier, Ville

PDF_RENDER_ZOOM = 4  # ~288 DPI, pour garder les numeros de lot lisibles sur un plan dense

from .models import (
    Bien,
    DetailCeremonie,
    DetailTerrain,
    Equipement,
    Indisponibilite,
    LotDetecte,
    MediaBien,
    PlanQuartier,
    ZonePlan,
)
from .pdf_extraction import extraire_lots, extraire_position, extraire_zones


Utilisateur = get_user_model()


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

        bien = data.get('bien')

        if bien and bien.unite_prix == Bien.UnitePrix.MOIS:
            raise serializers.ValidationError(
                "Les biens en allocation mensuelle n'ont pas de calendrier de disponibilite, "
                "utilisez le statut du bien."
            )

        # Validation des permissions
        request = self.context.get('request')

        if bien and request and not request.user.is_staff:
            if not bien.gestionnaires.filter(id=request.user.id).exists():
                raise serializers.ValidationError(
                    "Seul un gestionnaire du bien peut modifier son calendrier."
                )
        
        return data


class DetailCeremonieSerializer(serializers.ModelSerializer):
    class Meta:
        model = DetailCeremonie
        fields = ["avec_service", "description_service", "description_service_ar", "capacite_personnes"]


class DetailTerrainSerializer(serializers.ModelSerializer):
    class Meta:
        model = DetailTerrain
        fields = [
            "superficie_m2", "longueur_m", "largeur_m", "base_m", "hauteur_m", "hypotenuse_m", "diagonale_m",
            "titre_foncier", "borne", "moughataa", "plan", "numero_lot", "polygone",
        ]
        read_only_fields = ["plan", "numero_lot", "polygone"]


class DetailTerrainLotSerializer(serializers.ModelSerializer):
    """Version allegee de DetailTerrain pour l'affichage carte/liste (plan de lotissement)."""

    class Meta:
        model = DetailTerrain
        fields = [
            "numero_lot", "polygone", "plan", "superficie_m2", "longueur_m", "largeur_m",
            "base_m", "hauteur_m", "hypotenuse_m", "diagonale_m", "moughataa",
        ]


class ParcelleTerrainSerializer(serializers.ModelSerializer):
    """Ecriture dediee de la parcelle (plan/numero_lot/polygone) d'un bien terrain."""

    lot_detecte_id = serializers.PrimaryKeyRelatedField(
        source="lot_detecte", queryset=LotDetecte.objects.filter(statut=LotDetecte.Statut.EN_ATTENTE),
        write_only=True, required=False, allow_null=True,
        help_text="Si ce polygone provient d'un lot auto-detecte en attente, son id : "
        "permet de le marquer automatiquement comme affecte a ce bien.",
    )

    class Meta:
        model = DetailTerrain
        fields = ["plan", "numero_lot", "polygone", "lot_detecte_id"]

    def validate(self, data):
        plan = data.get("plan", getattr(self.instance, "plan", None))
        numero_lot = data.get("numero_lot", getattr(self.instance, "numero_lot", None))
        polygone = data.get("polygone", getattr(self.instance, "polygone", None))
        lot_detecte = data.get("lot_detecte")

        if plan and numero_lot:
            conflit = DetailTerrain.objects.filter(plan=plan, numero_lot=numero_lot)
            if self.instance is not None:
                conflit = conflit.exclude(pk=self.instance.pk)
            if conflit.exists():
                raise serializers.ValidationError(
                    {"numero_lot": "Ce numero de lot est deja utilise sur ce plan."}
                )

        if lot_detecte is not None and plan and lot_detecte.plan_id != plan.id:
            raise serializers.ValidationError(
                {"lot_detecte_id": "Ce lot detecte n'appartient pas au plan indique."}
            )

        if polygone is not None:
            if not isinstance(polygone, list) or len(polygone) < 3:
                raise serializers.ValidationError(
                    {"polygone": "Le polygone doit contenir au moins 3 points."}
                )
            for point in polygone:
                if not isinstance(point, dict) or "lat" not in point or "lng" not in point:
                    raise serializers.ValidationError(
                        {"polygone": "Chaque point du polygone doit avoir 'lat' et 'lng'."}
                    )

        return data

    def update(self, instance, validated_data):
        lot_detecte = validated_data.pop("lot_detecte", None)
        instance = super().update(instance, validated_data)

        # Libere tout lot detecte qui pointait encore vers ce bien mais ne
        # correspond plus a sa parcelle courante (changement de lot, ou
        # detachement via plan/numero_lot/polygone remis a vide).
        correspond_toujours = models.Q(plan=instance.plan, numero_lot=instance.numero_lot) if instance.plan and instance.numero_lot else models.Q(pk=None)
        LotDetecte.objects.filter(bien=instance.bien).exclude(correspond_toujours).update(
            statut=LotDetecte.Statut.EN_ATTENTE, bien=None
        )

        if lot_detecte is not None:
            lot_detecte.statut = LotDetecte.Statut.AFFECTE
            lot_detecte.bien = instance.bien
            lot_detecte.save(update_fields=["statut", "bien"])

        return instance


class LotDetecteSerializer(serializers.ModelSerializer):
    """Lot auto-detecte depuis le PDF d'un plan, en attente/affecte/ignore."""

    class Meta:
        model = LotDetecte
        fields = ["id", "plan", "numero_lot", "polygone_local", "statut"]
        read_only_fields = ["plan", "numero_lot", "polygone_local"]


class ZonePlanSerializer(serializers.ModelSerializer):
    """
    Zone non-vendable d'un plan (espace vert, equipement public,
    mosquee...). nom/description/superficie_m2/longueur_m/largeur_m/
    moughataa/adresse sont modifiables par l'admin ; type_zone/
    polygone_local restent geres par l'extraction automatique. bien :
    rempli une fois la zone "publiee" comme Bien(type_bien=espace).
    """

    bien = serializers.PrimaryKeyRelatedField(
        queryset=Bien.objects.filter(type_bien=Bien.TypeBien.ESPACE), allow_null=True, required=False
    )

    class Meta:
        model = ZonePlan
        fields = [
            "id", "plan", "nom", "type_zone", "description", "moughataa", "adresse",
            "superficie_m2", "longueur_m", "largeur_m", "base_m", "hauteur_m", "hypotenuse_m", "diagonale_m",
            "polygone_local", "bien",
        ]
        read_only_fields = ["plan", "type_zone", "polygone_local"]


class PlanQuartierSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlanQuartier
        fields = [
            "id", "quartier", "nom", "image",
            "centre_latitude", "centre_longitude", "largeur_m", "hauteur_m", "rotation_deg",
            "echelle_m_par_pixel", "actif", "date_creation", "date_modification",
        ]
        read_only_fields = ["date_creation", "date_modification", "echelle_m_par_pixel"]

    def validate_image(self, value):
        """
        Convertit automatiquement un PDF uploade (ex: plan de lotissement
        exporte depuis un logiciel de plan) en image PNG : la premiere page
        est rendue a haute resolution, le PDF original n'est pas conserve.
        Si c'est un PDF, tente aussi d'en extraire automatiquement les lots
        numerotes (voir pdf_extraction.extraire_lots) - stocke pour creation
        differee dans create()/update(), une fois le PlanQuartier sauvegarde -
        et, si le PDF est georeference (GeoPDF, ex: export ArcMap), la
        position exacte du plan (voir pdf_extraction.extraire_position),
        qui rend le positionnement 100% automatique meme pour le tout
        premier plan d'un quartier (voir validate()).
        Lit toujours les dimensions pixel de l'image finale (PDF ou pas),
        necessaires pour heriter l'echelle d'un plan precedent du meme quartier.
        """
        nom = (value.name or "").lower()
        self._lots_extraits = None
        self._zones_extraites = None
        self._position_geopdf = None
        self._image_pixel_largeur = self._image_pixel_hauteur = None

        if nom.endswith(".pdf"):
            pdf_bytes = value.read()
            try:
                document = pymupdf.open(stream=pdf_bytes, filetype="pdf")
                page = document.load_page(0)
                pixmap = page.get_pixmap(matrix=pymupdf.Matrix(PDF_RENDER_ZOOM, PDF_RENDER_ZOOM))
                png_bytes = pixmap.tobytes("png")
                # Dimensions pixel directement depuis le pixmap deja genere :
                # evite de re-decoder le PNG (souvent tres volumineux a ce
                # zoom) juste pour lire sa taille.
                self._image_pixel_largeur, self._image_pixel_hauteur = pixmap.width, pixmap.height
                document.close()
            except Exception:
                raise serializers.ValidationError(
                    "Impossible de convertir ce PDF en image. Verifiez que le fichier n'est pas corrompu."
                )

            try:
                self._lots_extraits = extraire_lots(pdf_bytes)
            except Exception:
                # Best-effort : un echec d'extraction ne doit jamais bloquer
                # l'upload/la conversion du plan, l'admin pourra toujours
                # tracer les lots a la main.
                self._lots_extraits = []

            try:
                self._zones_extraites = extraire_zones(pdf_bytes)
            except Exception:
                self._zones_extraites = []

            self._position_geopdf = extraire_position(pdf_bytes)

            nouveau_nom = re.sub(r"\.pdf$", ".png", value.name, flags=re.IGNORECASE)
            return ContentFile(png_bytes, name=nouveau_nom)

        try:
            value.seek(0)
            with Image.open(value) as img:
                self._image_pixel_largeur, self._image_pixel_hauteur = img.size
            value.seek(0)
        except Exception:
            pass

        return value

    def validate(self, data):
        """
        Determine centre/largeur/hauteur/rotation quand ils ne sont pas
        fournis explicitement :
        1. Si l'image est un GeoPDF georeference, utilise la position
           exacte qui en a ete extraite (voir validate_image) - fonctionne
           meme pour le tout premier plan d'un quartier, aucune saisie
           manuelle. S'applique aussi bien a la creation qu'a un simple
           remplacement d'image sur un plan existant (le GeoPDF est
           toujours la source la plus fiable, meme si un calibrage manuel
           imprecis existait avant).
        2. A la creation uniquement, sinon : herite centre/rotation/echelle
           du plan actif le plus recent du meme quartier (suppose que
           c'est la meme feuille cadastrale).
        3. A la creation, si ni l'un ni l'autre n'est disponible, les
           champs restent requis : aucune donnee GPS n'existe dans un PDF
           plat, impossible de deviner la position.
        """
        position_geopdf = getattr(self, "_position_geopdf", None)
        if position_geopdf is not None:
            for champ, valeur in position_geopdf.items():
                if data.get(champ) is None:
                    data[champ] = Decimal(str(valeur))

        if self.instance is None:
            quartier = data.get("quartier")
            dernier_plan = (
                PlanQuartier.objects.filter(
                    quartier=quartier, actif=True, echelle_m_par_pixel__isnull=False
                )
                .order_by("-date_creation")
                .first()
            )
            pixel_largeur = getattr(self, "_image_pixel_largeur", None)
            pixel_hauteur = getattr(self, "_image_pixel_hauteur", None)

            if dernier_plan is not None:
                if data.get("centre_latitude") is None:
                    data["centre_latitude"] = dernier_plan.centre_latitude
                if data.get("centre_longitude") is None:
                    data["centre_longitude"] = dernier_plan.centre_longitude
                if data.get("rotation_deg") is None:
                    data["rotation_deg"] = dernier_plan.rotation_deg
                if data.get("largeur_m") is None and pixel_largeur:
                    data["largeur_m"] = Decimal(
                        str(round(float(dernier_plan.echelle_m_par_pixel) * pixel_largeur, 2))
                    )
                if data.get("hauteur_m") is None and pixel_hauteur:
                    data["hauteur_m"] = Decimal(
                        str(round(float(dernier_plan.echelle_m_par_pixel) * pixel_hauteur, 2))
                    )

            manquants = [
                champ for champ in ("centre_latitude", "centre_longitude", "largeur_m", "hauteur_m")
                if data.get(champ) is None
            ]
            if manquants:
                message = (
                    "Requis pour le premier plan de ce quartier (aucune position a heriter)."
                    if dernier_plan is None
                    else "Impossible de calculer automatiquement ce champ pour cette image."
                )
                raise serializers.ValidationError({champ: message for champ in manquants})

        return data

    @transaction.atomic
    def create(self, validated_data):
        lots_extraits = getattr(self, "_lots_extraits", None)
        zones_extraites = getattr(self, "_zones_extraites", None)
        plan = super().create(validated_data)
        self._finaliser_echelle_et_lots(plan, lots_extraits, zones_extraites)
        return plan

    @transaction.atomic
    def update(self, instance, validated_data):
        image_remplacee = "image" in validated_data
        lots_extraits = getattr(self, "_lots_extraits", None) if image_remplacee else None
        zones_extraites = getattr(self, "_zones_extraites", None) if image_remplacee else None
        if image_remplacee:
            # Les lots deja confirmes (affecte -> un vrai Bien) restent
            # figes ; seuls les lots encore en attente/ignores de l'ancien
            # rendu sont perimes par le remplacement de l'image.
            instance.lots_detectes.exclude(statut=LotDetecte.Statut.AFFECTE).delete()
            # Des zones existent deja pour ce plan : potentiellement
            # enrichies a la main (nom corrige, description, superficie) -
            # on ne les recree JAMAIS automatiquement pour ne pas ecraser
            # ces saisies. Seule une premiere extraction reussie les peuple.
            if instance.zones.exists():
                zones_extraites = None
        plan = super().update(instance, validated_data)
        if image_remplacee:
            self._finaliser_echelle_et_lots(plan, lots_extraits, zones_extraites)
        return plan

    def _finaliser_echelle_et_lots(self, plan, lots_extraits, zones_extraites=None):
        pixel_largeur = getattr(self, "_image_pixel_largeur", None)
        if pixel_largeur and plan.largeur_m:
            plan.echelle_m_par_pixel = Decimal(str(float(plan.largeur_m) / pixel_largeur))
            plan.save(update_fields=["echelle_m_par_pixel"])
        if lots_extraits:
            LotDetecte.objects.bulk_create(
                [
                    LotDetecte(plan=plan, numero_lot=lot["numero_lot"], polygone_local=lot["polygone_local"])
                    for lot in lots_extraits
                ],
                ignore_conflicts=True,
            )
        if zones_extraites:
            ZonePlan.objects.bulk_create(
                [
                    ZonePlan(
                        plan=plan,
                        nom=zone["nom"],
                        type_zone=zone["type_zone"],
                        polygone_local=zone["polygone_local"],
                    )
                    for zone in zones_extraites
                ]
            )


class BienListSerializer(serializers.ModelSerializer):
    """Version allegee pour les listes/recherches."""

    ville = VilleNomSerializer(read_only=True)
    quartier = QuartierNomSerializer(read_only=True)
    photo_principale = serializers.SerializerMethodField()
    detail_terrain = DetailTerrainLotSerializer(read_only=True)

    class Meta:
        model = Bien
        fields = [
            "id", "reference", "titre", "titre_ar", "type_bien", "type_transaction",
            "prix", "unite_prix", "statut_disponibilite", "meuble", "nb_chambres", "nb_salles_bain",
            "ville", "quartier", "adresse_complete", "latitude", "longitude", "photo_principale", "actif", "vendu",
            "detail_terrain",
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

    gestionnaires = UtilisateurPublicSerializer(many=True, read_only=True)
    gestionnaires_ids = serializers.PrimaryKeyRelatedField(
        source="gestionnaires", queryset=Utilisateur.objects.all(), many=True, write_only=True, required=False
    )
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
            "prix", "unite_prix", "statut_disponibilite",
            "ville", "quartier", "adresse_complete", "adresse_complete_ar", "latitude", "longitude",
            "nb_proprietaires", "gestionnaires", "gestionnaires_ids",
            "equipements", "equipements_ids", "medias", "indisponibilites",
            "detail_ceremonie", "detail_terrain",
            "actif", "vendu", "date_creation", "date_modification",
        ]
        read_only_fields = ["reference", "date_creation", "date_modification"]

    def validate(self, data):
        type_bien = data.get("type_bien", getattr(self.instance, "type_bien", None))
        type_transaction = data.get("type_transaction", getattr(self.instance, "type_transaction", None))
        unite_prix = data.get("unite_prix", getattr(self.instance, "unite_prix", None))

        # Un espace (parc, equipement public...) suit la meme regle qu'un
        # terrain : vendu a prix fixe (coherent avec Bien.clean()).
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
        gestionnaires = validated_data.pop("gestionnaires", None)

        bien = Bien.objects.create(**validated_data)
        bien.equipements.set(equipements)
        # Si l'admin n'a pas explicitement choisi de gestionnaires, celui qui
        # cree le bien en devient gestionnaire par defaut.
        bien.gestionnaires.set(gestionnaires if gestionnaires else [self.context["request"].user])

        if bien.type_bien == Bien.TypeBien.CEREMONIE and detail_ceremonie_data:
            DetailCeremonie.objects.create(bien=bien, **detail_ceremonie_data)
        # DetailTerrain sert aussi aux espaces (superficie/longueur/largeur/
        # moughataa/plan/polygone) : memes champs, pas de modele duplique.
        if bien.type_bien in (Bien.TypeBien.TERRAIN, Bien.TypeBien.ESPACE) and detail_terrain_data:
            DetailTerrain.objects.create(bien=bien, **detail_terrain_data)
        return bien

    @transaction.atomic
    def update(self, instance, validated_data):
        detail_ceremonie_data = validated_data.pop("detail_ceremonie", None)
        detail_terrain_data = validated_data.pop("detail_terrain", None)
        equipements = validated_data.pop("equipements", None)
        gestionnaires = validated_data.pop("gestionnaires", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if equipements is not None:
            instance.equipements.set(equipements)
        if gestionnaires is not None:
            instance.gestionnaires.set(gestionnaires)

        if detail_ceremonie_data is not None:
            DetailCeremonie.objects.update_or_create(bien=instance, defaults=detail_ceremonie_data)
        if detail_terrain_data is not None:
            DetailTerrain.objects.update_or_create(bien=instance, defaults=detail_terrain_data)

        return instance
