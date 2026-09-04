import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models


class Utilisateur(AbstractUser):
    """
    Utilisateur Agharina : peut etre simple client, proprietaire/gestionnaire
    de biens, ou administrateur (via is_staff).
    Chaque utilisateur possede un code de parrainage unique qui genere
    automatiquement son "lien d'invitation".
    """
    telephone = models.CharField(max_length=20, blank=True, null=True)
    est_gestionnaire = models.BooleanField(
        default=False,
        help_text="Peut publier et gerer des biens immobiliers.",
    )

    code_invitation = models.CharField(max_length=12, unique=True, editable=False)
    invite_par = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="filleuls",
        help_text="Utilisateur qui a invite ce compte via son lien de parrainage.",
    )

    points_fidelite = models.PositiveIntegerField(default=0)

    date_creation = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.code_invitation:
            self.code_invitation = uuid.uuid4().hex[:10].upper()
        super().save(*args, **kwargs)

    @property
    def lien_invitation(self) -> str:
        return f"https://agharina.com/invite/{self.code_invitation}"

    def __str__(self):
        return self.get_full_name() or self.username


class TransactionPoints(models.Model):
    """
    Historique des mouvements de points de fidelite d'un utilisateur :
    gain (suite au parrainage d'un achat/location) ou conversion
    (echange contre un cadeau ou de l'argent).
    """

    class TypeMouvement(models.TextChoices):
        GAGNE = "gagne", "Points gagnes"
        CONVERTI = "converti", "Points convertis"

    utilisateur = models.ForeignKey(
        Utilisateur, on_delete=models.CASCADE, related_name="mouvements_points"
    )
    type_mouvement = models.CharField(max_length=10, choices=TypeMouvement.choices)
    points = models.IntegerField(help_text="Positif pour un gain, negatif pour une conversion.")
    description = models.CharField(max_length=255, blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_creation"]

    def __str__(self):
        return f"{self.utilisateur} - {self.type_mouvement} - {self.points} pts"
