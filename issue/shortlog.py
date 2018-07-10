import datetime
import json
import os
import typing

import issue


EVENTS_LOG_SIZE_DEFAULT = 80

EVENT_TYPE_SHOW = 'show'
EVENT_TYPE_SLUG = 'slug'
EVENT_TYPE_COMMENT = 'comment'
EVENT_TYPE_OPEN = 'open'
EVENT_TYPE_CLOSE = 'close'
EVENT_TYPE_TAGGED = 'tagged'
EVENT_TYPE_CHAINED_TO = 'chained_to'

# Lower is more important.
EVENTS_LOG_EVENT_WEIGHTS = {
    EVENT_TYPE_SHOW: 10,
    EVENT_TYPE_SLUG: 0,
    EVENT_TYPE_COMMENT: 7,
    EVENT_TYPE_OPEN: 0,
    EVENT_TYPE_CLOSE: 0,
    EVENT_TYPE_TAGGED: 8,
    EVENT_TYPE_CHAINED_TO: 5,
}


def read() -> typing.List:
    events_log_path = issue.util.paths.get_shortlog_path()
    events_log = []
    if os.path.isfile(events_log_path):
        with open(events_log_path) as ifstream:
            try:
                events_log = json.loads(ifstream.read())
            except json.decoder.JSONDecodeError:
                print('{}: failed to decode shortlog'.format(colorise(COLOR_ERROR, 'error')))
    return events_log


def write(events_log: typing.List) -> None:
    events_log_size = issue.config.getConfig().get('events_log_size', EVENTS_LOG_SIZE_DEFAULT)
    dumped = json.dumps(events_log[-events_log_size:])
    with open(issue.util.paths.get_shortlog_path(), 'w') as ofstream:
        ofstream.write(dumped)


def timestamp(dt=None):
    return (dt or datetime.datetime.now()).timestamp()

def append_event(issue_uid: str, event_type: str, parameters: typing.Dict = {}) -> None:
    events_log = issue.shortlog.read()
    content = {
        'issue_uid': issue_uid,
        'timestamp': timestamp(),
        'event': event_type,
        'parameters': parameters,
    }
    if events_log and (events_log[-1].get('event') == content.get('event') and events_log[-1].get('issue_uid') == 'issue_uid'):
        return
    events_log.append(content)
    issue.shortlog.write(events_log)


def append_event_open(issue_uid: str, message: str) -> None:
    issue.shortlog.append_event(issue_uid = issue_uid, event_type = EVENT_TYPE_OPEN, parameters = {
        'message': message,
    })

def append_event_show(issue_uid):
    issue.shortlog.append_event(issue_uid = issue_uid, event_type =  EVENT_TYPE_SHOW)

def append_event_tagged(issue_uid: str, tags: typing.List) -> None:
    issue.shortlog.append_event(issue_uid = issue_uid, event_type = EVENT_TYPE_TAGGED, parameters = {
        'tags': tags,
    })

def append_event_chained_to(issue_uid: str, chained_to_these_issues: typing.List) -> None:
    issue.shortlog.append_event(issue_uid = issue_uid, event_type = EVENT_TYPE_CHAINED_TO, parameters = {
        'chained_to': chained_to_these_issues,
    })

def append_event_close(issue_uid: str) -> None:
    issue.shortlog.append_event(issue_uid = issue_uid, event_type = EVENT_TYPE_CLOSE)

def append_event_slug(issue_uid: str, slug: str) -> None:
    issue.shortlog.append_event(issue_uid = issue_uid, event_type = EVENT_TYPE_SLUG, parameters = {
        'slug': slug,
    })


def sort(events_log):
    return sorted(events_log, key = lambda each: each['timestamp'], reverse = True)


def _bug_event_without_assigned_weight(event):
    print('{}: {}: event {} does not have a weight assigned'.format(colorise(COLOR_WARNING, 'warning'), colorise(COLOR_ERROR, 'bug'), colorise_repr(COLOR_LABEL, event['event'])))

def squash_events_log_aggressive_1(events_log):
    """Aggressive-squash-1 assumes that basic squashing has
    already been performed.
    """
    if len(events_log) < 2:
        return events_log
    squashed_events_log = [events_log[0]]
    for event in events_log[1:]:
        if event['issue_uid'] == squashed_events_log[-1]['issue_uid']:
            last_event_action = EVENTS_LOG_EVENT_WEIGHTS.get(squashed_events_log[-1]['event'])
            this_event_action = EVENTS_LOG_EVENT_WEIGHTS.get(event['event'])

            if last_event_action is None:
                _bug_event_without_assigned_weight(squashed_events_log[-1])
            if this_event_action is None:
                _bug_event_without_assigned_weight(event)
            if last_event_action is None or this_event_action is None:
                # zero out the comparison when an event does not have a weight assigned
                last_event_action, this_event_action = 0, 0

            if last_event_action > this_event_action:
                squashed_events_log.pop()
            elif last_event_action < this_event_action:
                continue
            else:
                pass
        squashed_events_log.append(event)
    return squashed_events_log

def rfind_if(seq, pred):
    index = len(seq)-1
    while index > -1:
        if pred(seq[index]):
            break
        index -= 1
    return index

def squash_events_log_aggressive_2(events_log):
    """Aggressive-squash-2 assumes that basic squashing, and
    aggressive-squashing-1 have already been performed.
    """
    if len(events_log) < 2:
        return events_log
    squashed_events_log = [events_log[0]]
    for event in events_log[1:]:
        this_event_action = EVENTS_LOG_EVENT_WEIGHTS.get(event['event'])
        index_of_last_event_for_the_same_issue = rfind_if(squashed_events_log, lambda e: e['issue_uid'] ==
                event['issue_uid'])
        if index_of_last_event_for_the_same_issue > -1:
            last_event_action = EVENTS_LOG_EVENT_WEIGHTS.get(squashed_events_log[index_of_last_event_for_the_same_issue]['event'])

            if last_event_action is None:
                _bug_event_without_assigned_weight(squashed_events_log[-1])
            if this_event_action is None:
                _bug_event_without_assigned_weight(event)
            if last_event_action is None or this_event_action is None:
                # zero out the comparison when an event does not have a weight assigned
                last_event_action, this_event_action = 0, 0

            if last_event_action > this_event_action:
                squashed_events_log.pop()
            elif last_event_action < this_event_action:
                continue
            else:
                pass
        squashed_events_log.append(event)
    return squashed_events_log

def squash_events_log(events_log, aggressive=0):
    if len(events_log) < 2:
        return events_log
    squashed_events_log = [events_log[0]]
    for event in events_log[1:]:
        if event['issue_uid'] == squashed_events_log[-1]['issue_uid'] and event['event'] == squashed_events_log[-1]['event']:
            continue
        squashed_events_log.append(event)
    if aggressive > 0:
        squashed_events_log = squash_events_log_aggressive_1(squashed_events_log)
    if aggressive > 1:
        squashed_events_log = squash_events_log_aggressive_2(squashed_events_log)
    return sort(squashed_events_log)
