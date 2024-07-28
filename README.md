# CS2PB

[![Run test-suite](https://github.com/kodikit/cs2pb/actions/workflows/django-tests.yaml/badge.svg)](https://github.com/kodikit/cs2pb/actions/workflows/django-tests.yaml)
[![Check settings](https://github.com/kodikit/cs2pb/actions/workflows/check-settings.yaml/badge.svg)](https://github.com/kodikit/cs2pb/actions/workflows/check-settings.yaml)

<img width="894" src="https://github.com/user-attachments/assets/b25b17c1-6636-4a01-9f52-4c761c2a033f">

## Features

- Squad overview web page
- Match history web page
- Discord integration
- Player of the Week challenge
- Match-wise badges (quad-kill, ace)
- Session-wise badged (surpass yourself, rising star)

## Installation

Create a virtual environment for Python:
```
python -m venv env
```

Activate the environment:
```
source env/bin/activate
```

Install the dependencies:
```
pip install -r requirements.txt
```

### Environment variables

The following environment variables are required:

- `CS2PB_ADMIN_MAIL_ADDRESS`: The mail address to send notifications to, when important failures occur which might require manual intervention (e.g., failure of the Steam API, or parsing demo files).

- `CS2PB_STEAM_API_KEY`: A valid key for accessing the Steam API.

- `CS2PB_DISCORD_ENABLED`: Set to `1` to enable the Discord bot.

### Bootstrapping

To bootstrap CS2PB easily, there is a fully automated process:
```
sh bootstrap.sh
```
Note that this requires access to the private repository [kodikit/cs2pb-bootstrap](https://github.com/kodikit/cs2pb-bootstrap), which you might not have access to. If you don't have access to that repository, you will have to bootstrap manually. To do that, create the file `django/discordbot/settings.json` (see `django/discordbot/settings.json.skeleton` for an example), and then run:
```
cd django
python manage.py migrate
python initialize.py --help
```

## Web links

- Badge designer: <https://badge.design>
