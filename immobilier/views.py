from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status, viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from .filters import BienFilter
from .models import Bien, Equipement, Indisponibilite, LotDetecte, MediaBien, PlanQuartier, ZonePlan
from .permissions import EstGestionnaireOuLectureSeule, EstStaffOuLectureSeule
from .serializers import (
    BienDetailSerializer,
    BienListSerializer,
    EquipementSerializer,
    IndisponibiliteSerializer,
    LotDetecteSerializer,
    MediaBienSerializer,
    ParcelleTerrainSerializer,
    PlanQuartierSerializer,
    ZonePlanSerializer,
)


class EquipementViewSet(viewsets.ModelViewSet):
    queryset = Equipement.objects.all()
    serializer_class = EquipementSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]


class BienViewSet(viewsets.ModelViewSet):
    """
    CRUD complet sur les biens.
    - Lecture publique, avec recherche/filtres (ville, type, prix, dispo...).
    - Ecriture reservee au gestionnaire du bien.
    - Recuperation par reference unique : /api/biens/par-reference/<reference>/
    """

    queryset = (
        Bien.objects.select_related("ville", "quartier", "detail_ceremonie", "detail_terrain")
        .prefetch_related("equipements", "medias", "indisponibilites", "gestionnaires")
        .all()
    )
    permission_classes = [EstGestionnaireOuLectureSeule]
    filterset_class = BienFilter
    search_fields = ["titre", "description", "reference", "adresse_complete"]
    ordering_fields = ["prix", "date_creation", "nb_chambres"]
    lookup_field = "reference"
    lookup_value_regex = "[^/]+"

    def get_serializer_class(self):
        if self.action == "list":
            return BienListSerializer
        return BienDetailSerializer


class MediaBienViewSet(viewsets.ModelViewSet):
    """
    Ajout/suppression de photos et videos pour un bien (bien=<id> en query param a la creation).

    Pour ajouter plusieurs fichiers en un seul appel, repeter le champ
    'fichier' plusieurs fois dans le formdata (meme cle, un fichier par
    valeur) : chaque fichier devient un MediaBien separe, avec le meme
    bien/type_media/legende.
    """

    queryset = MediaBien.objects.select_related("bien").all()
    serializer_class = MediaBienSerializer
    permission_classes = [EstGestionnaireOuLectureSeule]
    parser_classes = [MultiPartParser, FormParser]
    filterset_fields = ["bien", "type_media"]

    def create(self, request, *args, **kwargs):
        fichiers = request.FILES.getlist("fichier")
        if len(fichiers) <= 1:
            return super().create(request, *args, **kwargs)

        # request.data (QueryDict) contient aussi les fichiers deja uploades ;
        # request.data.copy() les deepcopy tous, ce qui plante des qu'un fichier
        # depasse FILE_UPLOAD_MAX_MEMORY_SIZE et devient un TemporaryUploadedFile
        # (handle de fichier non picklable). On extrait donc une seule fois les
        # champs texte partages, sans jamais copier le QueryDict complet.
        champs_partages = {
            "type_media": request.data.get("type_media"),
            "legende": request.data.get("legende", ""),
        }
        ordre = request.data.get("ordre")
        if ordre is not None:
            champs_partages["ordre"] = ordre

        # Tout ou rien : si un fichier echoue (validation, permission...) au
        # milieu du lot, on annule les medias deja crees plutot que de
        # laisser un upload partiel/incoherent (ex: 19 images sur 35).
        with transaction.atomic():
            created = []
            for fichier in fichiers:
                data = {**champs_partages, "fichier": fichier}
                serializer = self.get_serializer(data=data)
                serializer.is_valid(raise_exception=True)
                self.perform_create(serializer)
                created.append(serializer.data)

        return Response(created, status=status.HTTP_201_CREATED)

    def perform_create(self, serializer):
        bien = serializer.validated_data.get("bien")
        if bien is None:
            bien_id = self.request.data.get("bien")
            bien = Bien.objects.filter(id=bien_id).first()
        if bien is None:
            raise ValidationError({"bien": "Ce champ est requis."})
        if not bien.gestionnaires.filter(id=self.request.user.id).exists() and not self.request.user.is_staff:
            raise ValidationError("Seul un gestionnaire du bien peut ajouter des medias.")
        serializer.save(bien=bien)


