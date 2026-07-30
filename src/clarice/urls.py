"""
URL configuration for clarice project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path
from accounts.views import LandingLoginView
from lists import views as list_views

from clarice.api import api as api_v1


urlpatterns = [
    path("", LandingLoginView.as_view(), name="home"),
    path("dashboard/", list_views.dashboard, name="dashboard"),
    path("archive/", list_views.archive, name="archive"),
    path("app/", list_views.spa_shell, name="app_shell"),
    path("app/<path:subpath>", list_views.spa_shell, name="app_shell_path"),
    path("api/", include("lists.api_urls")),
    path("api/v1/", api_v1.urls),
    path("lists/", include("lists.urls")),
    path("accounts/", include("accounts.urls")),
    path("admin/", admin.site.urls),
]
