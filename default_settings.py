import os
import requests
from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import gettext_lazy as _

load_dotenv()

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/3.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

# Only for windows dev mode without docker
if os.name == 'nt' and os.environ.get('DEBUG'):
    DEBUG = True
    GDAL_LIBRARY_PATH = 'C:/OSGeo4W/bin/gdal302'
    GEOS_LIBRARY_PATH = 'C:/OSGeo4W/bin/geos_c'

ALLOWED_HOSTS = os.environ["ALLOWED_HOST"].split(",")

DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'DEFAUL_FROM_EMAIL@example.com')
ADMIN_EMAIL_LIST = os.environ.get('ADMIN_EMAIL_LIST', 'ADMIN_EMAIL_LIST@example.com')
REPLY_TO_EMAIL = os.environ.get('REPLY_TO_EMAIL', 'REPLY_TO_EMAIL@example.ch')

EMAIL_HOST = os.environ.get('EMAIL_HOST', 'localhost')
EMAIL_PORT = os.environ.get('EMAIL_PORT', 1025)
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD')
EMAIL_USE_TLS=True
EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')

# Application definition

INSTALLED_APPS = [
    'api.apps.ApiConfig',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.gis',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'djmoney',
    'allauth',
    'allauth.account',
    'rest_framework',
    'rest_framework_gis',
    'rest_framework_simplejwt',
    'drf_spectacular',
    'corsheaders',
    'health_check',
    'health_check.db',
    'health_check.contrib.migrations',
    'django_extended_ol',
    'pgtrigger',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': ['api/templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'oidc.status',
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'wsgi.application'


# Password validation
# https://docs.djangoproject.com/en/3.0/ref/settings/#auth-password-validators

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
# https://docs.djangoproject.com/en/3.0/topics/i18n/

LANGUAGE_CODE = os.getenv('DEFAULT_LANGUAGE', 'en')
DEFAULT_CURRENCY = 'CHF'

LOCALE_PATHS = [
    './api/locale',
    './locale',
]

LANGUAGES = (
    ('de', _('German')),
    ('it', _('Italian')),
    ('fr', _('French')),
    ('en', _('English')),
    ('rm', _('Romansh')),
)

TIME_ZONE = 'Europe/Zurich'
DATE_FORMAT = '%d.%m.%Y'
USE_I18N = True

USE_L10N = True

USE_TZ = True

SITE_ID = 2

VAT = 0.081

# Database
# https://docs.djangoproject.com/en/3.0/ref/settings/#databases
DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'
DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': os.environ["PGDATABASE"],
        'USER': os.environ["PGUSER"],
        'HOST': os.environ["PGHOST"],
        'PORT': os.environ["PGPORT"],
        'PASSWORD': os.environ["PGPASSWORD"],
        'OPTIONS': {
            'options': '-c search_path=' + os.environ["PGSCHEMA"] + ',public'
        },
    }
}

# Special needs for geoshop running on PostgreSQL
SPECIAL_DATABASE_CONFIG = {
    # A search config with this name must exist on your database, please refer to
    # https://www.postgresql.org/docs/current/textsearch-intro.html#TEXTSEARCH-INTRO-CONFIGURATIONS
    'FTS_SEARCH_CONFIG': LANGUAGE_CODE
}

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simple': {
            'format': '{levelname} {module} {filename} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': os.getenv('LOGGING_LEVEL', 'ERROR'),
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': os.getenv('LOGGING_LEVEL', 'ERROR'),
            'propagate': False,
        },
        # uncomment this for DB logging
        #'django.db.backends': {
        #    'level': 'DEBUG',
        #    'handlers': ['console'],
        #}
    },
}

# Django REST specific configuration
# https://www.django-rest-framework.org/
REST_FRAMEWORK = {
    # Use Django's standard `django.contrib.auth` permissions,
    # or allow read-only access for unauthenticated users.
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.DjangoModelPermissionsOrAnonReadOnly'
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.LimitOffsetPagination',
    'PAGE_SIZE': 100,
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'geoshop API',
    'DESCRIPTION': 'API for the geoshop',
    'VERSION': '0.1.0',
    'SERVE_INCLUDE_SCHEMA': False,
    # OTHER SETTINGS
}

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.0/howto/static-files/

USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
FORCE_SCRIPT_NAME = os.environ.get('FORCE_SCRIPT_NAME', '')
ROOTURL=os.getenv('ROOTURL', '')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
# For large admin fields like order with order items
DATA_UPLOAD_MAX_NUMBER_FIELDS = 5000

STATIC_URL = FORCE_SCRIPT_NAME + ROOTURL + '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'static')
MEDIA_ROOT = os.environ.get('MEDIA_ROOT', os.path.join(BASE_DIR, 'files'))
MEDIA_URL = os.environ.get('MEDIA_URL', FORCE_SCRIPT_NAME + ROOTURL +'/files/')

FRONT_PROTOCOL = os.environ["FRONT_PROTOCOL"]
FRONT_URL = os.environ["FRONT_URL"]
BACKEND_URL = os.environ.get("BACKEND_URL", "localhost:8000")
FRONT_HREF = os.environ.get("FRONT_HREF", '')
CSRF_COOKIE_DOMAIN = os.environ["CSRF_COOKIE_DOMAIN"]
CSRF_TRUSTED_ORIGINS = []

for host in ALLOWED_HOSTS:
    CSRF_TRUSTED_ORIGINS.append(f'http://{host}')
    CSRF_TRUSTED_ORIGINS.append(f'https://{host}')

CORS_ALLOWED_ORIGINS = os.environ['CORS_ALLOWED_ORIGINS'].split(',') if 'CORS_ALLOWED_ORIGINS' in os.environ else []
CORS_ALLOWED_ORIGIN_REGEXES = os.environ['CORS_ALLOWED_ORIGIN_REGEXES'].split(',') if 'CORS_ALLOWED_ORIGIN_REGEXES' in os.environ else []

CORS_ORIGIN_WHITELIST = [
    os.environ["FRONT_PROTOCOL"] + '://' + os.environ["FRONT_URL"],
]
DEFAULT_PRODUCT_THUMBNAIL_URL = 'default_product_thumbnail.png'
DEFAULT_METADATA_IMAGE_URL = 'default_metadata_image.png'
AUTO_LEGEND_URL = os.environ.get('AUTO_LEGEND_URL', '')
INTRA_LEGEND_URL = os.environ.get('INTRA_LEGEND_URL', '')

# Geometries settings
# FIXME: Does this work with another SRID?
DEFAULT_SRID = int(os.environ.get('DEFAULT_SRID', '2056'))

# default extent is set to the BBOX of switzerland
DEFAULT_EXTENT = (2828694.200665463,1075126.8548189853,2484749.5514877755,1299777.3195268118)

# Controls values of metadata accessibility field that will turn the metadata public
METADATA_PUBLIC_ACCESSIBILITIES = ['PUBLIC', 'APPROVAL_NEEDED']

# Healthcheck subsets configuration
HEALTH_CHECK = {
    "SUBSETS": {
        "startup": ["MigrationsHealthCheck", "DatabaseBackend"],
        "readiness": ["DatabaseBackend"],
        "liveness": []
    },
}

FEATURE_FLAGS = {
    "oidc": os.environ.get("OIDC_ENABLED", "False") == "True",
    "registration": os.environ.get("REGISTRATION_ENABLED", "True") == "True",
    "local_auth": os.environ.get("LOCAL_AUTH_ENABLED", "True") == "True"
}

AUTHENTICATION_BACKENDS = ("django.contrib.auth.backends.ModelBackend",)


# OIDC configuration
def discover_endpoints(discovery_url: str) -> dict:

    """
    Performs OpenID Connect discovery to retrieve the provider configuration.
    """
    response = requests.get(discovery_url)
    if response.status_code != 200:
        raise ValueError("Failed to retrieve provider configuration.")

    provider_config = response.json()

    # Extract endpoint URLs from provider configuration
    return {
        "authorization_endpoint": provider_config["authorization_endpoint"],
        "token_endpoint": provider_config["token_endpoint"],
        "userinfo_endpoint": provider_config["userinfo_endpoint"],
        "jwks_uri": provider_config["jwks_uri"],
        "introspection_endpoint": provider_config["introspection_endpoint"],
    }


