import shutil
import os

import issue


def make_dir_if_not_exists(path):
    if not os.path.isdir(path):
        os.mkdir(path)

def init(where: str, status: str, force: bool = False, up: bool = False):
    repository_path = issue.util.paths.get_repository_path(where = where)

    if force and os.path.isdir(repository_path):
        shutil.rmtree(repository_path)
    if not up and os.path.isdir(repository_path):
        raise issue.exceptions.RepositoryExists(repository_path)

    make_dir_if_not_exists(repository_path)
    make_dir_if_not_exists(issue.util.paths.tmp_path())
    make_dir_if_not_exists(issue.util.paths.objects_path())
    make_dir_if_not_exists(issue.util.paths.issues_path())
    make_dir_if_not_exists(issue.util.paths.tags_path())
    make_dir_if_not_exists(issue.util.paths.releases_path())

    with open(issue.util.paths.status_path(), 'w') as ofstream:
        ofstream.write(status)

    return os.path.abspath(repository_path)
