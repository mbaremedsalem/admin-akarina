from django.conf import settings
from django.db import models


class DeviceToken(models.Model):
    """Jeton FCM d'un appareil (web, Android ou iOS) qui doit recevoir les
    notifications push (nouveau bien, nouvelle offre...)."""

    class Plateforme(models.TextChoices):
        WEB = "web", "Web"
        ANDROID = "android", "Android"
        IOS = "ios", "iOS"

    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name="device_tokens",
        help_text="Optionnel : un visiteur non connecte peut aussi recevoir des notifications.",
    )
    token = models.CharField(max_length=255, unique=True)
    plateforme = models.CharField(max_length=10, choices=Plateforme.choices, default=Plateforme.WEB)
    actif = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_creation"]

    def __str__(self):
        return f"{self.plateforme} - {self.token[:16]}..."