class IndisponibiliteViewSet(viewsets.ModelViewSet):
    """
    Calendrier de disponibilite : le gestionnaire bloque des periodes
    (un jour, plusieurs jours, un ou plusieurs mois) pour son bien.
    """

    queryset = Indisponibilite.objects.select_related("bien").all()
    serializer_class = IndisponibiliteSerializer
    permission_classes = [EstGestionnaireOuLectureSeule]
    filterset_fields = ["bien"]

    def perform_create(self, serializer):
        bien = serializer.validated_data["bien"]
        if not bien.gestionnaires.filter(id=self.request.user.id).exists() and not self.request.user.is_staff:
            raise ValidationError("Seul un gestionnaire du bien peut modifier son calendrier.")
        serializer.save()


class PlanQuartierViewSet(viewsets.ModelViewSet):
    """
    Plans de lotissement (image + positionnement geographique) rattaches a
    un quartier. Lecture publique (affichage carte cote client), ecriture
    reservee au staff (cartographie back-office).
    """

    queryset = PlanQuartier.objects.select_related("quartier").all()
    serializer_class = PlanQuartierSerializer
    permission_classes = [EstStaffOuLectureSeule]
    parser_classes = [MultiPartParser, FormParser]
    filterset_fields = ["quartier", "actif"]


class LotDetecteViewSet(viewsets.ModelViewSet):
    """
    Lots auto-detectes depuis le PDF d'un plan (en_attente / affecte /
    ignore), consultes et geres par l'outil de digitalisation des plans
    dans l'admin. Lecture publique (coherent avec PlanQuartierViewSet),
    ecriture (ex: marquer "ignore") reservee au staff.
    """

    queryset = LotDetecte.objects.select_related("plan").all()
    serializer_class = LotDetecteSerializer
    permission_classes = [EstStaffOuLectureSeule]
    filterset_fields = ["plan", "statut"]


class ZonePlanViewSet(viewsets.ModelViewSet):
    """
    Zones nommees non-vendables d'un plan (espace vert, equipement public,
    mosquee...). Geometrie/type extraits automatiquement a l'upload ; nom/
    description/superficie modifiables par le staff en cliquant la zone
    dans l'editeur de plan (seul partial_update est route, voir urls.py -
    pas de creation/suppression manuelle, uniquement via re-upload du plan).
    """

    queryset = ZonePlan.objects.select_related("plan").all()
    serializer_class = ZonePlanSerializer
    permission_classes = [EstStaffOuLectureSeule]
    filterset_fields = ["plan", "type_zone"]


class ParcelleTerrainView(generics.GenericAPIView):
    """
    Mise a jour dediee de la parcelle (plan / numero_lot / polygone) d'un
    bien terrain ou espace (DetailTerrain sert aux deux - voir
    BienDetailSerializer.create), utilisee par l'outil de digitalisation
    des plans dans l'admin. Reservee au staff.
    """

    serializer_class = ParcelleTerrainSerializer
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, reference):
        if not request.user.is_staff:
            raise PermissionDenied("Seul un administrateur peut modifier le decoupage d'un plan.")
        bien = get_object_or_404(
            Bien, reference=reference, type_bien__in=[Bien.TypeBien.TERRAIN, Bien.TypeBien.ESPACE]
        )
        detail_terrain = getattr(bien, "detail_terrain", None)
        if detail_terrain is None:
            raise ValidationError("Ce bien n'a pas encore de fiche terrain (detail_terrain).")
        serializer = self.get_serializer(detail_terrain, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
