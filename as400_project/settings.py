# Django settings for as400_project project.
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = BASE_DIR / 'logs'
LOG_DIR.mkdir(exist_ok=True)

# Carregar variáveis do .env
load_dotenv(BASE_DIR / '.env')

# ==================== SEGURANÇA ====================
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-...')
DEBUG = os.getenv('DEBUG', 'False') == 'True'
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '').split(',')

# ==================== APPS ====================
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'pessoas',
]

# ==================== MIDDLEWARE ====================
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'as400_project.urls'

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
            ],
        },
    },
]

WSGI_APPLICATION = 'as400_project.wsgi.application'

# ==================== BANCO DE DADOS (SQLite para sessões) ====================
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# ==================== VALIDAÇÃO DE SENHA ====================
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ==================== INTERNACIONALIZAÇÃO ====================
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True

#SCRIPT_NAME_PREFIX = os.getenv('SCRIPT_NAME_PREFIX', '').strip('/')

#if SCRIPT_NAME_PREFIX:
#    FORCE_SCRIPT_NAME = f'/{SCRIPT_NAME_PREFIX}'
#    STATIC_URL = f'/{SCRIPT_NAME_PREFIX}/static/'
#    MEDIA_URL  = f'/{SCRIPT_NAME_PREFIX}/media/'
#    CSRF_COOKIE_PATH    = f'/{SCRIPT_NAME_PREFIX}'
#    SESSION_COOKIE_PATH = f'/{SCRIPT_NAME_PREFIX}'
#    USE_X_FORWARDED_HOST = True
#    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
#else:
#    FORCE_SCRIPT_NAME = None
#    STATIC_URL = '/static/'
#    MEDIA_URL  = '/media/'

# ==================== SUBPATH (sempre raiz agora) ====================
# Estamos usando subdomínios, então não precisamos de FORCE_SCRIPT_NAME.
FORCE_SCRIPT_NAME = None
STATIC_URL = '/static/'
MEDIA_URL  = '/media/'

# Proxy HTTPS atrás do Nginx
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')


# ==================== ARQUIVOS ESTÁTICOS ====================
#STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# ==================== CACHE (em memória, suficiente para testes) ====================
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'as400-cache',
        'TIMEOUT': 300,
        'OPTIONS': {'MAX_ENTRIES': 1000},
    }
}

# ==================== LOGS ====================
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
        'file': {
            'level': 'ERROR',
            'class': 'logging.FileHandler',
            'filename': str(LOG_DIR / 'django_errors.log'),
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'console'],
            'level': 'ERROR',
            'propagate': True,
        },
        'pessoas': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}

# ==================== VARIÁVEIS DO AS/400 ====================
AS400_HOST = os.getenv('AS400_HOST')
AS400_USER = os.getenv('AS400_USER')
AS400_PASSWORD = os.getenv('AS400_PASSWORD')
AS400_LIBRARY = os.getenv('AS400_LIBRARY')

# ==================== UPLOAD ====================
DATA_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024 * 100  # 100 MB
# ==================== DEEPSEEK ====================
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY', '')
