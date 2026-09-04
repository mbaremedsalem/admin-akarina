from django.urls import path

from .views import TransactionViewSet

LIST_CREATE = {"get": "list", "post": "create"}
DETAIL = {"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}

urlpatterns = [
    path("transactions/", TransactionViewSet.as_view(LIST_CREATE), name="transaction-list"),
    path("transactions/<int:pk>/", TransactionViewSet.as_view(DETAIL), name="transaction-detail"),
]
