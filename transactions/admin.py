from django.contrib import admin

from .models import Transaction


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ["reference", "bien", "client", "type_transaction", "statut", "montant_total", "date_creation"]
    list_filter = ["statut", "type_transaction"]
    search_fields = ["reference", "bien__reference"]
