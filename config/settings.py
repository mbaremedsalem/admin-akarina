"""
Configuration Django du projet Agharina.
Systeme de vente / location de biens immobiliers.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = "django-insecure-change-moi-en-production"
DEBUG = True
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Tiers
    "rest_framework",
    "rest_framework.authtoken",
    "django_filters",
    "corsheaders",

    # Apps metier Agharina
    "comptes",
    "localisation",
    "immobilier",
    "transactions",
    "fidelite",
    "offres",
    "notifications",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# DATABASES = {
#     "default": {
#         "ENGINE": os.environ.get("DB_ENGINE", "django.db.backends.sqlite3"),
#         "NAME": os.environ.get("DB_NAME", BASE_DIR / "db.sqlite3"),
#         "USER": os.environ.get("DB_USER", ""),
#         "PASSWORD": os.environ.get("DB_PASSWORD", ""),
#         "HOST": os.environ.get("DB_HOST", ""),
#         "PORT": os.environ.get("DB_PORT", ""),
#         # Schema dedie : cette base est partagee avec un autre projet (Akareena) sur
#         # le meme cluster PostgreSQL. "agharina" isole completement nos tables et
#         # notre historique de migrations de l'existant (schema "public").
#         "OPTIONS": (
#             {"sslmode": "require", "options": "-c search_path=agharina"}
#             if os.environ.get("DB_HOST")
#             else {}
#         ),
#     }
# }

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


AUTH_USER_MODEL = "comptes.Utilisateur"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Africa/Nouakchott"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Un bien peut recevoir jusqu'a 35 photos/videos en un seul POST (voir
# MediaBienViewSet.create) : on autorise explicitement une marge au-dessus
# de ce chiffre plutot que de dependre des valeurs par defaut de Django.
DATA_UPLOAD_MAX_NUMBER_FILES = 50
DATA_UPLOAD_MAX_NUMBER_FIELDS = 100

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.BasicAuthentication",
        "rest_framework.authentication.TokenAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
}

# Frontend admin (agharina-admin-frontend) sert depuis un autre port en dev.
# CORS_ALLOW_ALL_ORIGINS n'est active qu'en DEBUG (jamais en production).
CORS_ALLOW_ALL_ORIGINS = DEBUG

# Notifications push (Firebase Cloud Messaging). Le fichier de la cle de service
# n'est jamais commite (voir .gitignore) ; en production, definir
# FIREBASE_CREDENTIALS_PATH vers un emplacement securise en dehors du depot.
FIREBASE_CREDENTIALS_PATH = os.environ.get(
    "FIREBASE_CREDENTIALS_PATH",
    str(BASE_DIR / "akarena-firebase-adminsdk-fbsvc-a00a0e1886.json"),
)
