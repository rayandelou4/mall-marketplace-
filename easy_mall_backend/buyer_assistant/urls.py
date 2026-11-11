from django.urls import path

from .views import BuyerAssistantConfigView, BuyerAssistantSearchView

app_name = "buyer_assistant"

urlpatterns = [
    path("config/", BuyerAssistantConfigView.as_view(), name="config"),
    path("search/", BuyerAssistantSearchView.as_view(), name="search"),
]