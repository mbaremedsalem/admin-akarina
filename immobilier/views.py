from rest_framework import permissions, status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from .filters import BienFilter
from .models import Bien, Equipement, Indisponibilite, MediaBien
from .permissions import EstGestionnaireOuLectureSeule
from .serializers import (
    BienDetailSerializer,
    BienListSerializer,
    EquipementSerializer,
    IndisponibiliteSerializer,
    MediaBienSerializer,
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
        Bien.objects.select_related("ville", "quartier", "gestionnaire", "detail_ceremonie", "detail_terrain")
        .prefetch_related("equipements", "medias", "indisponibilites")
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

    def get_queryset(self):
        qs = super().get_queryset()
        if self.action == "list" and not self.request.query_params.get("actif"):
            qs = qs.filter(actif=True)
        return qs


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

        created = []
        for fichier in fichiers:
            data = request.data.copy()
            data["fichier"] = fichier
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
        if bien.gestionnaire_id != self.request.user.id and not self.request.user.is_staff:
            raise ValidationError("Seul le gestionnaire du bien peut ajouter des medias.")
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
        if bien.gestionnaire_id != self.request.user.id and not self.request.user.is_staff:
            raise ValidationError("Seul le gestionnaire du bien peut modifier son calendrier.")
        serializer.save()
