from django.contrib import admin

from .models import Cadeau, EchangeCadeau


@admin.register(Cadeau)
class CadeauAdmin(admin.ModelAdmin):
    list_display = ["nom", "points_necessaires", "valeur_argent", "stock", "actif"]


@admin.register(EchangeCadeau)
class EchangeCadeauAdmin(admin.ModelAdmin):
    list_display = ["reference", "utilisateur", "cadeau", "points_utilises", "statut", "date_creation"]
    list_filter = ["statut"]
    search_fields = ["reference", "utilisateur__username", "cadeau__nom"]
