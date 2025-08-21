from django.urls import path
from . import views

app_name = "users"
urlpatterns = [
    path("login/", views.custom_login, name="login"),
    path("logout/", views.custom_logout, name="logout"),
    path("redirect/", views.user_redirect, name="redirect"),
    path("profile/", views.user_landing, name="profile"),
]
