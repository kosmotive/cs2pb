import pathlib

import git


repo_dir = pathlib.Path(__file__).parent.parent


def get_head_info():
    r = git.Repo(str(repo_dir))
    sha = r.head.object.hexsha
    date = r.head.object.committed_date
    return dict(sha = sha, date = date)
