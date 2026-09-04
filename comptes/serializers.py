from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import TransactionPoints

Utilisateur = get_user_model()


class UtilisateurPublicSerializer(serializers.ModelSerializer):
    """Version allegee (affichee comme gestionnaire d'un bien, etc.)."""

    class Meta:
        model = Utilisateur
        fields = ["id", "username", "first_name", "last_name", "telephone"]


class UtilisateurSerializer(serializers.ModelSerializer):
    nb_filleuls = serializers.IntegerField(source="filleuls.count", read_only=True)

    class Meta:
        model = Utilisateur
        fields = [
            "id", "username", "email", "first_name", "last_name", "telephone",
            "est_gestionnaire", "code_invitation", "lien_invitation",
            "invite_par", "points_fidelite", "nb_filleuls", "date_creation",
        ]
        read_only_fields = ["code_invitation", "lien_invitation", "points_fidelite", "date_creation"]


class UtilisateurAdminSerializer(UtilisateurSerializer):
    """
    Utilise uniquement par l'admin (is_staff) pour l'affectation des
    privileges (is_staff, is_active). Ne jamais brancher ces champs sur
    ProfilView : un utilisateur ne doit pas pouvoir se les attribuer lui-meme.
    """

    class Meta(UtilisateurSerializer.Meta):
        fields = UtilisateurSerializer.Meta.fields + ["is_staff", "is_active"]


class ReinitialisationMotDePasseSerializer(serializers.Serializer):
    """Utilise par l'admin pour reinitialiser le mot de passe d'un utilisateur."""

    nouveau_mot_de_passe = serializers.CharField(write_only=True, validators=[validate_password])


class InscriptionSerializer(serializers.ModelSerializer):
    """
    Inscription d'un nouvel utilisateur. Le champ `code_parrain` (optionnel)
    permet de rattacher automatiquement le nouveau compte a son parrain via
    le lien d'invitation recu.
    """

    password = serializers.CharField(write_only=True, validators=[validate_password])
    code_parrain = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = Utilisateur
        fields = [
            "id", "username", "email", "password", "first_name", "last_name",
            "telephone", "est_gestionnaire", "code_parrain",
        ]

    def validate_code_parrain(self, value):
        if value and not Utilisateur.objects.filter(code_invitation=value).exists():
            raise serializers.ValidationError("Code d'invitation invalide.")
        return value

    def create(self, validated_data):
        code_parrain = validated_data.pop("code_parrain", None)
        password = validated_data.pop("password")
        parrain = None
        if code_parrain:
            parrain = Utilisateur.objects.filter(code_invitation=code_parrain).first()

        utilisateur = Utilisateur(invite_par=parrain, **validated_data)
        utilisateur.set_password(password)
        utilisateur.save()
        return utilisateur


class TransactionPointsSerializer(serializers.ModelSerializer):
    class Meta:
        model = TransactionPoints
        fields = ["id", "utilisateur", "type_mouvement", "points", "description", "date_creation"]
        read_only_fields = fields
