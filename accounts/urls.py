from django.urls import path
from . import views

urlpatterns = [
    # Frontend URLs
    path("signup/", views.signup_view, name="signup"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("dashboard/", views.dashboard_view, name="dashboard"),
    path("profile/", views.profile_view, name="profile"),
    # API URLs
    path("api/register/", views.UserRegistrationAPIView.as_view(), name="api_register"),
    path("api/login/", views.LoginAPIView.as_view(), name="api_login"),
    path("api/logout/", views.logout_api_view, name="api_logout"),
    path("api/profile/", views.UserProfileAPIView.as_view(), name="api_profile"),
]
