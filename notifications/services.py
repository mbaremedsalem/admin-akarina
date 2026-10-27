"""Envoi de notifications push (Firebase Cloud Messaging) vers les appareils
web/Android/iOS enregistres. Toute erreur est avalee et journalisee : une
notification qui echoue ne doit jamais faire echouer la creation du bien/de
l'offre qui l'a declenchee.
"""
import logging

import firebase_admin
from django.conf import settings
from firebase_admin import credentials, messaging

logger = logging.getLogger(__name__)

_firebase_app = None


def _get_firebase_app():
    global _firebase_app
    if _firebase_app is None:
        cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
        _firebase_app = firebase_admin.initialize_app(cred)
    return _firebase_app


def envoyer_notification(titre, corps, data=None, image=None):
    """Envoie une notification push a tous les appareils actifs (mobile + web)."""
    from .models import DeviceToken

    tokens = list(DeviceToken.objects.filter(actif=True).values_list("token", flat=True))
    if not tokens:
        return

    try:
        _get_firebase_app()
        message = messaging.MulticastMessage(
            notification=messaging.Notification(title=titre, body=corps, image=image),
            data={str(k): str(v) for k, v in (data or {}).items()},
            tokens=tokens,
        )
        response = messaging.send_each_for_multicast(message)
    except Exception:
        logger.exception("Echec de l'envoi de la notification push '%s'", titre)
        return

    if response.failure_count:
        tokens_invalides = [
            tokens[i]
            for i, res in enumerate(response.responses)
            if not res.success
            and isinstance(res.exception, messaging.UnregisteredError)
        ]
        if tokens_invalides:
            DeviceToken.objects.filter(token__in=tokens_invalides).update(actif=False)
