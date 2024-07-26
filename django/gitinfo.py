from datetime import datetime
import pathlib
import re

import git


repo_dir = pathlib.Path(__file__).parent.parent
base_repo_url = 'https://github.com/kodikit/cs2pb'

changelog_exclude = [
    'ef37efb000f082b1a18e9fd4c1e49344eb6d4f78',
    'e7c3037db900d619187186ffa6c9865196c562cc',
]

changelog_substitute_message = {
    'f229070697d182f1aa55b2594bf3e7f0cf69bd34': 'Fix Discord name field in settings/signup',
}


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
        if c.hexsha in changelog_exclude: continue
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
            entry['message'] = changelog_substitute_message.get(c.hexsha, entry['message'])
            changelog.append(entry | dict(sha = c.hexsha, date = get_fmt_date(c)))

    return changelog


changelog = get_changelog()
