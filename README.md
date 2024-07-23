# CS2PB

[![Run test-suite](https://github.com/kodikit/cs2pb/actions/workflows/django-tests.yaml/badge.svg)](https://github.com/kodikit/cs2pb/actions/workflows/django-tests.yaml)
[![Check settings](https://github.com/kodikit/cs2pb/actions/workflows/check-settings.yaml/badge.svg)](https://github.com/kodikit/cs2pb/actions/workflows/check-settings.yaml)

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

Set up the environment variables listed below!

Bootstrap CS2PB:
```
sh bootstrap.sh
```
Note that this requires access to the private repository `kodikit/cs2pb-bootstrap`, which you might not have access to.

If you don't have access to that repository, you will have to bootstrap manually:
```
cd django
python manage.py migrate
python initialize.py --help
```

## Environment variables

`CS2PB_ADMIN_MAIL_ADDRESS`: The mail address to send notifications to, when important failures occur which might require manual intervention (e.g., failure of the Steam API, or parsing demo files).

`CS2PB_STEAM_API_KEY`: A valid key for accessing the Steam API.

## Web links

- Badge designer: <https://badge.design>
