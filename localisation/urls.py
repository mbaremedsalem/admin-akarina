from django.urls import path

from .views import QuartierViewSet, VilleViewSet

LIST_CREATE = {"get": "list", "post": "create"}
DETAIL = {"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}

urlpatterns = [
    path("villes/", VilleViewSet.as_view(LIST_CREATE), name="ville-list"),
    path("villes/<int:pk>/", VilleViewSet.as_view(DETAIL), name="ville-detail"),
    path("quartiers/", QuartierViewSet.as_view(LIST_CREATE), name="quartier-list"),
    path("quartiers/<int:pk>/", QuartierViewSet.as_view(DETAIL), name="quartier-detail"),
]
