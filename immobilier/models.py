import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver

from localisation.models import Quartier, Ville


class Equipement(models.Model):
    """
    Caracteristique/equipement d'un bien : camera de securite, piscine,
    garage, chambre de gardien, balcon, climatisation, wifi, etc.
    Modele libre pour rester extensible sans toucher au code.
    """
    nom = models.CharField(max_length=100, unique=True)
    nom_ar = models.CharField(
        max_length=100, blank=True, verbose_name="Nom (arabe)",
        help_text="Traduction arabe du nom, affichee quand le client consulte le site en arabe.",
    )
    icone = models.CharField(
        max_length=50, blank=True,
        help_text="Nom d'icone cote frontend (ex: 'piscine', 'camera').",
    )

    class Meta:
        ordering = ["nom"]

    def __str__(self):
        return self.nom


class Bien(models.Model):
    """
    Modele central : represente n'importe quel bien immobilier
    (maison de ceremonie, duplexe, appartement, terrain, commercial),
    proposee a la vente ou a la location.

    Les caracteristiques propres a certains types (ceremonie, terrain)
    sont deportees dans des modeles de detail lies en OneToOne
    (voir DetailCeremonie / DetailTerrain) pour rester flexible.
    """

    class TypeBien(models.TextChoices):
        CEREMONIE = "ceremonie", "Maison de ceremonie"
        DUPLEXE = "duplexe", "Duplexe"
        APPARTEMENT = "appartement", "Appartement"
        TERRAIN = "terrain", "Terrain"
        COMMERCIAL = "commercial", "Commercial"

    class TypeTransaction(models.TextChoices):
        VENTE = "vente", "Vente"
        LOCATION = "location", "Location"

    class UnitePrix(models.TextChoices):
        JOUR = "jour", "Par jour"
        TROIS_JOURS = "3jours", "Par 3 jours"
        MOIS = "mois", "Par mois"
        FORFAIT = "forfait", "Prix fixe (vente)"

    # --- Identification ---
    reference = models.CharField(max_length=25, unique=True, editable=False, db_index=True)
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

    type_bien = models.CharField(max_length=20, choices=TypeBien.choices)
    type_transaction = models.CharField(max_length=20, choices=TypeTransaction.choices)

    # --- Caracteristiques generales ---
    meuble = models.BooleanField(default=False, verbose_name="Meuble")
    nb_chambres = models.PositiveSmallIntegerField(null=True, blank=True)
    nb_salles_bain = models.PositiveSmallIntegerField(null=True, blank=True)
    nb_etages = models.PositiveSmallIntegerField(null=True, blank=True)

    # --- Prix ---
    prix = models.DecimalField(max_digits=14, decimal_places=2)
    unite_prix = models.CharField(max_length=10, choices=UnitePrix.choices)

    # --- Localisation ---
    ville = models.ForeignKey(Ville, on_delete=models.PROTECT, related_name="biens")
    quartier = models.ForeignKey(
        Quartier, on_delete=models.SET_NULL, null=True, blank=True, related_name="biens"
    )
    adresse_complete = models.CharField(max_length=255, blank=True)
    adresse_complete_ar = models.CharField(
        max_length=255, blank=True, verbose_name="Adresse complete (arabe)",
        help_text="Traduction arabe de l'adresse, affichee quand le client consulte le site en arabe.",
    )
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)

    # --- Propriete / gestion ---
    nb_proprietaires = models.PositiveSmallIntegerField(default=1)
    gestionnaire = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="biens_geres",
        help_text="Utilisateur qui gere ce bien (proprietaire ou mandataire).",
    )

    # --- Equipements / caracteristiques additionnelles ---
    equipements = models.ManyToManyField(Equipement, blank=True, related_name="biens")

    actif = models.BooleanField(default=True, help_text="Bien visible/publie sur la plateforme.")
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date_creation"]
        indexes = [models.Index(fields=["type_bien", "type_transaction"])]

    def save(self, *args, **kwargs):
        if not self.reference:
            prefixe = self.type_bien[:3].upper() if self.type_bien else "BIE"
            self.reference = f"AGH-{prefixe}-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def clean(self):
        # Coherence type_bien / unite_prix / type_transaction
        if self.type_transaction == self.TypeTransaction.VENTE and self.unite_prix != self.UnitePrix.FORFAIT:
            raise ValidationError("Un bien a vendre doit avoir un prix fixe (unite_prix = forfait).")
        if self.type_transaction == self.TypeTransaction.LOCATION and self.unite_prix == self.UnitePrix.FORFAIT:
            raise ValidationError("Un bien a louer doit avoir une unite de prix jour/3jours/mois.")

    def __str__(self):
        return f"{self.reference} - {self.titre}"


