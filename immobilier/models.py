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
        ESPACE = "espace", "Espace / equipement public"

    class TypeTransaction(models.TextChoices):
        VENTE = "vente", "Vente"
        LOCATION = "location", "Location"

    class UnitePrix(models.TextChoices):
        JOUR = "jour", "Par jour"
        TROIS_JOURS = "3jours", "Par 3 jours"
        MOIS = "mois", "Par mois"
        FORFAIT = "forfait", "Prix fixe (vente)"

    class StatutDisponibilite(models.TextChoices):
        DISPONIBLE = "disponible", "Disponible"
        ATTRIBUE = "attribue", "Attribue"
        PAS_ENCORE_DISPONIBLE = "pas_encore_disponible", "Pas encore disponible"

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
    # Nullable/blank uniquement pour type_bien=ESPACE (type_transaction=AUCUNE) :
    # un parc/equipement public ne se vend ni ne se loue. Tous les autres
    # types continuent de les exiger (voir clean()/BienDetailSerializer.validate()).
    prix = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    unite_prix = models.CharField(max_length=10, choices=UnitePrix.choices, blank=True)
    statut_disponibilite = models.CharField(
        max_length=25, choices=StatutDisponibilite.choices,
        default=StatutDisponibilite.DISPONIBLE, blank=True,
        help_text="Pour les biens en allocation mensuelle uniquement : statut gere manuellement "
        "par le gestionnaire (pas de calendrier jour par jour pour ce type d'allocation).",
    )

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
    gestionnaires = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="biens_geres",
        blank=True,
        help_text="Utilisateurs qui gerent ce bien (proprietaires ou mandataires). "
        "Un admin peut en affecter/retirer plusieurs.",
    )

    # --- Equipements / caracteristiques additionnelles ---
    equipements = models.ManyToManyField(Equipement, blank=True, related_name="biens")

    actif = models.BooleanField(default=True, help_text="Bien visible/publie sur la plateforme.")
    vendu = models.BooleanField(
        default=False,
        help_text="Bien vendu : affiche comme 'Deja vendu' et ne peut plus etre achete. "
        "Mis a jour automatiquement quand une transaction de vente est confirmee.",
    )
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
        # Coherence type_bien / unite_prix / type_transaction. Un espace
        # (parc, equipement public...) suit la meme regle qu'un terrain :
        # vendu a prix fixe (type_transaction=vente, unite_prix=forfait).
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


class PlanQuartier(models.Model):
    """
    Plan de lotissement (image) rattache a un quartier, positionne sur la
    carte (centre + dimensions reelles + rotation) pour servir de fond
    visuel et de reference aux parcelles (DetailTerrain.polygone).
    """

    quartier = models.ForeignKey(Quartier, on_delete=models.CASCADE, related_name="plans")
    nom = models.CharField(max_length=150, blank=True, help_text="Ex: Plan Nasr - Teyarett")
    image = models.FileField(upload_to="plans/%Y/%m/")
    centre_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    centre_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    largeur_m = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Largeur reelle de l'image sur le terrain, en metres.",
    )
    hauteur_m = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Hauteur reelle de l'image sur le terrain, en metres.",
    )
    rotation_deg = models.DecimalField(
        max_digits=6, decimal_places=2, default=0,
        help_text="Rotation horaire de l'image depuis le nord, en degres.",
    )
    echelle_m_par_pixel = models.DecimalField(
        max_digits=10, decimal_places=5, null=True, blank=True,
        help_text="Metres reels par pixel de l'image rendue, calcule automatiquement. "
        "Sert a heriter la position/echelle pour les plans suivants du meme quartier.",
    )
    actif = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date_creation"]
        verbose_name = "Plan de quartier"
        verbose_name_plural = "Plans de quartier"

    def __str__(self):
        return self.nom or f"Plan {self.quartier}"


class DetailTerrain(models.Model):
    """Caracteristiques specifiques a un terrain."""

    bien = models.OneToOneField(Bien, on_delete=models.CASCADE, related_name="detail_terrain")
    superficie_m2 = models.DecimalField(max_digits=12, decimal_places=2)
    longueur_m = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    largeur_m = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    # Dimensions complementaires pour les parcelles non rectangulaires
    # (triangle, trapeze, quadrilatere irregulier...) : longueur/largeur ne
    # suffisent pas a les decrire. Champs libres, l'admin ne remplit que
    # ceux pertinents pour la forme reelle du lot (ex: base+hauteur pour un
    # triangle, les deux bases+hauteur pour un trapeze).
    base_m = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    hauteur_m = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    hypotenuse_m = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    diagonale_m = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    titre_foncier = models.CharField(max_length=100, blank=True)
    borne = models.BooleanField(default=False, help_text="Terrain borne ou non.")
    moughataa = models.CharField(max_length=100, blank=True, help_text="Moughataa du terrain.")
    plan = models.ForeignKey(
        PlanQuartier, on_delete=models.SET_NULL, null=True, blank=True, related_name="lots"
    )
    numero_lot = models.CharField(
        max_length=30, blank=True, help_text="Numero du lot tel qu'affiche sur le plan."
    )
    polygone = models.JSONField(
        null=True, blank=True,
        help_text="Liste de points [{lat, lng}, ...] delimitant la parcelle sur la carte.",
    )

    def __str__(self):
        return f"Terrain - {self.bien.reference}"


