"""
URLs de l'app `accounts`, montées sous `/api/v1/accounts/` (voir config/urls.py).
"""

from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

app_name = "accounts"

urlpatterns = [
    path("register/", views.RegisterView.as_view(), name="register"),
    path("login/", views.CustomTokenObtainPairView.as_view(), name="login"),
    path("login/refresh/", TokenRefreshView.as_view(), name="login-refresh"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("me/", views.MeView.as_view(), name="me"),
    path("users/<slug:username>/", views.PublicProfileView.as_view(), name="public-profile"),
    path("email/verify/", views.EmailVerificationConfirmView.as_view(), name="email-verify"),
    path("email/resend/", views.ResendEmailVerificationView.as_view(), name="email-resend"),
    path("phone/otp/request/", views.PhoneOTPRequestView.as_view(), name="phone-otp-request"),
    path("phone/otp/verify/", views.PhoneOTPVerifyView.as_view(), name="phone-otp-verify"),
    path("password/change/", views.ChangePasswordView.as_view(), name="password-change"),
    path("password/reset/request/", views.PasswordResetRequestView.as_view(), name="password-reset-request"),
    path("password/reset/verify/", views.PasswordResetCodeVerifyView.as_view(), name="password-reset-verify"),
    path("password/reset/confirm/", views.PasswordResetConfirmView.as_view(), name="password-reset-confirm"),
]
