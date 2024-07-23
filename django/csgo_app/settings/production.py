import os

from csgo_app.settings.common import *


# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ['SECRET_KEY']

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

ALLOWED_HOSTS = ['cs2pb.evoid.de']

STATIC_ROOT = BASE_DIR / 'static-deployed'

LOG_PATH = BASE_DIR / 'logs'

LOGGING['formatters']['verbose'] = {
    'format': '%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s',
}

LOGGING['handlers']['errors'] = {
    'class': 'logging.handlers.TimedRotatingFileHandler',
    'filename': LOG_PATH / 'errors.log',
    'formatter': 'verbose',
    'when': 'D',
    'level': 'ERROR',
}

LOGGING['handlers']['django'] = {
    'class': 'logging.handlers.TimedRotatingFileHandler',
    'filename': LOG_PATH / 'django.log',
    'formatter': 'verbose',
    'when': 'D',
}

LOGGING['handlers']['discord'] = {
    'class': 'logging.handlers.TimedRotatingFileHandler',
    'filename': LOG_PATH / 'discord.log',
    'formatter': 'verbose',
    'when': 'D',
}

LOGGING['handlers']['api'] = {
    'class': 'logging.handlers.TimedRotatingFileHandler',
    'filename': LOG_PATH / 'api.log',
    'formatter': 'verbose',
    'when': 'D',
}

LOGGING['handlers']['ratelimit'] = {
    'class': 'logging.handlers.TimedRotatingFileHandler',
    'filename': LOG_PATH / 'ratelimit.log',
    'formatter': 'verbose',
    'when': 'D',
}

LOGGING['handlers']['stats'] = {
    'class': 'logging.handlers.TimedRotatingFileHandler',
    'filename': LOG_PATH / 'stats.log',
    'formatter': 'verbose',
    'when': 'D',
}

LOGGING['handlers']['accounts'] = {
    'class': 'logging.handlers.TimedRotatingFileHandler',
    'filename': LOG_PATH / 'accounts.log',
    'formatter': 'verbose',
    'when': 'D',
}

LOGGING['loggers']['django'] = {
    'handlers': ['django', 'errors'],
    'level': 'WARNING',
}

LOGGING['loggers']['discord'] = {
    'handlers': ['discord', 'errors'],
    'level': 'INFO',
}

LOGGING['loggers']['discord.client'] = {
    'handlers': ['discord', 'errors'],
    'level': 'INFO',
}

LOGGING['loggers']['discord.gateway'] = {
    'handlers': ['discord', 'errors'],
    'level': 'INFO',
}

LOGGING['loggers']['discord.http'] = {
    'handlers': ['discord', 'errors'],
    'level': 'INFO',
}

LOGGING['loggers']['discordbot.bot'] = {
    'handlers': ['discord', 'errors'],
    'level': 'DEBUG',
}

LOGGING['loggers']['discordbot.models'] = {
    'handlers': ['discord', 'errors'],
    'level': 'INFO',
}

LOGGING['loggers']['api'] = {
    'handlers': ['api', 'errors'],
    'level': 'DEBUG',
}

LOGGING['loggers']['ratelimit'] = {
    'handlers': ['ratelimit', 'errors'],
    'level': 'DEBUG',
}

LOGGING['loggers']['stats.models'] = {
    'handlers': ['stats', 'errors'],
    'level': 'INFO',
}

LOGGING['loggers']['stats.views'] = {
    'handlers': ['stats', 'errors'],
    'level': 'INFO',
}

LOGGING['loggers']['stats.updater'] = {
    'handlers': ['stats', 'errors'],
    'level': 'INFO',
}

LOGGING['loggers']['stats.plots'] = {
    'handlers': ['stats', 'errors'],
    'level': 'INFO',
}

LOGGING['loggers']['stats.features'] = {
    'handlers': ['stats', 'errors'],
    'level': 'INFO',
}

LOGGING['loggers']['accounts.models'] = {
    'handlers': ['accounts', 'errors'],
    'level': 'INFO',
}

