from django.db.models.signals import post_save
from django.dispatch import receiver

from comptes.models import TransactionPoints
from immobilier.models import Bien, Indisponibilite

from .models import Transaction

POINTS_PAR_PARRAINAGE = 50  # points attribues au parrain a chaque transaction finalisee de son filleul


@receiver(post_save, sender=Transaction)
def attribuer_points_et_bloquer_calendrier(sender, instance: Transaction, **kwargs):
    """
    Quand une transaction passe au statut CONFIRMEE :
    1) si le client a ete parraine, son parrain gagne automatiquement
       des points de fidelite (une seule fois par transaction).
    2) si c'est une location, la periode reservee est automatiquement
       bloquee dans le calendrier de disponibilite du bien.
    """
    if instance.statut != Transaction.Statut.CONFIRMEE:
        return

    if not instance.points_attribues:
        parrain = instance.client.invite_par
        if parrain is not None:
            parrain.points_fidelite += POINTS_PAR_PARRAINAGE
            parrain.save(update_fields=["points_fidelite"])
            TransactionPoints.objects.create(
                utilisateur=parrain,
                type_mouvement=TransactionPoints.TypeMouvement.GAGNE,
                points=POINTS_PAR_PARRAINAGE,
                description=(
                    f"Filleul {instance.client} a finalise la transaction {instance.reference}"
                ),
            )
        Transaction.objects.filter(pk=instance.pk).update(points_attribues=True)

    if instance.type_transaction == Bien.TypeTransaction.LOCATION and instance.date_debut and instance.date_fin:
        Indisponibilite.objects.get_or_create(
            bien=instance.bien,
            date_debut=instance.date_debut,
            date_fin=instance.date_fin,
            defaults={"motif": f"Loue via transaction {instance.reference}"},
        )