class LotDetecte(models.Model):
    """
    Lot (parcelle) detecte automatiquement depuis le PDF d'un PlanQuartier,
    en attente d'etre rattache a un Bien/DetailTerrain par l'admin.

    polygone_local est en coordonnees fractionnaires (0..1) RELATIVES A
    L'IMAGE du plan (pas en lat/lng) : tant que le lot n'est pas affecte,
    sa position doit rester recalculee en direct a partir de la position
    courante du PlanQuartier (qui peut encore bouger), pour ne pas deriver
    si l'admin repositionne/redimensionne/tourne l'overlay apres coup.
    """

    class Statut(models.TextChoices):
        EN_ATTENTE = "en_attente", "En attente"
        AFFECTE = "affecte", "Affecte"
        IGNORE = "ignore", "Ignore"

    plan = models.ForeignKey(PlanQuartier, on_delete=models.CASCADE, related_name="lots_detectes")
    numero_lot = models.CharField(max_length=30, blank=True)
    polygone_local = models.JSONField(
        help_text="Liste de points [{x, y}, ...] en fractions 0..1 de l'image du plan."
    )
    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.EN_ATTENTE)
    bien = models.OneToOneField(
        Bien, on_delete=models.SET_NULL, null=True, blank=True, related_name="lot_detecte"
    )
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["numero_lot"]
        verbose_name = "Lot detecte"
        verbose_name_plural = "Lots detectes"
        constraints = [
            models.UniqueConstraint(
                fields=["plan", "numero_lot"],
                condition=~models.Q(numero_lot=""),
                name="unique_numero_lot_par_plan_lotdetecte",
            )
        ]

    def __str__(self):
        return f"Lot {self.numero_lot or '?'} - {self.plan}"


class ZonePlan(models.Model):
    """
    Zone non-vendable d'un plan (espace vert, equipement public,
    mosquee...), extraite automatiquement du PDF (voir
    pdf_extraction.extraire_zones) en meme temps que les lots, pour que le
    plan affiche sur la carte corresponde fidelement au document source.

    nom/description/superficie_m2/longueur_m/largeur_m/moughataa/adresse
    sont ensuite modifiables par l'admin (cliquer la zone dans l'editeur de
    plan) : contrairement a LotDetecte, une fois qu'au moins une zone
    existe pour un plan, un remplacement d'image ne les recree JAMAIS
    automatiquement, pour ne pas ecraser ces saisies (voir
    PlanQuartierSerializer.update).

    bien (optionnel) : une fois les informations saisies, l'admin peut
    "publier" la zone comme Bien(type_bien=ESPACE) pour qu'elle obtienne
    sa propre fiche publique cote client (affichee comme un espace/parc,
    jamais comme un terrain a vendre - voir Bien.TypeBien.ESPACE).
    """

    class TypeZone(models.TextChoices):
        ESPACE_VERT = "espace_vert", "Espace vert"
        ESPACE_PUBLIC = "espace_public", "Espace public"
        EQUIPEMENT_PUBLIC = "equipement_public", "Equipement public"
        MOSQUEE = "mosquee", "Mosquee"
        AUTRE = "autre", "Autre"

    plan = models.ForeignKey(PlanQuartier, on_delete=models.CASCADE, related_name="zones")
    nom = models.CharField(max_length=150, help_text="Modifiable si l'auto-detection s'est trompee.")
    type_zone = models.CharField(max_length=20, choices=TypeZone.choices, default=TypeZone.AUTRE)
    description = models.TextField(blank=True)
    moughataa = models.CharField(max_length=100, blank=True)
    adresse = models.CharField(max_length=255, blank=True)
    superficie_m2 = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    longueur_m = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    largeur_m = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    # Memes dimensions complementaires que DetailTerrain, pour les zones
    # non rectangulaires (ex: espace vert en forme d'eventail).
    base_m = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    hauteur_m = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    hypotenuse_m = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    diagonale_m = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    polygone_local = models.JSONField(
        help_text="Liste de points [{x, y}, ...] en fractions 0..1 de l'image du plan."
    )
    bien = models.OneToOneField(
        Bien, on_delete=models.SET_NULL, null=True, blank=True, related_name="zone_plan",
        help_text="Fiche publique (type_bien=espace) une fois la zone publiee cote client.",
    )
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nom"]
        verbose_name = "Zone du plan"
        verbose_name_plural = "Zones du plan"

    def __str__(self):
        return f"{self.nom} - {self.plan}"


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
        if self.bien_id and self.bien.unite_prix == Bien.UnitePrix.MOIS:
            raise ValidationError(
                "Les biens en allocation mensuelle n'ont pas de calendrier de disponibilite, "
                "utilisez le statut du bien."
            )

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


@receiver(post_delete, sender=PlanQuartier)
def supprimer_image_plan_quartier(sender, instance, **kwargs):
    """Supprime le fichier physique du plan quand le PlanQuartier est supprime."""
    if instance.image:
        instance.image.delete(save=False)


@receiver(pre_save, sender=PlanQuartier)
def remplacer_image_plan_quartier(sender, instance, **kwargs):
    """Supprime l'ancienne image quand le fichier d'un PlanQuartier est remplace."""
    if not instance.pk:
        return
    ancien_fichier = sender.objects.filter(pk=instance.pk).values_list("image", flat=True).first()
    if ancien_fichier and ancien_fichier != instance.image.name:
        instance.image.storage.delete(ancien_fichier)
