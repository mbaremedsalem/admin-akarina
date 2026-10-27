from django.db.models.signals import post_save
from django.dispatch import receiver

from immobilier.models import Bien
from offres.models import Offre

from .services import envoyer_notification


@receiver(post_save, sender=Bien)
def notifier_nouveau_bien(sender, instance, created, **kwargs):
    if not created:
        return
    envoyer_notification(
        titre="Nouveau bien disponible",
        corps=instance.titre,
        data={"type": "bien", "bien_reference": instance.reference},
    )


@receiver(post_save, sender=Offre)
def notifier_nouvelle_offre(sender, instance, created, **kwargs):
    if not created:
        return
    envoyer_notification(
        titre="Nouvelle offre Agharina",
        corps=instance.titre,
        data={"type": "offre", "offre_id": str(instance.id)},
    )
