import importlib.util
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Load `.env` if present (useful for cPanel/Passenger where env vars may not be set).
# Values from the real environment take precedence.
dotenv_path = BASE_DIR / ".env"
if dotenv_path.exists():
    try:
        for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("'").strip('"')
            if key and key not in os.environ:
                os.environ[key] = value
    except OSError:
        pass

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-secret-key-change-in-production")
DEBUG = os.getenv("DJANGO_DEBUG", "False").strip().lower() in {"1", "true", "yes", "on"}

# Allow hosts via env, with a safe fallback for local + production domain.
_allowed_hosts_env = os.getenv(
    "DJANGO_ALLOWED_HOSTS",
    "127.0.0.1,localhost,digitalassettradeintl.com,www.digitalassettradeintl.com",
)
ALLOWED_HOSTS = [host.strip() for host in _allowed_hosts_env.split(",") if host.strip()]

# CSRF trusted origins via env; when not set, default to production origins in non-debug mode.
_csrf_env = os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "").strip()
if _csrf_env:
    CSRF_TRUSTED_ORIGINS = [o.strip() for o in _csrf_env.split(",") if o.strip()]
elif not DEBUG:
    CSRF_TRUSTED_ORIGINS = [
        "https://digitalassettradeintl.com",
        "https://www.digitalassettradeintl.com",
    ]
else:
    CSRF_TRUSTED_ORIGINS = []

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "core.middleware.LockScreenMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

if importlib.util.find_spec("whitenoise") is not None:
    MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

db_engine = os.getenv("DJANGO_DB_ENGINE", "sqlite").strip().lower()

if db_engine == "mysql":
    try:
        import MySQLdb  # type: ignore  # noqa: F401
    except Exception:
        # Allow running without mysqlclient by using PyMySQL as a drop-in replacement.
        try:
            import pymysql  # type: ignore

            pymysql.install_as_MySQLdb()
        except Exception:
            pass
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": os.getenv("DJANGO_DB_NAME", ""),
            "USER": os.getenv("DJANGO_DB_USER", ""),
            "PASSWORD": os.getenv("DJANGO_DB_PASSWORD", ""),
            "HOST": os.getenv("DJANGO_DB_HOST", "localhost"),
            "PORT": os.getenv("DJANGO_DB_PORT", "3306"),
            "OPTIONS": {
                "charset": "utf8mb4",
            },
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

if importlib.util.find_spec("whitenoise") is not None:
    use_manifest_storage = os.getenv("DJANGO_STATIC_USE_MANIFEST", "False").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": (
                "whitenoise.storage.CompressedManifestStaticFilesStorage"
                if use_manifest_storage
                else "whitenoise.storage.CompressedStaticFilesStorage"
            )
        },
    }
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "core.User"
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/user-dashboard/"
LOGOUT_REDIRECT_URL = "/login/"
DEFAULT_FROM_EMAIL = "no-reply@referral.local"

EMAIL_APP_NAME = os.getenv("EMAIL_APP_NAME", "Referral System")
EMAIL_OTP_EXPIRY_MINUTES = int(os.getenv("EMAIL_OTP_EXPIRY_MINUTES", "10"))
EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS = int(
    os.getenv("EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS", "60")
)

if os.getenv("EMAIL_HOST"):
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = os.getenv("EMAIL_HOST")
    EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
    EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
    EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
    EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True").strip().lower() in {"1", "true", "yes", "on"}
    EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "False").strip().lower() in {"1", "true", "yes", "on"}
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
