from django.contrib import admin

from .models import (
    Bien,
    DetailCeremonie,
    DetailTerrain,
    Equipement,
    Indisponibilite,
    MediaBien,
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
    list_display = ["reference", "titre", "type_bien", "type_transaction", "prix", "unite_prix", "ville", "gestionnaire", "actif"]
    list_filter = ["type_bien", "type_transaction", "meuble", "actif", "ville"]
    search_fields = ["reference", "titre", "description"]
    readonly_fields = ["reference"]
    inlines = [DetailCeremonieInline, DetailTerrainInline, MediaBienInline, IndisponibiliteInline]


@admin.register(Equipement)
class EquipementAdmin(admin.ModelAdmin):
    list_display = ["nom", "icone"]
