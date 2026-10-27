from django.contrib import admin

from .models import (
    Bien,
    DetailCeremonie,
    DetailTerrain,
    Equipement,
    Indisponibilite,
    LotDetecte,
    MediaBien,
    PlanQuartier,
    ZonePlan,
)


class MediaBienInline(admin.TabularInline):
    model = MediaBien
    extra = 1


class IndisponibiliteInline(admin.TabularInline):
    model = Indisponibilite
    extra = 0


class DetailCeremonieInline(admin.StackedInline):
    model = DetailCeremonie
    extra = 0


class DetailTerrainInline(admin.StackedInline):
    model = DetailTerrain
    extra = 0


@admin.register(Bien)
class BienAdmin(admin.ModelAdmin):
    list_display = ["reference", "titre", "type_bien", "type_transaction", "prix", "unite_prix", "statut_disponibilite", "ville", "actif", "vendu"]
    list_filter = ["type_bien", "type_transaction", "meuble", "statut_disponibilite", "actif", "vendu", "ville"]
    search_fields = ["reference", "titre", "description"]
    readonly_fields = ["reference"]
    filter_horizontal = ["gestionnaires", "equipements"]
    inlines = [DetailCeremonieInline, DetailTerrainInline, MediaBienInline, IndisponibiliteInline]


@admin.register(Equipement)
class EquipementAdmin(admin.ModelAdmin):
    list_display = ["nom", "icone"]


@admin.register(PlanQuartier)
class PlanQuartierAdmin(admin.ModelAdmin):
    list_display = ["nom", "quartier", "centre_latitude", "centre_longitude", "largeur_m", "hauteur_m", "rotation_deg", "actif"]
    list_filter = ["quartier__ville", "quartier", "actif"]
    search_fields = ["nom", "quartier__nom"]


@admin.register(LotDetecte)
class LotDetecteAdmin(admin.ModelAdmin):
    list_display = ["numero_lot", "plan", "statut", "bien"]
    list_filter = ["statut", "plan__quartier"]
    search_fields = ["numero_lot", "plan__nom"]


@admin.register(ZonePlan)
class ZonePlanAdmin(admin.ModelAdmin):
    list_display = ["nom", "type_zone", "plan"]
    list_filter = ["type_zone", "plan__quartier"]
    search_fields = ["nom", "plan__nom"]
