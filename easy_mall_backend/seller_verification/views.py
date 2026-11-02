"""
Views pour le système de certification des vendeurs.

Fournit les endpoints API pour :
- Les vendeurs : consulter statut, soumettre demandes, uploader documents
- Les administrateurs : examiner demandes, prendre décisions, gérer certifications
"""

import os
from typing import Dict, Any
from django.conf import settings
from django.db import transaction
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets, permissions, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    SellerCertification,
    VerificationRequest,
    VerificationDocument,
    VerificationCriteria,
    RiskSignal,
    VerificationLevel,
    VerificationRequestStatus,
    VerificationType,
    CertificationAuditLog,
)
from .serializers import (
    VerificationRequestSerializer,
    VerificationRequestSubmitSerializer,
    VerificationDocumentUploadSerializer,
    SellerCertificationSerializer,
    VerificationCriteriaSerializer,
    RiskSignalSerializer,
    UserVerificationStatusSerializer,
)
from .services import (
    VerificationService,
    RiskDetectionService,
    DocumentValidationService,
    CertificationCalculator,
)
from accounts.models import User


class IsSeller(permissions.BasePermission):
    """Permission personnalisée pour vérifier si l'utilisateur est un vendeur."""
    
    def has_permission(self, request, view):
        return request.user.is_authenticated


class IsAdminOrStaff(permissions.BasePermission):
    """Permission pour les administrateurs et staff."""
    
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_staff


class IsVerificationAdmin(permissions.BasePermission):
    """Permission pour les administrateurs autorisés à gérer les vérifications."""
    
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and 
            request.user.is_staff and
            # Pourrait être étendu avec des permissions spécifiques
            request.user.has_perm('seller_verification.view_verificationrequest')
        )


class UserVerificationStatusView(APIView):
    """
    Vue pour obtenir le statut de vérification de l'utilisateur connecté.
    
    GET /api/seller-verification/status/
    """
    
    permission_classes = [IsSeller]
    
    def get(self, request, format=None):
        """Retourne le statut de vérification complet de l'utilisateur."""
        serializer = UserVerificationStatusSerializer(request.user)
        return Response(serializer.data)


class VerificationLevelsView(APIView):
    """
    Vue pour obtenir les niveaux de certification disponibles.
    
    GET /api/seller-verification/levels/
    """
    
    permission_classes = [IsSeller]
    
    def get(self, request, format=None):
        """Retourne la liste des niveaux avec critères et éligibilité."""
        service = VerificationService()
        
        # Récupérer tous les critères
        criteria_queryset = VerificationCriteria.objects.filter(is_active=True)
        criteria_data = VerificationCriteriaSerializer(criteria_queryset, many=True).data
        
        # Calculer l'éligibilité pour chaque niveau
        eligible_levels = service.get_eligible_levels(request.user)
        
        # Formater la réponse
        response_data = {
            "levels": criteria_data,
            "eligible_levels": eligible_levels,
            "current_certifications": SellerCertificationSerializer(
                request.user.certifications.filter(revoked_at__isnull=True),
                many=True
            ).data,
        }
        
        return Response(response_data)


class VerificationRequestViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet
):
    """
    ViewSet pour gérer les demandes de vérification.
    
    Endpoints :
    - GET /api/seller-verification/requests/ : Liste des demandes de l'utilisateur
    - POST /api/seller-verification/requests/ : Créer une nouvelle demande
    - GET /api/seller-verification/requests/{id}/ : Détails d'une demande
    - PUT /api/seller-verification/requests/{id}/ : Modifier une demande (brouillon)
    """
    
    permission_classes = [IsSeller]
    serializer_class = VerificationRequestSerializer
    
    def get_queryset(self):
        """Retourne uniquement les demandes de l'utilisateur connecté."""
        return VerificationRequest.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        """Crée une demande avec l'utilisateur connecté comme propriétaire."""
        serializer.save(user=self.request.user)
        
        # Log d'audit
        CertificationAuditLog.objects.create(
            user=self.request.user,
            request=serializer.instance,
            action=CertificationAuditLog.ActionType.REQUEST_CREATED,
            actor=self.request.user,
            details={
                "verification_type": serializer.instance.verification_type,
                "target_level": serializer.instance.target_level,
            }
        )
    
    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """
        Soumet une demande de vérification.
        
        POST /api/seller-verification/requests/{id}/submit/
        """
        verification_request = self.get_object()
        
        # Vérifier que la demande appartient à l'utilisateur
        if verification_request.user != request.user:
            return Response(
                {"detail": "Vous n'avez pas la permission de soumettre cette demande."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = VerificationRequestSubmitSerializer(
            data={},
            context={
                'request': request,
                'verification_request': verification_request
            }
        )
        
        if serializer.is_valid():
            verification_request = serializer.save()
            
            # Détecter les signaux de risque
            risk_service = RiskDetectionService()
            risk_signals = risk_service.detect_risk_signals(request.user)
            
            # Sauvegarder les signaux détectés
            for signal in risk_signals:
                signal.save()
            
            return Response(
                VerificationRequestSerializer(verification_request).data,
                status=status.HTTP_200_OK
            )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """
        Annule une demande de vérification.
        
        POST /api/seller-verification/requests/{id}/cancel/
        """
        verification_request = self.get_object()
        
        # Vérifier que la demande appartient à l'utilisateur
        if verification_request.user != request.user:
            return Response(
                {"detail": "Vous n'avez pas la permission d'annuler cette demande."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            verification_request.cancel()
            
            # Log d'audit
            CertificationAuditLog.objects.create(
                user=request.user,
                request=verification_request,
                action=CertificationAuditLog.ActionType.REQUEST_CANCELLED,
                actor=request.user,
                details={"status": verification_request.status}
            )
            
            return Response(
                VerificationRequestSerializer(verification_request).data,
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['get', 'post'])
    def documents(self, request, pk=None):
        """
        Gérer les documents d'une demande.
        
        GET /api/seller-verification/requests/{id}/documents/ : Liste des documents
        POST /api/seller-verification/requests/{id}/documents/ : Uploader un document
        """
        verification_request = self.get_object()
        
        # Vérifier que la demande appartient à l'utilisateur
        if verification_request.user != request.user:
            return Response(
                {"detail": "Vous n'avez pas la permission d'accéder à ces documents."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if request.method == 'GET':
            # Liste des documents
            documents = verification_request.documents.all()
            from .serializers import VerificationDocumentSerializer
            serializer = VerificationDocumentSerializer(
                documents,
                many=True,
                context={'request': request}
            )
            return Response(serializer.data)
        
        elif request.method == 'POST':
            # Upload d'un document
            serializer = VerificationDocumentUploadSerializer(
                data=request.data,
                context={
                    'request': request,
                    'verification_request': verification_request
                }
            )
            
            if serializer.is_valid():
                document = serializer.save()
                
                # Valider le document
                is_valid, errors = DocumentValidationService.validate_document(document)
                document.is_valid_format = is_valid
                document.validation_errors = errors
                document.validated_at = timezone.now() if is_valid else None
                document.save()
                
                # Log d'audit
                CertificationAuditLog.objects.create(
                    user=request.user,
                    request=verification_request,
                    document=document,
                    action=CertificationAuditLog.ActionType.DOCUMENT_VALIDATED,
                    actor=request.user,
                    details={
                        "is_valid": is_valid,
                        "errors": errors,
                    }
                )
                
                return Response(
                    VerificationDocumentSerializer(
                        document,
                        context={'request': request}
                    ).data,
                    status=status.HTTP_201_CREATED
                )
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class VerificationDocumentDownloadView(APIView):
    """
    Vue pour télécharger un document de vérification.
    
    GET /api/seller-verification/documents/{id}/download/
    """
    
    permission_classes = [IsVerificationAdmin]
    
    def get(self, request, document_id, format=None):
        """Télécharge un document (accessible uniquement aux admins)."""
        document = get_object_or_404(VerificationDocument, id=document_id)
        
        # Vérifier que l'utilisateur a la permission de voir ce document
        # Les admins peuvent voir tous les documents
        if not request.user.is_staff:
            return Response(
                {"detail": "Permission refusée."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Vérifier que le fichier existe
        if not document.file or not document.file.storage.exists(document.file.name):
            raise Http404("Document non trouvé.")
        
        # Log d'audit de l'accès
        CertificationAuditLog.objects.create(
            user=document.request.user,
            request=document.request,
            document=document,
            action=CertificationAuditLog.ActionType.ADMIN_ACTION,
            actor=request.user,
            details={
                "action": "document_download",
                "filename": document.original_filename,
            }
        )
        
        # Retourner le fichier
        response = FileResponse(
            document.file.open('rb'),
            content_type=document.mime_type
        )
        response['Content-Disposition'] = f'attachment; filename="{document.original_filename}"'
        return response


class AdminVerificationRequestViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet admin pour examiner les demandes de vérification.
    
    Endpoints :
    - GET /api/admin/verification-requests/ : Liste toutes les demandes
    - GET /api/admin/verification-requests/{id}/ : Détails d'une demande
    """
    
    permission_classes = [IsVerificationAdmin]
    serializer_class = VerificationRequestSerializer
    
    def get_queryset(self):
        """Retourne toutes les demandes avec filtrage."""
        queryset = VerificationRequest.objects.all()
        
        # Filtres
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        level_filter = self.request.query_params.get('level')
        if level_filter:
            queryset = queryset.filter(target_level=level_filter)
        
        user_filter = self.request.query_params.get('user')
        if user_filter:
            queryset = queryset.filter(user__username__icontains=user_filter)
        
        return queryset.select_related('user', 'reviewed_by').prefetch_related('documents')
    
    @action(detail=True, methods=['post'])
    def review(self, request, pk=None):
        """
        Examiner une demande de vérification (admin seulement).
        
        POST /api/admin/verification-requests/{id}/review/
        """
        verification_request = self.get_object()
        
        # Vérifier que la demande est en attente
        if verification_request.status not in [
            VerificationRequestStatus.PENDING,
            VerificationRequestStatus.UNDER_REVIEW,
            VerificationRequestStatus.NEEDS_MORE_INFORMATION
        ]:
            return Response(
                {"detail": "Cette demande ne peut plus être examinée."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validation des données
        decision = request.data.get('decision')
        notes = request.data.get('notes', '')
        rejection_reason = request.data.get('rejection_reason', '')
        
        if decision not in ['approve', 'reject', 'request_more_info']:
            return Response(
                {"detail": "Décision invalide. Options: approve, reject, request_more_info"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        with transaction.atomic():
            if decision == 'approve':
                # Approuver la demande
                verification_request.status = VerificationRequestStatus.APPROVED
                verification_request.reviewed_by = request.user
                verification_request.reviewed_at = timezone.now()
                verification_request.decision_notes = notes
                verification_request.save()
                
                # Attribuer la certification
                service = VerificationService()
                try:
                    certification = service.grant_certification(
                        user=verification_request.user,
                        level=verification_request.target_level,
                        granted_by=request.user,
                        verification_request=verification_request,
                        notes=notes
                    )
                    
                    # Log d'audit
                    CertificationAuditLog.objects.create(
                        user=verification_request.user,
                        request=verification_request,
                        certification=certification,
                        action=CertificationAuditLog.ActionType.REQUEST_APPROVED,
                        actor=request.user,
                        details={
                            "level": verification_request.target_level,
                            "notes": notes,
                        }
                    )
                    
                except Exception as e:
                    return Response(
                        {"detail": f"Erreur lors de l'attribution de la certification: {str(e)}"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
            elif decision == 'reject':
                # Refuser la demande
                verification_request.status = VerificationRequestStatus.REJECTED
                verification_request.reviewed_by = request.user
                verification_request.reviewed_at = timezone.now()
                verification_request.decision_notes = notes
                verification_request.rejection_reason = rejection_reason
                verification_request.save()
                
                # Log d'audit
                CertificationAuditLog.objects.create(
                    user=verification_request.user,
                    request=verification_request,
                    action=CertificationAuditLog.ActionType.REQUEST_REJECTED,
                    actor=request.user,
                    details={
                        "notes": notes,
                        "rejection_reason": rejection_reason,
                    }
                )
                
            elif decision == 'request_more_info':
                # Demander plus d'informations
                verification_request.status = VerificationRequestStatus.NEEDS_MORE_INFORMATION
                verification_request.reviewed_by = request.user
                verification_request.reviewed_at = timezone.now()
                verification_request.decision_notes = notes
                verification_request.save()
                
                # Log d'audit
                CertificationAuditLog.objects.create(
                    user=verification_request.user,
                    request=verification_request,
                    action=CertificationAuditLog.ActionType.STATUS_CHANGE,
                    actor=request.user,
                    details={
                        "old_status": "pending",
                        "new_status": "needs_more_information",
                        "notes": notes,
                    }
                )
            
            return Response(
                VerificationRequestSerializer(verification_request).data,
                status=status.HTTP_200_OK
            )
    
    @action(detail=True, methods=['get'])
    def risk_signals(self, request, pk=None):
        """
        Récupère les signaux de risque pour l'utilisateur de cette demande.
        
        GET /api/admin/verification-requests/{id}/risk-signals/
        """
        verification_request = self.get_object()
        
        # Récupérer les signaux de risque actifs
        risk_signals = RiskSignal.objects.filter(
            user=verification_request.user,
            status__in=["active", "reviewed"]
        ).order_by('-severity', '-detected_at')
        
        serializer = RiskSignalSerializer(risk_signals, many=True)
        return Response(serializer.data)


class AdminCertificationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet admin pour gérer les certifications.
    
    Endpoints :
    - GET /api/admin/certifications/ : Liste toutes les certifications
    - GET /api/admin/certifications/{id}/ : Détails d'une certification
    """
    
    permission_classes = [IsVerificationAdmin]
    serializer_class = SellerCertificationSerializer
    
    def get_queryset(self):
        """Retourne toutes les certifications avec filtrage."""
        queryset = SellerCertification.objects.all().select_related(
            'user', 'granted_by', 'revoked_by', 'verification_request'
        )
        
        # Filtres
        user_filter = self.request.query_params.get('user')
        if user_filter:
            queryset = queryset.filter(user__username__icontains=user_filter)
        
        level_filter = self.request.query_params.get('level')
        if level_filter:
            queryset = queryset.filter(level=level_filter)
        
        active_only = self.request.query_params.get('active_only')
        if active_only == 'true':
            queryset = queryset.filter(revoked_at__isnull=True)
        
        return queryset
    
    @action(detail=True, methods=['post'])
    def revoke(self, request, pk=None):
        """
        Révoquer une certification.
        
        POST /api/admin/certifications/{id}/revoke/
        """
        certification = self.get_object()
        
        reason = request.data.get('reason', '')
        
        if not reason:
            return Response(
                {"detail": "Un motif de révocation est requis."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            service = VerificationService()
            service.revoke_certification(certification, request.user, reason)
            
            return Response(
                SellerCertificationSerializer(certification).data,
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class AdminVerificationDashboardView(APIView):
    """
    Tableau de bord admin pour les vérifications.
    
    GET /api/admin/verification-dashboard/
    """
    
    permission_classes = [IsVerificationAdmin]
    
    def get(self, request, format=None):
        """Retourne les statistiques pour le tableau de bord admin."""
        # Demandes par statut
        requests_by_status = VerificationRequest.objects.values('status').annotate(
            count=Count('id')
        ).order_by('status')
        
        # Certifications par niveau
        certifications_by_level = SellerCertification.objects.filter(
            revoked_at__isnull=True
        ).values('level').annotate(
            count=Count('id')
        ).order_by('level')
        
        # Signaux de risque par sévérité
        risk_signals_by_severity = RiskSignal.objects.filter(
            status__in=["active", "reviewed"]
        ).values('severity').annotate(
            count=Count('id')
        ).order_by('severity')
        
        # Demandes en attente (urgentes)
        pending_requests = VerificationRequest.objects.filter(
            status__in=["pending", "under_review"]
        ).order_by('submitted_at')[:10]
        
        pending_serializer = VerificationRequestSerializer(pending_requests, many=True)
        
        return Response({
            "requests_by_status": list(requests_by_status),
            "certifications_by_level": list(certifications_by_level),
            "risk_signals_by_severity": list(risk_signals_by_severity),
            "pending_requests": pending_serializer.data,
            "total_users": User.objects.count(),
            "users_with_certifications": User.objects.filter(
                certifications__revoked_at__isnull=True
            ).distinct().count(),
        })


class ProcessAutomaticCertificationsView(APIView):
    """
    Vue pour traiter les certifications automatiques.
    
    POST /api/internal/process-automatic-certifications/
    (Devrait être appelée par une tâche périodique)
    """
    
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, format=None):
        """
        Traite les certifications automatiques pour tous les utilisateurs.
        
        Cette vue devrait être appelée par une tâche Celery ou cron.
        """
        if not request.user.is_staff:
            return Response(
                {"detail": "Permission refusée."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        processed_users = []
        errors = []
        
        # Traiter les certifications automatiques
        calculator = CertificationCalculator()
        service = VerificationService()
        
        # Parcourir tous les utilisateurs actifs
        users = User.objects.filter(is_active=True, is_email_verified=True)
        
        for user in users:
            try:
                with transaction.atomic():
                    # Calculer les certifications automatiques
                    automatic_levels = calculator.calculate_automatic_certifications(user)
                    
                    # Attribuer chaque certification automatique
                    for level in automatic_levels:
                        # Vérifier si l'utilisateur a déjà cette certification active
                        existing = SellerCertification.objects.filter(
                            user=user,
                            level=level,
                            revoked_at__isnull=True
                        ).exists()
                        
                        if not existing:
                            service.grant_certification(
                                user=user,
                                level=level,
                                granted_by=None,  # Attribution automatique
                                notes="Attribution automatique par le système"
                            )
                    
                    processed_users.append(user.username)
                    
            except Exception as e:
                errors.append({
                    "user": user.username,
                    "error": str(e)
                })
        
        # Vérifier les certifications expirées
        expired_certifications = service.check_for_expired_certifications()
        
        return Response({
            "processed_users": processed_users,
            "errors": errors,
            "expired_certifications_count": len(expired_certifications),
            "expired_certifications": [
                {
                    "user": cert.user.username,
                    "level": cert.level,
                    "expired_at": cert.expires_at.isoformat()
                }
                for cert in expired_certifications
            ],
        })