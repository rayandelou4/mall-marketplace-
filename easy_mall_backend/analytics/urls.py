"""
URLs de l'app `analytics`, montées sous `/api/v1/analytics/` (voir config/urls.py).
"""

from django.urls import path

from . import views

app_name = "analytics"

urlpatterns = [
    path("stats/", views.GlobalStatsView.as_view(), name="global-stats"),
    path("seller/", views.SellerStatsView.as_view(), name="seller-stats"),
]
