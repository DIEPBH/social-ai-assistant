from django.urls import path

from .views import privacy_policy
from .admin_dashboard import admin_dashboard
urlpatterns = [
     path("privacy-policy/", privacy_policy),
     path("", privacy_policy),  # Đảm bảo rằng URL gốc cũng được định tuyến đến privacy_policy
     path("admin-dashboard/", admin_dashboard, name="admin_dashboard"),
]