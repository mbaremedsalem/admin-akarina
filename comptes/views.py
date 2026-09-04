from django.contrib.auth import get_user_model
from rest_framework import generics, permissions, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import TransactionPoints
from .serializers import (
    InscriptionSerializer,
    ReinitialisationMotDePasseSerializer,
    TransactionPointsSerializer,
    UtilisateurAdminSerializer,
    UtilisateurSerializer,
)

Utilisateur = get_user_model()


class InscriptionView(generics.CreateAPIView):
    """Creation de compte + rattachement automatique au parrain (code_parrain)."""

    queryset = Utilisateur.objects.all()
    serializer_class = InscriptionSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        utilisateur = Utilisateur.objects.get(id=response.data["id"])
        token, _ = Token.objects.get_or_create(user=utilisateur)
        response.data["token"] = token.key
        response.data["lien_invitation"] = utilisateur.lien_invitation
        return response


class ProfilView(generics.RetrieveUpdateAPIView):
    """
    Le profil de l'utilisateur connecte (avec son lien d'invitation).
    Un utilisateur staff voit/garde ses champs is_staff/is_active dans la
    reponse (utile au frontend admin pour verifier les droits a la
    connexion) ; ce n'est pas une escalade de privileges puisqu'il faut
    deja etre staff pour que ces champs apparaissent.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.request.user.is_staff:
            return UtilisateurAdminSerializer
        return UtilisateurSerializer

    def get_object(self):
        return self.request.user


class UtilisateurViewSet(viewsets.ModelViewSet):
    """
    Liste/detail accessibles a tout utilisateur connecte. La modification
    (privileges is_staff/is_active/est_gestionnaire compris) et la
    suppression sont reservees a l'admin (is_staff) - la creation de
    compte passe par /inscription/, pas par cette vue. "post" reste
    autorise uniquement pour l'action reinitialiser_mot_de_passe : aucune
    URL ne mappe POST vers "create" sur ce viewset.
    """

    queryset = Utilisateur.objects.all()
    http_method_names = ["get", "put", "patch", "post", "delete", "head", "options"]

    def get_serializer_class(self):
        if self.request.user.is_staff:
            return UtilisateurAdminSerializer
        return UtilisateurSerializer

    def get_permissions(self):
        if self.action in ["update", "partial_update", "destroy", "reinitialiser_mot_de_passe"]:
            return [permissions.IsAdminUser()]
        return [permissions.IsAuthenticated()]

    @action(detail=True, methods=["post"], url_path="reinitialiser-mot-de-passe")
    def reinitialiser_mot_de_passe(self, request, pk=None):
        """Permet a un admin de forcer le mot de passe d'un utilisateur (ex: mot de passe oublie)."""
        utilisateur = self.get_object()
        serializer = ReinitialisationMotDePasseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        utilisateur.set_password(serializer.validated_data["nouveau_mot_de_passe"])
        utilisateur.save(update_fields=["password"])
        # Invalide l'ancien jeton pour forcer une reconnexion avec le nouveau mot de passe.
        Token.objects.filter(user=utilisateur).delete()
        return Response({"detail": "Mot de passe reinitialise avec succes."})


class MesPointsView(APIView):
    """Solde de points de fidelite + historique des mouvements."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        mouvements = TransactionPoints.objects.filter(utilisateur=request.user)
        data = TransactionPointsSerializer(mouvements, many=True).data
        return Response({
            "solde_points": request.user.points_fidelite,
            "historique": data,
        })
