"""
Django settings for FindX — AI-powered Lost & Found Platform
"""

from pathlib import Path
import os
import sys
from dotenv import load_dotenv

import dj_database_url

load_dotenv(override=True)

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("SECRET_KEY", "django-insecure-findx-production-fallback-key-change-in-env-123456789")
DEBUG = os.getenv("DEBUG", "True").lower() == "true"

ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    "[::1]",
    ".onrender.com",
]
RENDER_EXTERNAL_HOSTNAME = os.getenv("RENDER_EXTERNAL_HOSTNAME")
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

CSRF_TRUSTED_ORIGINS = [
    "https://*.onrender.com",
]
if RENDER_EXTERNAL_HOSTNAME:
    CSRF_TRUSTED_ORIGINS.append(f"https://{RENDER_EXTERNAL_HOSTNAME}")

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Local Apps
    'core',
    'accounts',
    'items',
    'matching',
    'claims',
    'chat',
    'notifications',
    'panel',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'lost_and_found.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'notifications.context_processors.unread_notifications',
            ],
        },
    },
]

WSGI_APPLICATION = 'lost_and_found.wsgi.application'

DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.config(
            default=DATABASE_URL,
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

AUTH_USER_MODEL = 'accounts.User'
LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'core:dashboard'
LOGOUT_REDIRECT_URL = 'core:home'

# ─── Email Configuration ───────────────────────────────────────────────────────
_EMAIL_HOST          = os.getenv("EMAIL_HOST", "smtp.gmail.com")
_EMAIL_PORT          = int(os.getenv("EMAIL_PORT", 587))
_EMAIL_USE_TLS       = os.getenv("EMAIL_USE_TLS", "True").lower() in ("true", "1")
_EMAIL_HOST_USER     = os.getenv("EMAIL_HOST_USER", "").strip()
_EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "").replace(" ", "").strip()

DEFAULT_FROM_EMAIL = os.getenv(
    "DEFAULT_FROM_EMAIL",
    f"FindX Platform <{_EMAIL_HOST_USER}>" if _EMAIL_HOST_USER else "noreply@findx.local"
)

_placeholders = ("your_email@gmail.com", "your_16_character", "paste_your_16", "your_16_char_app_password")
IS_SMTP_CONFIGURED = (
    bool(_EMAIL_HOST_USER)
    and bool(_EMAIL_HOST_PASSWORD)
    and _EMAIL_HOST_USER not in _placeholders
    and not any(p in _EMAIL_HOST_PASSWORD for p in _placeholders)
)

if "test" in sys.argv:
    MAILERS = {
        "default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"},
    }
elif IS_SMTP_CONFIGURED:
    MAILERS = {
        "default": {
            "BACKEND": "django.core.mail.backends.smtp.EmailBackend",
            "OPTIONS": {
                "host": _EMAIL_HOST,
                "port": _EMAIL_PORT,
                "username": _EMAIL_HOST_USER,
                "password": _EMAIL_HOST_PASSWORD,
                "use_tls": _EMAIL_USE_TLS,
            },
        },
    }
else:
    MAILERS = {
        "default": {"BACKEND": "django.core.mail.backends.console.EmailBackend"},
    }

# ─── FindX AI Matching Configuration ──────────────────────────────────────────
FINDX_MATCH_WEIGHTS = {
    "image":       0.35,
    "text":        0.30,
    "category":    0.10,
    "color":       0.10,
    "location":    0.10,
    "date":        0.05,
}

FINDX_MATCH_THRESHOLDS = {
    "very_strong": 85,   # notify + highlight
    "strong":      70,   # notify
    "possible":    55,   # store only
    "minimum":     40,   # ignore below this
}

# Gemini API key (optional — for AI answer scoring on claims)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Use sentence-transformers for text matching (downloads ~90MB on first run)
FINDX_USE_SENTENCE_TRANSFORMERS = (
    "test" not in sys.argv
    and os.getenv("USE_SENTENCE_TRANSFORMERS", "false" if os.getenv("RENDER") else "true").lower() == "true"
)
