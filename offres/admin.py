from django.contrib import admin

from .models import Offre


@admin.register(Offre)
class OffreAdmin(admin.ModelAdmin):
    list_display = ["titre", "type_offre", "bien", "date_debut", "date_fin", "actif"]
    list_filter = ["type_offre", "actif"]
