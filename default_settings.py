import os
from django.utils.translation import gettext_lazy as _

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
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'localhost')
EMAIL_PORT = os.environ.get('EMAIL_PORT', 1025)
# Setting to test email sending in console
EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')

#
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'DEFAUL_FROM_EMAIL@example.com')
ADMIN_EMAIL_LIST = os.environ.get('ADMIN_EMAIL_LIST', 'ADMIN_EMAIL_LIST@example.com')
REPLY_TO_EMAIL = os.environ.get('REPLY_TO_EMAIL', 'REPLY_TO_EMAIL@example.ch')

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
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
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
FORCE_SCRIPT_NAME = os.environ.get('ROOTURL', '')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
# For large admin fields like order with order items
DATA_UPLOAD_MAX_NUMBER_FIELDS = 5000

STATIC_URL = FORCE_SCRIPT_NAME + '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'static')
MEDIA_ROOT = os.environ.get('MEDIA_ROOT', os.path.join(BASE_DIR, 'files'))
MEDIA_URL = os.environ.get('MEDIA_URL', FORCE_SCRIPT_NAME + '/files/')

FRONT_PROTOCOL = os.environ["FRONT_PROTOCOL"]
FRONT_URL = os.environ["FRONT_URL"]
FRONT_HREF = os.environ.get("FRONT_HREF", '')
CSRF_COOKIE_DOMAIN = os.environ["CSRF_COOKIE_DOMAIN"]
CSRF_TRUSTED_ORIGINS = []

for host in ALLOWED_HOSTS:
    CSRF_TRUSTED_ORIGINS.append(f'http://{host}')
    CSRF_TRUSTED_ORIGINS.append(f'https://{host}')

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

# Default Extent
# default extent is set to the BBOX of switzerland
SWISS_EXTENT = (2828694.200665463,1075126.8548189853,2484749.5514877755,1299777.3195268118)

# Controls values of metadata accessibility field that will turn the metadata public
METADATA_PUBLIC_ACCESSIBILITIES = ['PUBLIC', 'APPROVAL_NEEDED']
