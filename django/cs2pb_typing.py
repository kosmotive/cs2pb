import sys

if sys.version_info < (3, 11):
    from typing_extensions import *  # noqa: F403, F401
else:
    from typing import *  # noqa: F403, F401
