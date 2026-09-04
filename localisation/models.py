from django.db import models


class Ville(models.Model):
    nom = models.CharField(max_length=100, unique=True)
    nom_ar = models.CharField(
        max_length=100, blank=True, verbose_name="Nom (arabe)",
        help_text="Traduction arabe du nom, affichee quand le client consulte le site en arabe.",
    )
    region = models.CharField(max_length=100, blank=True)
    pays = models.CharField(max_length=100, default="Mauritanie")

    class Meta:
        ordering = ["nom"]
        verbose_name = "Ville"
        verbose_name_plural = "Villes"

    def __str__(self):
        return self.nom


class Quartier(models.Model):
    ville = models.ForeignKey(Ville, on_delete=models.CASCADE, related_name="quartiers")
    nom = models.CharField(max_length=100)
    nom_ar = models.CharField(
        max_length=100, blank=True, verbose_name="Nom (arabe)",
        help_text="Traduction arabe du nom, affichee quand le client consulte le site en arabe.",
    )

    class Meta:
        ordering = ["nom"]
        unique_together = ("ville", "nom")
        verbose_name = "Quartier"
        verbose_name_plural = "Quartiers"

    def __str__(self):
        return f"{self.nom} ({self.ville.nom})"
