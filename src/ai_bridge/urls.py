from django.urls import path
from .views import analyze_message_bridge

urlpatterns = [
    path("analyze-message/", analyze_message_bridge, name="analyze_message_bridge"),
]