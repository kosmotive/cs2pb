import importlib
import pathlib
import urllib.request


file_dir_path = pathlib.Path(__file__).parent
demo_path = file_dir_path / 'data/demos'
demo_path.mkdir(parents=True, exist_ok=True)


def get_demo_path(demo_id):
    demo_filename = f'{demo_id}.dem.bz2'
    demo_filepath = demo_path / demo_filename

    if not demo_filepath.is_file():
        urllib.request.urlretrieve(f'http://evoid.de/cs2pb-test-data/demos/{demo_filename}', str(demo_filepath))

    return str(demo_filepath)


class fake_api:

    profiles = {
        '1234567890': dict(
            personaname = 'steamname',
            avatar = 'https://avatar-s.url',
            avatarmedium = 'https://avatar-m.url',
            avatarfull = 'https://avatar-l.url',
        )
    }

    @staticmethod
    def fetch_profile(steamid):
        return fake_api.profiles[steamid]

    @staticmethod
    def inject(*modules):
        for module_name in modules:
            m = importlib.import_module(module_name)
            setattr(m, 'api', fake_api)

    @staticmethod
    def restore(*modules):
        from api import api
        for module_name in modules:
            m = importlib.import_module(module_name)
            setattr(m, 'api', api)

