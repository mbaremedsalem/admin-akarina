from django.urls import path
from rest_framework.authtoken.views import obtain_auth_token

from .views import InscriptionView, MesPointsView, ProfilView, UtilisateurViewSet

urlpatterns = [
    path("inscription/", InscriptionView.as_view(), name="inscription"),
    path("connexion/", obtain_auth_token, name="connexion"),
    path("profil/", ProfilView.as_view(), name="profil"),
    path("mes-points/", MesPointsView.as_view(), name="mes-points"),
    path("utilisateurs/", UtilisateurViewSet.as_view({"get": "list"}), name="utilisateur-list"),
    path(
        "utilisateurs/<int:pk>/",
        UtilisateurViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}),
        name="utilisateur-detail",
    ),
    path(
        "utilisateurs/<int:pk>/reinitialiser-mot-de-passe/",
        UtilisateurViewSet.as_view({"post": "reinitialiser_mot_de_passe"}),
        name="utilisateur-reset-password",
    ),
]
