import os

import issue


def ls():
    return os.listdir(issue.util.paths.tags_path())
