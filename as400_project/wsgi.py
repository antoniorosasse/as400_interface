# Django WSGI application for as400_project project.
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'as400_project.settings')

# Forçar carregamento do .env no wsgi
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).resolve().parent.parent / '.env')

application = get_wsgi_application()