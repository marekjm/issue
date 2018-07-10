import datetime
import os

import issue


ISSUE_HIDDEN_DIRECTORY = '.issue'

_ISSUE_REPOSITORY_PATH = None


def get_repository_path(where: str = None, safe: bool = False) -> str:
    global _ISSUE_REPOSITORY_PATH
    if where is not None:
        return os.path.join(where, ISSUE_HIDDEN_DIRECTORY)

    if _ISSUE_REPOSITORY_PATH is None:
        repository_path = os.getcwd()
        isdir = lambda d: os.path.isdir(os.path.join(d, ISSUE_HIDDEN_DIRECTORY))
        while not isdir(repository_path) and repository_path != '/':
            repository_path = issue.util.misc.first(os.path.split(repository_path))
        repository_path = os.path.join(repository_path, ISSUE_HIDDEN_DIRECTORY)
        exists = os.path.isdir(repository_path)
        if (not exists) and (not safe):
            raise issue.exceptions.RepositoryNotFound()
        if exists:
            _ISSUE_REPOSITORY_PATH = repository_path
    return _ISSUE_REPOSITORY_PATH


def objects_path() -> str:
    return os.path.join(get_repository_path(), 'objects')


def issues_path() -> str:
    return os.path.join(objects_path(), 'issues')


def comments_path_of(issue_id: str) -> str:
    return os.path.join(issues_path(), issue_id[:2], issue_id, 'comments')


def diffs_path_of(issue_id: str) -> str:
    return os.path.join(issues_path(), issue_id[:2], issue_id, 'diff')


def indexed_path_of(issue_id: str) -> str:
    return os.path.join(issues_path(), issue_id[:2], '{0}.json'.format(issue_id))


def get_shortlog_path() -> str:
    return os.path.join(issue.util.paths.get_repository_path(), 'log', 'events_log.json')


def last_issue_path() -> str:
    return os.path.join(get_repository_path(), 'last')


def tmp_path() -> str:
    return os.path.join(get_repository_path(), 'tmp')


def tags_path() -> str:
    return os.path.join(objects_path(), 'tags')


def releases_path() -> str:
    return os.path.join(objects_path(), 'releases')


def pack_path() -> str:
    return os.path.join(get_repository_path(), 'pack.json')


def remote_pack_path() -> str:
    return os.path.join(get_repository_path(), 'remote_pack.json')


def status_path() -> str:
    return os.path.join(get_repository_path(), 'status')
