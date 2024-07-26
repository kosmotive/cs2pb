from datetime import datetime
import pathlib
import re

import git


repo_dir = pathlib.Path(__file__).parent.parent
base_repo_url = 'https://github.com/kodikit/cs2pb'


def get_fmt_date(commit):
    return datetime.utcfromtimestamp(
        commit.committed_date
    ).strftime('%Y-%m-%d')


def get_head_info():
    r = git.Repo(str(repo_dir))
    sha = r.head.object.hexsha
    date = get_fmt_date(r.head.object)
    return dict(sha = sha, date = date)


def get_changelog():
    r = git.Repo(str(repo_dir))
    merge_pr_pattern = re.compile(r'^Merge pull request #([0-9]+) from.+')
    hotfix_pattern = re.compile(r'^hotfix:(.*)', re.IGNORECASE)
    changelog = list()
    for c in r.iter_commits():
        entry = None
        
        m = merge_pr_pattern.match(c.message)
        if m is not None and '[no changelog]' not in c.message and '[no-changelog]' not in c.message:
            pr_id = int(m.group(1))
            entry = dict(
                message = '\n'.join(c.message.split('\n')[1:]).strip(),
                url = base_repo_url + '/pull/' + str(pr_id),
            )

        m = hotfix_pattern.match(c.message)
        if m is not None:
            entry = dict(
                message = 'Hotfix: ' + m.group(1).split('\n')[0].strip(),
                url = base_repo_url + '/commits/' + c.hexsha,
            )

        if entry is not None:
            changelog.append(entry | dict(sha = c.hexsha, date = get_fmt_date(c)))

    return changelog


changelog = get_changelog()
