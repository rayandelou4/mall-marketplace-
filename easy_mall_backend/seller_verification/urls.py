"""
URLs pour le système de certification des vendeurs.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views

# Router pour les ViewSets
router = DefaultRouter()
router.register(r'requests', views.VerificationRequestViewSet, basename='verification-request')
router.register(r'admin/verification-requests', views.AdminVerificationRequestViewSet, basename='admin-verification-request')
router.register(r'admin/certifications', views.AdminCertificationViewSet, basename='admin-certification')

urlpatterns = [
    # Statut et informations générales
    path('status/', views.UserVerificationStatusView.as_view(), name='user-verification-status'),
    path('levels/', views.VerificationLevelsView.as_view(), name='verification-levels'),
    
    # Documents
    path('documents/<uuid:document_id>/download/', 
         views.VerificationDocumentDownloadView.as_view(), 
         name='verification-document-download'),
    
    # Tableau de bord admin
    path('admin/dashboard/', 
         views.AdminVerificationDashboardView.as_view(), 
         name='admin-verification-dashboard'),
    
    # Traitement automatique (interne)
    path('internal/process-automatic-certifications/', 
         views.ProcessAutomaticCertificationsView.as_view(), 
         name='process-automatic-certifications'),
    
    # Inclure les routes du router
    path('', include(router.urls)),
]

# URLs globales pour inclure dans le projet principal
seller_verification_urlpatterns = [
    path('api/seller-verification/', include(urlpatterns)),
]