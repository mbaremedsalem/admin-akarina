from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import TransactionPoints, Utilisateur


@admin.register(Utilisateur)
class UtilisateurAdmin(UserAdmin):
    list_display = ["username", "email", "telephone", "est_gestionnaire", "code_invitation", "points_fidelite", "invite_par"]
    fieldsets = UserAdmin.fieldsets + (
        ("Agharina", {"fields": ("telephone", "est_gestionnaire", "invite_par", "points_fidelite")}),
    )


@admin.register(TransactionPoints)
class TransactionPointsAdmin(admin.ModelAdmin):
    list_display = ["utilisateur", "type_mouvement", "points", "date_creation"]
    list_filter = ["type_mouvement"]
