# Importaciones de Django y librerías necesarias para URLs y autenticación
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from GeoInsightApp.decorators import role_required
from django.contrib.auth import views as auth_views
from rest_framework.routers import DefaultRouter
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from rest_framework_simplejwt.views import TokenRefreshView

from GeoInsightApp.auth_views import CustomTokenObtainPairView, PasswordResetRequestView, PasswordResetConfirmView

# Importación de viewsets de la API
from GeoInsightApp.api_views import (
    UserProfileViewSet, CourseViewSet, GroupViewSet, GroupMemberViewSet,
    CompanyViewSet, VisitViewSet, EvidenceViewSet, ReviewViewSet,
    SectionViewSet, CareerViewSet, SemesterViewSet,
    YearViewSet, AdminSemesterViewSet, AdminCareerViewSet, AdminCourseViewSet, VCMSectionViewSet,
    AdminSectionViewSet, UserProfileAdminViewSet, VisitManagementViewSet, DocenteAssignViewSet
)

# Importación de vistas funcionales
from GeoInsightApp.views import current_user, register, logout_view, descargar_pdf_seccion_api, descargar_excel_seccion_api, descargar_imagenes_seccion_api

# Protección de login para el admin
protected_admin_login = role_required(allowed_roles=['admin'])(auth_views.LoginView.as_view())

# Configuración del router de la API REST
router = DefaultRouter()
router.register(r'users', UserProfileViewSet)
router.register(r'careers', CareerViewSet)
router.register(r'semesters', SemesterViewSet)
router.register(r'courses', CourseViewSet)
router.register(r'sections', SectionViewSet) 
router.register(r'groups', GroupViewSet, basename='groups')
router.register(r'groupmembers', GroupMemberViewSet)
router.register(r'companies', CompanyViewSet)
router.register(r'visits', VisitViewSet, basename='visit')
router.register(r'evidences', EvidenceViewSet)
router.register(r'reviews', ReviewViewSet)

#Ruta de VCM
router.register(r"vcm/sections", VCMSectionViewSet, basename="vcm-section")

#Ruta para asignacion docente
router.register(r"admin/asignacion-docente", DocenteAssignViewSet, basename="asignacion-docente")

# Nuevos registros para administración
router.register(r'years', YearViewSet)
router.register(r'admin/semesters', AdminSemesterViewSet, basename='admin-semesters')
router.register(r'admin/careers', AdminCareerViewSet, basename='admin-careers')
router.register(r'admin/courses', AdminCourseViewSet, basename='admin-courses')
router.register(r'admin/sections', AdminSectionViewSet, basename='admin-section')
router.register(r'admin/users', UserProfileAdminViewSet, basename='admin-user-profile')
router.register(r'admin/visits', VisitManagementViewSet, basename='admin-visits')

urlpatterns = [
    path('api/logout/', logout_view, name='logout'),

    # Rutas de usuarios y autenticación
    path('api/users/me/', current_user, name='current-user'),
    path('api/register/', register, name='register'),
    path('api/token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    path('api/sections/<int:seccion_id>/exp-pdf/', descargar_pdf_seccion_api, name='descargar_pdf_seccion'),
    path('api/sections/<int:seccion_id>/excel/', descargar_excel_seccion_api, name='descargar_excel_seccion'),
    path('api/sections/<int:seccion_id>/imagenes/', descargar_imagenes_seccion_api, name='descargar_imagenes_seccion'),

    # Rutas de administración
    path('admin/login/', protected_admin_login, name='admin_login'),
    path('admin/', admin.site.urls),

    # Rutas de la API REST registradas en el router
    path('api/', include(router.urls)),

    # Documentación y esquema de la API
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    path('api/swagger/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),

    path('api/password-reset/', PasswordResetRequestView.as_view(), name='password_reset_request'),
    path('api/password-reset-confirm/', PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
]


# Servir archivos media en modo desarrollo
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
