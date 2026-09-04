from django.contrib import admin

from .models import Quartier, Ville


class QuartierInline(admin.TabularInline):
    model = Quartier
    extra = 1


@admin.register(Ville)
class VilleAdmin(admin.ModelAdmin):
    list_display = ["nom", "region", "pays"]
    inlines = [QuartierInline]


@admin.register(Quartier)
class QuartierAdmin(admin.ModelAdmin):
    list_display = ["nom", "ville"]
    list_filter = ["ville"]
