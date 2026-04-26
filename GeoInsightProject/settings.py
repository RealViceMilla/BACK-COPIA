# Importaciones 
from pathlib import Path
from datetime import timedelta
import environ
import os

BASE_DIR = Path(__file__).resolve().parent.parent

#Rutas para las carpetas de static y templates
STATIC_DIR = os.path.join(BASE_DIR, 'static')
TEMPLATE_DIR = os.path.join(BASE_DIR, 'templates')

# Inicializa django-environ
env = environ.Env()
environ.Env.read_env(os.path.join(BASE_DIR, ".env"))

# Carga dinámicamente desde el .env
GDAL_LIBRARY_PATH = env("GDAL_LIBRARY_PATH")
GEOS_LIBRARY_PATH = env("GEOS_LIBRARY_PATH")

SECRET_KEY = env('SECRET_KEY', default='insecure-key')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env.bool('DEBUG', default=True)
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=[])

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    'django.contrib.gis',
    'rest_framework',
    'rest_framework_gis',
    'rest_framework_simplejwt',
    'widget_tweaks',
    'leaflet',
    'corsheaders',
    'drf_spectacular',
    
    'GeoInsightApp',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'GeoInsightProject.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [TEMPLATE_DIR],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'GeoInsightProject.wsgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': env("POSTGRES_DB"),
        'USER': env("POSTGRES_USER"),
        'PASSWORD': env("POSTGRES_PASSWORD"),
        'HOST': env("POSTGRES_HOST"),
        'PORT': env.int("POSTGRES_PORT"),
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'America/Santiago'

USE_I18N = True

USE_TZ = True

# Cookies
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False

SESSION_COOKIE_SECURE = not DEBUG 
CSRF_COOKIE_SECURE = not DEBUG

SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"



# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# Configuración para archivos de media
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Leaflet Configuración
LEAFLET_CONFIG = {
    'DEFAULT_CENTER': (40.7128, -74.0060),
    'DEFAULT_ZOOM': 10,
    'MIN_ZOOM': 3,
    'MAX_ZOOM': 18,
    'SPATIAL_EXTENT': (-180, -90, 180, 90),
    'TILES': [
        ('OpenStreetMap', 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {'attribution': '© OpenStreetMap contributors'}),
    ],
    'SRID': 4326, 
}

# Opcional GIS widgets
GIS_WIDGETS = {
    "default": "OLWidgetMap",
}

# Conexión con Frontend
CORS_ALLOWED_ORIGINS = [
    "https://www.terrenoregistro.cl",
    "https://terrenoregistro.cl",
]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    'content-type',
    'authorization',
    'x-csrftoken',
]

# Autenticación con JWT en vez de sesiones
REST_FRAMEWORK = {
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'GeoInsightApp.authentication.CookieJWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
}


SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}


SPECTACULAR_SETTINGS = {
    'TITLE': 'GeoInsight API',
    'DESCRIPTION': 'Documentación de la API de GeoInsight',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    
    # Configuración de Swagger UI
    'SWAGGER_UI_SETTINGS': {
        'dom_id': '#swagger-ui',
        'deepLinking': True,
        'showExtensions': True,
        'showCommonExtensions': True,
        'docExpansion': 'none',
        'defaultModelsExpandDepth': 1,
        'defaultModelExpandDepth': 1,
        'displayOperationId': True,
        'displayRequestDuration': True,
    },
}

# Configuración de correo electrónico
EMAIL_BACKEND = env('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = env('EMAIL_HOST', default='smtp.terrenoregistro.cl')
EMAIL_PORT = env.int('EMAIL_PORT', default=587)
EMAIL_USE_TLS = env.bool('EMAIL_USE_TLS', default=True)
EMAIL_USE_SSL = env.bool('EMAIL_USE_SSL', default=False)
EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')
EMAIL_TIMEOUT = env.int('EMAIL_TIMEOUT', default=30)
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default='no-reply@terrenoregistro.cl')
PASSWORD_RESET_FRONTEND_URL = env('PASSWORD_RESET_FRONTEND_URL', default='https://terrenoregistro.cl/reset-password')