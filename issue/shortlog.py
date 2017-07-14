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
    with open(pth, 'w') as ofstream:
        ofstream.write(json.dumps(shortlog))


def append_event(event_type: str, content: typing.Dict, noise: int = 0) -> None:
    event = {
        'event': event_type,
        'timestamp': issue.util.timestamp(),
        'noise': noise,
        'content': content,
    }
    shortlog = read()
    shortlog.append(event)
    write(shortlog)


def append_event_issue_opened(issue_id: str, message: str) -> None:
    append_event(issue_id, 'issue-open', {
        'issue': issue_id,
        'message': message,
    })


def append_event_issue_tagged(issue_id: str, tags: typing.List) -> None:
    append_event(issue_id, 'issue-tagged', {
        'issue': issue_id,
        'tags': tags,
    })


def append_event_issue_milestoned(issue_id: str, milestones: typing.List) -> None:
    append_event(issue_id, 'issue-milestoned', {
        'issue': issue_id,
        'milestones': milestones,
    })


def append_event_issue_chained_to(issue_id: str, chained_to_these_issues: typing.List) -> None:
    append_event(issue_id, 'issue-chained-to', {
        'issue': issue_id,
        'chained_to': chained_to_these_issues,
    })
