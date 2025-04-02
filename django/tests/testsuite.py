import logging
import os
import pathlib
import urllib.request
from unittest.mock import patch

import cs2_client
import matplotlib.image as mpimg
import numpy as np

file_dir_path = pathlib.Path(__file__).parent
demo_path = file_dir_path / 'data/demos'
demo_path.mkdir(parents=True, exist_ok=True)

# Disable all logging except for errors
logging.disable(logging.ERROR)


def get_demo_path(demo_id):
    demo_filename = f'{demo_id}.dem.bz2'
    demo_filepath = demo_path / demo_filename

    if not demo_filepath.is_file():
        urllib.request.urlretrieve(f'http://evoid.de/cs2pb-test-data/demos/{demo_filename}', str(demo_filepath))

    return str(demo_filepath)


class fake_api:

    _original_api = None

    @staticmethod
    def fetch_profile(steamid):
        return dict(
            personaname = f'name-of-{steamid}',
            avatar = f'https://{steamid}/avatar-s.url',
            avatarmedium = f'https://{steamid}/avatar-m.url',
            avatarfull = f'https://{steamid}/avatar-l.url',
        )

    @staticmethod
    def patch(func):
        @patch.object(cs2_client, 'api', fake_api)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper


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
