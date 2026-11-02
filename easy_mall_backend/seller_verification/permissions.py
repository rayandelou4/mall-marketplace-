"""
Permissions personnalisées pour le système de certification des vendeurs.
"""

from rest_framework import permissions


class IsSeller(permissions.BasePermission):
    """
    Permission pour vérifier que l'utilisateur est authentifié.
    Tous les utilisateurs authentifiés peuvent être vendeurs.
    """
    
    def has_permission(self, request, view):
        return request.user.is_authenticated


class IsAdminOrStaff(permissions.BasePermission):
    """Permission pour les administrateurs et staff."""
    
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_staff


class IsVerificationAdmin(permissions.BasePermission):
    """
    Permission pour les administrateurs autorisés à gérer les vérifications.
    
    Vérifie que l'utilisateur est staff ET a les permissions spécifiques.
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated or not request.user.is_staff:
            return False
        
        # Vérifier les permissions spécifiques
        required_perms = {
            'GET': ['seller_verification.view_verificationrequest'],
            'POST': ['seller_verification.change_verificationrequest'],
            'PUT': ['seller_verification.change_verificationrequest'],
            'PATCH': ['seller_verification.change_verificationrequest'],
            'DELETE': ['seller_verification.delete_verificationrequest'],
        }
        
        method_perms = required_perms.get(request.method, [])
        if not method_perms:
            return True  # Méthode non définie, autoriser par défaut pour staff
        
        return all(request.user.has_perm(perm) for perm in method_perms)


class CanViewDocuments(permissions.BasePermission):
    """
    Permission pour voir les documents de vérification.
    
    - L'utilisateur peut voir ses propres documents
    - Les admins peuvent voir tous les documents
    """
    
    def has_permission(self, request, view):
        return request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        # L'utilisateur peut voir ses propres documents
        if obj.request.user == request.user:
            return True
        
        # Les admins peuvent voir tous les documents
        if request.user.is_staff and request.user.has_perm('seller_verification.view_verificationdocument'):
            return True
        
        return False


class CanManageCertification(permissions.BasePermission):
    """
    Permission pour gérer les certifications.
    
    - L'utilisateur peut voir ses propres certifications
    - Les admins peuvent gérer toutes les certifications
    """
    
    def has_permission(self, request, view):
        return request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        # L'utilisateur peut voir ses propres certifications
        if obj.user == request.user:
            return True
        
        # Les admins peuvent gérer toutes les certifications
        if request.user.is_staff and request.user.has_perm('seller_verification.change_sellercertification'):
            return True
        
        return False


class CanSubmitVerificationRequest(permissions.BasePermission):
    """
    Permission pour soumettre une demande de vérification.
    
    Vérifie que l'utilisateur n'a pas de demande active du même type.
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # Vérifier les demandes actives
        from .models import VerificationRequest, VerificationRequestStatus
        
        if request.method == 'POST':
            # Pour la création, vérifier s'il y a déjà une demande active du même type
            verification_type = request.data.get('verification_type')
            
            if verification_type:
                active_requests = VerificationRequest.objects.filter(
                    user=request.user,
                    verification_type=verification_type,
                    status__in=[
                        VerificationRequestStatus.PENDING,
                        VerificationRequestStatus.UNDER_REVIEW,
                        VerificationRequestStatus.NEEDS_MORE_INFORMATION
                    ]
                ).exists()
                
                if active_requests:
                    return False
        
        return True


class CanUploadDocuments(permissions.BasePermission):
    """
    Permission pour uploader des documents.
    
    Vérifie que l'utilisateur peut uploader des documents pour cette demande.
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # Récupérer la demande depuis le contexte
        verification_request = view.kwargs.get('verification_request')
        if not verification_request:
            return True  # La validation se fera dans la vue
        
        # Vérifier que la demande appartient à l'utilisateur
        if verification_request.user != request.user:
            return False
        
        # Vérifier que la demande est en brouillon
        if verification_request.status != 'draft':
            return False
        
        return True


class IsSystemOrAdmin(permissions.BasePermission):
    """
    Permission pour les actions système ou admin.
    
    Utilisé pour les tâches automatiques et les endpoints internes.
    """
    
    def has_permission(self, request, view):
        # Les tâches système peuvent être authentifiées avec un token spécial
        system_token = request.META.get('HTTP_X_SYSTEM_TOKEN')
        if system_token and system_token == 'SYSTEM_TOKEN_SECRET':
            return True
        
        # Les admins peuvent aussi accéder
        return request.user.is_authenticated and request.user.is_staff