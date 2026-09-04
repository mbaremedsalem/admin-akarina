import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from immobilier.models import Bien


class Transaction(models.Model):
    """
    Vente ou location finalisee d'un bien par un client.
    C'est cet objet qui declenche l'attribution des points de fidelite
    au parrain du client (voir signals.py), une seule fois, quand la
    transaction passe au statut CONFIRMEE.
    """

    class Statut(models.TextChoices):
        EN_ATTENTE = "en_attente", "En attente"
        CONFIRMEE = "confirmee", "Confirmee"
        ANNULEE = "annulee", "Annulee"
        TERMINEE = "terminee", "Terminee"

    reference = models.CharField(max_length=25, unique=True, editable=False)
    bien = models.ForeignKey(Bien, on_delete=models.PROTECT, related_name="transactions")
    client = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="transactions_client")
    type_transaction = models.CharField(max_length=20, choices=Bien.TypeTransaction.choices)

    # Pertinent seulement pour une location.
    date_debut = models.DateField(null=True, blank=True)
    date_fin = models.DateField(null=True, blank=True)

    montant_total = models.DecimalField(max_digits=14, decimal_places=2)
    statut = models.CharField(max_length=15, choices=Statut.choices, default=Statut.EN_ATTENTE)

    points_attribues = models.BooleanField(
        default=False, editable=False,
        help_text="Empeche un double credit de points au parrain.",
    )

    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date_creation"]

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = f"TX-{uuid.uuid4().hex[:10].upper()}"
        super().save(*args, **kwargs)

    def clean(self):
        if self.type_transaction == Bien.TypeTransaction.LOCATION and not (self.date_debut and self.date_fin):
            raise ValidationError("Une location necessite une date de debut et une date de fin.")

    def __str__(self):
        return f"{self.reference} - {self.bien.reference} - {self.statut}"
