from django.urls import path

from .views import (
    BienViewSet,
    EquipementViewSet,
    IndisponibiliteViewSet,
    LotDetecteViewSet,
    MediaBienViewSet,
    ParcelleTerrainView,
    PlanQuartierViewSet,
    ZonePlanViewSet,
)

LIST_CREATE = {"get": "list", "post": "create"}
DETAIL = {"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}
LIST_ONLY = {"get": "list"}
DETAIL_EDIT = {"get": "retrieve", "patch": "partial_update"}

urlpatterns = [
    path("biens/", BienViewSet.as_view(LIST_CREATE), name="bien-list"),
    path("biens/<str:reference>/", BienViewSet.as_view(DETAIL), name="bien-detail"),
    path("biens/<str:reference>/parcelle/", ParcelleTerrainView.as_view(), name="bien-parcelle"),
    path("equipements/", EquipementViewSet.as_view(LIST_CREATE), name="equipement-list"),
    path("equipements/<int:pk>/", EquipementViewSet.as_view(DETAIL), name="equipement-detail"),
    path("medias/", MediaBienViewSet.as_view(LIST_CREATE), name="media-bien-list"),
    path("medias/<int:pk>/", MediaBienViewSet.as_view(DETAIL), name="media-bien-detail"),
    path("indisponibilites/", IndisponibiliteViewSet.as_view(LIST_CREATE), name="indisponibilite-list"),
    path("indisponibilites/<int:pk>/", IndisponibiliteViewSet.as_view(DETAIL), name="indisponibilite-detail"),
    path("plans-quartier/", PlanQuartierViewSet.as_view(LIST_CREATE), name="plan-quartier-list"),
    path("plans-quartier/<int:pk>/", PlanQuartierViewSet.as_view(DETAIL), name="plan-quartier-detail"),
    path("lots-detectes/", LotDetecteViewSet.as_view(LIST_CREATE), name="lot-detecte-list"),
    path("lots-detectes/<int:pk>/", LotDetecteViewSet.as_view(DETAIL), name="lot-detecte-detail"),
    path("zones-plan/", ZonePlanViewSet.as_view(LIST_ONLY), name="zone-plan-list"),
    path("zones-plan/<int:pk>/", ZonePlanViewSet.as_view(DETAIL_EDIT), name="zone-plan-detail"),
]
