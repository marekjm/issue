import os

import issue


def get_path():
    return os.path.join(issue.util.get_repository_path(), 'log', 'shortlog.json')
