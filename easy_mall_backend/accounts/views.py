"""
Vues de l'app `accounts`.

Nécessite dans settings.py : `rest_framework_simplejwt`,
`rest_framework_simplejwt.token_blacklist` (pour le logout), et des scopes
de throttling `register` / `login` / `otp` dans DEFAULT_THROTTLE_RATES
(voir §10 du document d'architecture — limitation des tentatives).
"""

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import User
from .serializers import (
    ChangePasswordSerializer,
    CustomTokenObtainPairSerializer,
    EmailVerificationConfirmSerializer,
    MeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetCodeVerifySerializer,
    PasswordResetRequestSerializer,
    PhoneOTPRequestSerializer,
    PhoneOTPVerifySerializer,
    RegisterSerializer,
    ResendEmailVerificationSerializer,
    UserSerializer,
    UserUpdateSerializer,
)


class RegisterView(generics.CreateAPIView):
    """
    Inscription — déclenche l'envoi async des vérifications e-mail/téléphone,
    et retourne directement les tokens JWT (pas besoin d'un second appel à
    /login/ juste après : ce round-trip supplémentaire pouvait échouer
    indépendamment de l'inscription elle-même — notamment si l'e-mail est
    retapé avec une casse différente, la recherche de connexion est stricte
    par défaut — créant une confusion "erreur affichée alors que le compte
    est bien créé").
    """

    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    throttle_scope = "register"
    throttle_classes = [ScopedRateThrottle]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {
                "detail": "Compte créé avec succès. Vérifiez votre e-mail pour activer votre compte.",
                "user": MeSerializer(user).data,
            },
            status=status.HTTP_201_CREATED,
        )


class CustomTokenObtainPairView(TokenObtainPairView):
    """Connexion — access + refresh token JWT, throttlée contre le brute-force."""

    serializer_class = CustomTokenObtainPairSerializer
    throttle_scope = "login"
    throttle_classes = [ScopedRateThrottle]


class LogoutView(APIView):
    """Déconnexion — blackliste le refresh token."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        refresh = request.data.get("refresh")
        if not refresh:
            return Response(
                {"detail": "Le champ 'refresh' est requis."}, status=status.HTTP_400_BAD_REQUEST
            )
        try:
            RefreshToken(refresh).blacklist()
        except Exception:
            return Response({"detail": "Token invalide."}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_205_RESET_CONTENT)


class MeView(generics.RetrieveUpdateAPIView):
    """Profil de l'utilisateur connecté (lecture + mise à jour)."""

    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

    def get_serializer_class(self):
        return UserUpdateSerializer if self.request.method in ("PUT", "PATCH") else MeSerializer


class PublicProfileView(generics.RetrieveAPIView):
    """Profil public d'un utilisateur (ex. consulté depuis une fiche produit)."""

    queryset = User.objects.filter(is_active=True)
    serializer_class = UserSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = "username"


class EmailVerificationConfirmView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_scope = "email_verify"
    throttle_classes = [ScopedRateThrottle]

    def post(self, request):
        serializer = EmailVerificationConfirmSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": "E-mail vérifié avec succès."})


class ResendEmailVerificationView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_scope = "email_resend"
    throttle_classes = [ScopedRateThrottle]

    def post(self, request):
        serializer = ResendEmailVerificationSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": "Code de vérification renvoyé."})


class PhoneOTPRequestView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_scope = "otp"
    throttle_classes = [ScopedRateThrottle]

    def post(self, request):
        serializer = PhoneOTPRequestSerializer(data={}, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": "Code envoyé par SMS."})


class PhoneOTPVerifyView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = PhoneOTPVerifySerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": "Numéro de téléphone vérifié avec succès."})


class PasswordResetRequestView(APIView):
    """Toujours répondre 200, que l'e-mail existe ou non (anti-énumération de comptes)."""

    permission_classes = [permissions.AllowAny]
    throttle_scope = "password_reset"
    throttle_classes = [ScopedRateThrottle]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": "Si cet e-mail existe, un code de réinitialisation a été envoyé."})


class PasswordResetCodeVerifyView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PasswordResetCodeVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response({"detail": "Code valide."})


class PasswordResetConfirmView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": "Mot de passe réinitialisé avec succès."})


class ChangePasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": "Mot de passe modifié avec succès."})