def check_oidc() -> bool:
    if not FEATURE_FLAGS['oidc']:
        return False
    missing = []
    for x in ["OIDC_RP_CLIENT_ID", "ZITADEL_PROJECT", "OIDC_OP_BASE_URL", "OIDC_PRIVATE_KEYFILE"]:
        if not os.environ.get(x):
            missing.append(x)
    if missing:
        raise ImproperlyConfigured(f"OIDC is enabled, but missing required parameters {missing}")
    return True

if check_oidc():
    INSTALLED_APPS.append('mozilla_django_oidc')
    MIDDLEWARE.append('mozilla_django_oidc.middleware.SessionRefresh')
    AUTHENTICATION_BACKENDS = ('oidc.PermissionBackend',) + AUTHENTICATION_BACKENDS
    REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"] = (
        "oidc.PermissionBackend",
    ) + REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]

    OIDC_RP_CLIENT_ID = os.environ.get("OIDC_RP_CLIENT_ID")
    ZITADEL_PROJECT = os.environ.get("ZITADEL_PROJECT")
    OIDC_RP_CLIENT_SECRET = os.environ.get("OIDC_RP_CLIENT_SECRET")
    OIDC_OP_BASE_URL = os.environ.get("OIDC_OP_BASE_URL")
    OIDC_PRIVATE_KEYFILE = os.environ.get("OIDC_PRIVATE_KEYFILE")

    OIDC_RP_SIGN_ALGO = "RS256"
    OIDC_RP_SCOPES = "openid profile email address phone locale"
    OIDC_USE_PKCE = True

    discovery_info = discover_endpoints(
        OIDC_OP_BASE_URL + "/.well-known/openid-configuration"
    )
    OIDC_INTROSPECT_URL = discovery_info["introspection_endpoint"]
    OIDC_OP_AUTHORIZATION_ENDPOINT = discovery_info["authorization_endpoint"]
    OIDC_OP_TOKEN_ENDPOINT = discovery_info["token_endpoint"]
    OIDC_OP_USER_ENDPOINT = discovery_info["userinfo_endpoint"]
    OIDC_OP_JWKS_ENDPOINT = discovery_info["jwks_uri"]

    OIDC_REDIRECT_ALLOWED_HOSTS = os.environ["OIDC_REDIRECT_ALLOWED_HOST"].split(",")
    LOGIN_REDIRECT_URL = os.environ.get("OIDC_REDIRECT_BASE_URL") + "/oidc/callback"
    LOGOUT_REDIRECT_URL = os.environ.get("OIDC_REDIRECT_BASE_URL") + "/"
    LOGIN_URL = os.environ.get("OIDC_REDIRECT_BASE_URL") + "/oidc/authenticate"

# Customize openlayers widget used in admin interface
OLWIDGET = {
    "globals": {
        "srid": DEFAULT_SRID,
        "extent": [2420000, 130000, 2900000, 1350000],
        "resolutions": [
            4000, 3750, 3500, 3250, 3000, 2750, 2500, 2250, 2000, 1750, 1500, 1250,
            1000, 750, 650, 500, 250, 100, 50, 20, 10, 5, 2.5, 2, 1.5, 1, 0.5
        ],
    },
    "wmts": {
        "layer_name": 'ch.kantone.cadastralwebmap-farbe',
        "style": 'default',
        "matrix_set": '2056',
        "attributions": '<a target="new" href="https://www.swisstopo.admin.ch/internet/swisstopo/en/home.html"'
            + '>swisstopo</a>', # optional
        "url_template": 'https://wmts10.geo.admin.ch/1.0.0/{Layer}/default/current/2056/{TileMatrix}/{TileCol}/{TileRow}.png',
        "request_encoding": 'REST', # optional
        "format": 'image/png' # optional
    }
}

# Limit maximum allowed area of an order, in square meters. 0 for unlimited
MAX_ORDER_AREA=float(os.environ.get("MAX_ORDER_AREA", "0"))

# 25 Megabytes
DATA_UPLOAD_MAX_MEMORY_SIZE=int(os.environ.get("DATA_UPLOAD_MAX_MEMORY_SIZE", "26214400"))
