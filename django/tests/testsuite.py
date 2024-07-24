import pathlib
import urllib.request


file_dir_path = pathlib.Path(__file__).parent
demo_path = file_dir_path / 'data/demos'


def get_demo_path(demo_id):
    demo_filename = f'{demo_id}.dem.bz2'
    demo_filepath = demo_path / demo_filename

    if not demo_filepath.is_file():
        urllib.request.urlretrieve(f'http://evoid.de/cs2pb-test-data/demos/{demo_filename}', str(demo_filepath))

    return str(demo_filepath)
