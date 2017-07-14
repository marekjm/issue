import json
import os
import typing

import issue


def get_path() -> str:
    return os.path.join(issue.util.get_repository_path(), 'log', 'shortlog.json')


def read() -> typing.List:
    pth = get_path()
    if not os.path.isfile(pth):
        return []
    shortlog = []
    with open(pth) as ifstream:
        shortlog = json.loads(ifstream.read())
    return shortlog


def write(shortlog: typing.List) -> None:
    pth = get_path()
    if not os.path.isdir(issue.util.first(os.path.split(pth))):
        os.makedirs(issue.util.first(os.path.split(pth)))
    with open(pth) as ofstream:
        ofstream.write(json.dumps(shortlog))
