from django.urls import path

from .views import BienViewSet, EquipementViewSet, IndisponibiliteViewSet, MediaBienViewSet

LIST_CREATE = {"get": "list", "post": "create"}
DETAIL = {"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}

urlpatterns = [
    path("biens/", BienViewSet.as_view(LIST_CREATE), name="bien-list"),
    path("biens/<str:reference>/", BienViewSet.as_view(DETAIL), name="bien-detail"),
    path("equipements/", EquipementViewSet.as_view(LIST_CREATE), name="equipement-list"),
    path("equipements/<int:pk>/", EquipementViewSet.as_view(DETAIL), name="equipement-detail"),
    path("medias/", MediaBienViewSet.as_view(LIST_CREATE), name="media-bien-list"),
    path("medias/<int:pk>/", MediaBienViewSet.as_view(DETAIL), name="media-bien-detail"),
    path("indisponibilites/", IndisponibiliteViewSet.as_view(LIST_CREATE), name="indisponibilite-list"),
    path("indisponibilites/<int:pk>/", IndisponibiliteViewSet.as_view(DETAIL), name="indisponibilite-detail"),
]