class DetailCeremonie(models.Model):
    """Caracteristiques specifiques a une maison de ceremonie."""

    bien = models.OneToOneField(Bien, on_delete=models.CASCADE, related_name="detail_ceremonie")
    avec_service = models.BooleanField(
        default=False, help_text="Traiteur/personnel/decoration inclus ou non."
    )
    description_service = models.TextField(blank=True)
    description_service_ar = models.TextField(
        blank=True, verbose_name="Description du service (arabe)",
        help_text="Traduction arabe de la description du service, affichee quand le client consulte le site en arabe.",
    )
    capacite_personnes = models.PositiveIntegerField(null=True, blank=True)

    def __str__(self):
        return f"Ceremonie - {self.bien.reference}"


class DetailTerrain(models.Model):
    """Caracteristiques specifiques a un terrain."""

    bien = models.OneToOneField(Bien, on_delete=models.CASCADE, related_name="detail_terrain")
    superficie_m2 = models.DecimalField(max_digits=12, decimal_places=2)
    longueur_m = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    largeur_m = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    titre_foncier = models.CharField(max_length=100, blank=True)
    borne = models.BooleanField(default=False, help_text="Terrain borne ou non.")

    def __str__(self):
        return f"Terrain - {self.bien.reference}"


class MediaBien(models.Model):
    """Une ou plusieurs photos et/ou videos rattachees a un bien."""

    class TypeMedia(models.TextChoices):
        IMAGE = "image", "Image"
        VIDEO = "video", "Video"

    bien = models.ForeignKey(Bien, on_delete=models.CASCADE, related_name="medias")
    type_media = models.CharField(max_length=10, choices=TypeMedia.choices)
    fichier = models.FileField(upload_to="biens/%Y/%m/")
    legende = models.CharField(max_length=150, blank=True)
    ordre = models.PositiveSmallIntegerField(default=0)
    date_ajout = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["ordre", "date_ajout"]

    def __str__(self):
        return f"{self.type_media} - {self.bien.reference}"


class Indisponibilite(models.Model):
    """
    Calendrier de disponibilite d'un bien : par defaut un bien est
    considere disponible, le gestionnaire vient bloquer des periodes
    (un jour, plusieurs jours ou un/plusieurs mois complets).
    """

    bien = models.ForeignKey(Bien, on_delete=models.CASCADE, related_name="indisponibilites")
    date_debut = models.DateField()
    date_fin = models.DateField()
    motif = models.CharField(max_length=150, blank=True, help_text="Ex: deja loue, en travaux...")
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date_debut"]
        verbose_name = "Periode d'indisponibilite"
        verbose_name_plural = "Periodes d'indisponibilite"

    def clean(self):
        if self.date_fin < self.date_debut:
            raise ValidationError("La date de fin doit etre posterieure ou egale a la date de debut.")

    def __str__(self):
        return f"{self.bien.reference} indisponible du {self.date_debut} au {self.date_fin}"

    @staticmethod
    def est_disponible(bien: Bien, date_debut, date_fin) -> bool:
        """Verifie qu'aucune periode bloquee ne chevauche l'intervalle demande."""
        return not Indisponibilite.objects.filter(
            bien=bien, date_debut__lte=date_fin, date_fin__gte=date_debut
        ).exists()


@receiver(post_delete, sender=MediaBien)
def supprimer_fichier_mediabien(sender, instance, **kwargs):
    """Supprime le fichier physique (image/video) quand le MediaBien est supprime."""
    if instance.fichier:
        instance.fichier.delete(save=False)


@receiver(pre_save, sender=MediaBien)
def remplacer_fichier_mediabien(sender, instance, **kwargs):
    """Supprime l'ancien fichier physique quand le fichier d'un MediaBien est remplace."""
    if not instance.pk:
        return
    ancien_fichier = sender.objects.filter(pk=instance.pk).values_list("fichier", flat=True).first()
    if ancien_fichier and ancien_fichier != instance.fichier.name:
        instance.fichier.storage.delete(ancien_fichier)
