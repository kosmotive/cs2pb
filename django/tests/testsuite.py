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

    @staticmethod
    def fetch_profile(steamid):
        return dict(
            personaname = f'name-of-{steamid}',
            avatar = f'https://{steamid}/avatar-s.url',
            avatarmedium = f'https://{steamid}/avatar-m.url',
            avatarfull = f'https://{steamid}/avatar-l.url',
        )

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

