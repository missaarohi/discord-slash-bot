from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path("interactions", views.discord_interactions, name="discord_interactions"),

    path("", views.dashboard, name="dashboard"),
    path("signup/", views.signup, name="signup"),
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="bot/login.html", redirect_authenticated_user=True),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),

    path("servers/connect/", views.connect_server, name="connect_server"),
    path("servers/<int:server_id>/config/", views.command_config, name="command_config"),
]