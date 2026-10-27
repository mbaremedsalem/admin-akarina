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
        bien = obj if hasattr(obj, "gestionnaires") else obj.bien
        return request.user.is_staff or bien.gestionnaires.filter(id=request.user.id).exists()


class EstStaffOuLectureSeule(permissions.BasePermission):
    """
    Lecture libre pour tout le monde. Ecriture reservee au staff
    (cartographie des plans de quartier, tache back-office distincte
    de la gestion habituelle d'un bien par son/ses gestionnaire(s)).
    """

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)
