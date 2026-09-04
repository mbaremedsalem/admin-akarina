from rest_framework import permissions


class EstGestionnaireOuLectureSeule(permissions.BasePermission):
    """
    Lecture libre pour tout le monde. Ecriture reservee au gestionnaire
    du bien concerne (ou a un administrateur).
    """

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        bien = obj if hasattr(obj, "gestionnaire") else obj.bien
        return request.user.is_staff or bien.gestionnaire_id == request.user.id
