from django.urls import path

from .views import OffreViewSet

LIST_CREATE = {"get": "list", "post": "create"}
DETAIL = {"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}

urlpatterns = [
    path("offres/", OffreViewSet.as_view(LIST_CREATE), name="offre-list"),
    path("offres/<int:pk>/", OffreViewSet.as_view(DETAIL), name="offre-detail"),
]
