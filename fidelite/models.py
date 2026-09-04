from django.conf import settings
from django.db import models
from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver


class Cadeau(models.Model):
    """Cadeau ou montant en argent echangeable contre des points de fidelite."""

    nom = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    points_necessaires = models.PositiveIntegerField()
    valeur_argent = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Renseigner si le 'cadeau' est une conversion en argent.",
    )
    image = models.ImageField(upload_to="cadeaux/", null=True, blank=True)
    stock = models.PositiveIntegerField(default=0)
    actif = models.BooleanField(default=True)

    def __str__(self):
        return self.nom


@receiver(post_delete, sender=Cadeau)
def supprimer_image_cadeau(sender, instance, **kwargs):
    """Supprime le fichier image physique quand le cadeau est supprime."""
    if instance.image:
        instance.image.delete(save=False)


@receiver(pre_save, sender=Cadeau)
def remplacer_image_cadeau(sender, instance, **kwargs):
    """Supprime l'ancienne image physique quand l'image d'un cadeau est remplacee."""
    if not instance.pk:
        return
    ancienne_image = sender.objects.filter(pk=instance.pk).values_list("image", flat=True).first()
    if ancienne_image and ancienne_image != instance.image.name:
        instance.image.storage.delete(ancienne_image)


class EchangeCadeau(models.Model):
    class Statut(models.TextChoices):
        EN_ATTENTE = "en_attente", "En attente"
        VALIDE = "valide", "Valide"
        REFUSE = "refuse", "Refuse"

    utilisateur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="echanges_cadeaux")
    cadeau = models.ForeignKey(Cadeau, on_delete=models.PROTECT, related_name="echanges")
    points_utilises = models.PositiveIntegerField()
    statut = models.CharField(max_length=15, choices=Statut.choices, default=Statut.EN_ATTENTE)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_creation"]

    def __str__(self):
        return f"{self.utilisateur} -> {self.cadeau} ({self.statut})"
