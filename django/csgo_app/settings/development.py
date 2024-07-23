from csgo_app.settings.common import *


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-xw%w2h+2dig8-_b_6&1(&67=d1748ur-tt%=e#3kgi@z*##jqa'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []

# The CSGO API should be disabled in production to ensure that a development instance won't interfer with a production instance
CSGO_API_ENABLED = True # FIXME: set back to False

