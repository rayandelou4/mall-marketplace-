from django.urls import path

from .views import AssistantConfigView, ListingSuggestionsView

app_name = "seller_assistant"

urlpatterns = [
    path("config/", AssistantConfigView.as_view(), name="config"),
    path("suggestions/", ListingSuggestionsView.as_view(), name="suggestions"),
]