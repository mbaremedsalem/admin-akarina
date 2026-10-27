from django.urls import path

from .views import DeviceTokenViewSet

urlpatterns = [
    path("device-tokens/", DeviceTokenViewSet.as_view({"post": "create"}), name="device-token-create"),
    path("device-tokens/unregister/", DeviceTokenViewSet.as_view({"post": "unregister"}), name="device-token-unregister"),
]
