from django.contrib import admin

from .models import DeviceToken


@admin.register(DeviceToken)
class DeviceTokenAdmin(admin.ModelAdmin):
    list_display = ["plateforme", "token", "utilisateur", "actif", "date_creation"]
    list_filter = ["plateforme", "actif"]
    search_fields = ["token", "utilisateur__username"]
