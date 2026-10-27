from rest_framework import serializers

from .models import DeviceToken


class DeviceTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceToken
        fields = ["id", "token", "plateforme"]

    def create(self, validated_data):
        request = self.context["request"]
        utilisateur = request.user if request.user.is_authenticated else None
        instance, _ = DeviceToken.objects.update_or_create(
            token=validated_data["token"],
            defaults={
                "plateforme": validated_data.get("plateforme", DeviceToken.Plateforme.WEB),
                "utilisateur": utilisateur,
                "actif": True,
            },
        )
        return instance
