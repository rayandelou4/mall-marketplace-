from django.urls import path

from .views import NegotiationActionView, NegotiationListCreateView

app_name = "negotiations"

urlpatterns = [
    path("", NegotiationListCreateView.as_view(), name="list-create"),
    path("<uuid:pk>/accept/", NegotiationActionView.as_view(action_name="accept"), name="accept"),
    path("<uuid:pk>/reject/", NegotiationActionView.as_view(action_name="reject"), name="reject"),
    path("<uuid:pk>/counter/", NegotiationActionView.as_view(action_name="counter"), name="counter"),
]