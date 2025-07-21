"""
URL configuration for emotionalTracker project.

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
from django.urls import path, include
from .views import EmotionViewSet, EmotionOverviewSet, AuthViewSet, ManagerOverViewSet, DepartmentDirectorOverviewSet, EntityDirectorOverviewSet, PoleDirectorOverviewSet
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView


router = DefaultRouter()
router.register(r'emotions', EmotionViewSet, basename='emotion')
router.register(r'emotion-overview', EmotionOverviewSet, basename='emotion-overview')
router.register(r'manager', ManagerOverViewSet, basename='manager-overview')
router.register(r'department', DepartmentDirectorOverviewSet, basename='department-overview')
router.register(r'entity', EntityDirectorOverviewSet, basename='entity-overview')
router.register(r'cluster', PoleDirectorOverviewSet, basename='cluster-overview')
router.register(r'auth', AuthViewSet, basename='auth')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include(router.urls)),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]
