from django.urls import path

from .views import CadeauViewSet, EchangeCadeauViewSet

LIST_CREATE = {"get": "list", "post": "create"}
DETAIL = {"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}

urlpatterns = [
    path("cadeaux/", CadeauViewSet.as_view(LIST_CREATE), name="cadeau-list"),
    path("cadeaux/<int:pk>/", CadeauViewSet.as_view(DETAIL), name="cadeau-detail"),
    path("echanges-cadeaux/", EchangeCadeauViewSet.as_view(LIST_CREATE), name="echange-cadeau-list"),
    path("echanges-cadeaux/<int:pk>/", EchangeCadeauViewSet.as_view(DETAIL), name="echange-cadeau-detail"),
]
