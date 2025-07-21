import sys
import os

path = '/home/AssetMate/AssetMate'
if path not in sys.path:
    sys.path.append(path)

os.environ['DJANGO_SETTINGS_MODULE'] = 'CMMS.settings'

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()