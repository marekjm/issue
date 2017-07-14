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


def append_event(issue_id: str, event: typing.Dict, noise: int = 0) -> None:
    event['issue'] = issue_id
    event['timestamp'] = issue.util.timestamp()
    event['noise'] = noise
    shortlog = read()
    if shortlog and shortlog[-1].get('event') == event.get('event') and shortlog[-1].get('issue') == issue_id:
        return
    shortlog.append(event)
    write(shortlog)
