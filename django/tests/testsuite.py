import functools
import importlib
import logging
import os
import pathlib
import urllib.request

import matplotlib.image as mpimg
import numpy as np

file_dir_path = pathlib.Path(__file__).parent
demo_path = file_dir_path / 'data/demos'
demo_path.mkdir(parents=True, exist_ok=True)

# Disable all loging except for errors
logging.disable(logging.ERROR)


def get_demo_path(demo_id):
    demo_filename = f'{demo_id}.dem.bz2'
    demo_filepath = demo_path / demo_filename

    if not demo_filepath.is_file():
        urllib.request.urlretrieve(f'http://evoid.de/cs2pb-test-data/demos/{demo_filename}', str(demo_filepath))

    return str(demo_filepath)


class _fake_api:

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
            setattr(m, 'api', _fake_api)

    @staticmethod
    def restore(*modules):
        from cs2_client import api
        for module_name in modules:
            m = importlib.import_module(module_name)
            setattr(m, 'api', api)


def fake_api():
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            _fake_api.inject('cs2_client')
            try:
                return func(*args, **kwargs)
            finally:
                _fake_api.restore('cs2_client')
        return wrapper
    return decorator


def assert_image_almost_equal(testcase, test_id, actual, expected, delta = 0.1):
    if not isinstance(actual, np.ndarray):
        actual = mpimg.imread(actual, format = 'png')
    try:
        if not isinstance(expected, np.ndarray):
            expected = mpimg.imread(expected)
        testcase.assertAlmostEqual(np.linalg.norm(actual - expected), 0, delta = delta)
    except:  # noqa: E722
        os.makedirs('tests/data/failed.actual', exist_ok = True)
        mpimg.imsave(f'tests/data/failed.actual/{test_id}.png', actual)
        raise
