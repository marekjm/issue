import datetime
import os

import issue


ISSUE_HIDDEN_DIRECTORY = '.issue'

_ISSUE_REPOSITORY_PATH = None


def first(seq):
    return seq[0]


def get_repository_path() -> str:
    global _ISSUE_REPOSITORY_PATH
    if _ISSUE_REPOSITORY_PATH is None:
        repository_path = os.getcwd()
        while not os.path.isdir(os.path.join(repository_path, ISSUE_HIDDEN_DIRECTORY)) and repository_path != '/':
            repository_path = first(os.path.split(repository_path))
        repository_path = os.path.join(repository_path, ISSUE_HIDDEN_DIRECTORY)
        if not os.path.isdir(repository_path):
            raise issue.exceptions.RepositoryNotFound()
        _ISSUE_REPOSITORY_PATH = repository_path
    return _ISSUE_REPOSITORY_PATH


def timestamp(dt: datetime.datetime = None) -> float:
    return (dt or datetime.datetime.now()).timestamp()
