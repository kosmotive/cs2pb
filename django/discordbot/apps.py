from django.apps import AppConfig

import threading


class DiscordbotConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'discordbot'

    def ready(self):
        self.bot_thread = threading.Thread(target=run_bot, daemon=True)
        self.bot_thread.start()


def run_bot():
    from discordbot.bot import bot

