from django.db import models
from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver

from immobilier.models import Bien


class Offre(models.Model):
    """
    Publicite / offre promotionnelle creee par la societe Agharina.
    Peut etre generale (bannieres publicitaires) ou ciblee sur un bien
    precis (mise en avant, reduction).
    """

    class TypeOffre(models.TextChoices):
        PUBLICITE = "publicite", "Publicite"
        PROMOTION = "promotion", "Promotion"
        REDUCTION = "reduction", "Reduction"

    titre = models.CharField(max_length=200)
    titre_ar = models.CharField(
        max_length=200, blank=True, verbose_name="Titre (arabe)",
        help_text="Traduction arabe du titre, affichee quand le client consulte le site en arabe.",
    )
    description = models.TextField(blank=True)
    description_ar = models.TextField(
        blank=True, verbose_name="Description (arabe)",
        help_text="Traduction arabe de la description, affichee quand le client consulte le site en arabe.",
    )
    type_offre = models.CharField(max_length=15, choices=TypeOffre.choices)
    image = models.ImageField(upload_to="offres/", help_text="Image affichee sur le bandeau d'offres du site public.")

    bien = models.ForeignKey(
        Bien, on_delete=models.CASCADE, null=True, blank=True, related_name="offres",
        help_text="Optionnel : laisser vide pour une publicite generale.",
    )
    reduction_pourcentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    date_debut = models.DateField()
    date_fin = models.DateField()
    actif = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_creation"]

    def __str__(self):
        return self.titre


@receiver(post_delete, sender=Offre)
def supprimer_image_offre(sender, instance, **kwargs):
    """Supprime le fichier image physique quand l'offre est supprimee."""
    if instance.image:
        instance.image.delete(save=False)


@receiver(pre_save, sender=Offre)
def remplacer_image_offre(sender, instance, **kwargs):
    """Supprime l'ancienne image physique quand l'image d'une offre est remplacee."""
    if not instance.pk:
        return
    ancienne_image = sender.objects.filter(pk=instance.pk).values_list("image", flat=True).first()
    if ancienne_image and ancienne_image != instance.image.name:
        instance.image.storage.delete(ancienne_image)
