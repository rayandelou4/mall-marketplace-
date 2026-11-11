from django.urls import path

from .views import VisualSearchConfigView, VisualSearchView

app_name = "visual_search"

urlpatterns = [
    path("config/", VisualSearchConfigView.as_view(), name="config"),
    path("search/", VisualSearchView.as_view(), name="search"),
]