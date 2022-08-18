#!/usr/bin/env python3

import datetime
import json
import os
import random
import re
import shutil
import subprocess
import sys

import unidecode
try:
    import colored
except ImportError:
    colored = None

import clap

import issue


filename_ui = os.path.expanduser('~/.local/share/issue/ui.json')

model = {}
with open(filename_ui, 'r') as ifstream: model = json.loads(ifstream.read())

args = list(clap.formatter.Formatter(sys.argv[1:]).format())

command = clap.builder.Builder(model).insertHelpCommand().build().get()
parser = clap.parser.Parser(command).feed(args)
checker = clap.checker.RedChecker(parser)


try:
    err = None
    checker.check()
    fail = False
except clap.errors.MissingArgumentError as e:
    print('missing argument for option: {0}'.format(e))
    fail = True
except clap.errors.UnrecognizedOptionError as e:
    print('unrecognized option found: {0}'.format(e))
    fail = True
except clap.errors.ConflictingOptionsError as e:
    print('conflicting options found: {0}'.format(e))
    fail = True
except clap.errors.RequiredOptionNotFoundError as e:
    fail = True
    print('required option not found: {0}'.format(e))
except clap.errors.InvalidOperandRangeError as e:
    print('invalid number of operands: {0}'.format(e))
    fail = True
except clap.errors.UIDesignError as e:
    print('UI has design error: {0}'.format(e))
    fail = True
except clap.errors.AmbiguousCommandError as e:
    name, candidates = str(e).split(': ')
    print("ambiguous shortened command name: '{0}', candidates are: {1}".format(name, candidates))
    print("note: if this is a false positive use '--' operand separator")
    fail = True
finally:
    if fail: exit(1)
    ui = parser.parse().ui().finalise()


if '--version' in ui:
    fmt = 'issue version {version}'
    if '--verbose' in ui:
        fmt += ' ({commit})'
    print(fmt.format(
        version = issue.__version__,
        commit = issue.__commit__,
    ))
    exit(0)
if clap.helper.HelpRunner(ui=ui, program=sys.argv[0]).adjust(options=['-h', '--help']).run().displayed():
    exit(0)


LS_KEYWORD_MATCH_THRESHOLD = 1


# Colorisation utilities.
def colorise_if_possible(color, s):
    if colored is None:
        return s
    return (colored.fg(color) + s + colored.attr('reset'))

def colorise(color, s):
    return colorise_if_possible(color, s)

def colorise_repr(color, s):
    s = repr(s)
    return s[0] + colorise_if_possible(color, s[1:-1]) + s[0]

COLOR_ERROR = 'red'
COLOR_FATAL = 'red'
COLOR_WARNING = 'red'
COLOR_NOTE = 'blue'
COLOR_HASH = 'yellow'
COLOR_BRANCH_NAME = 'white'
COLOR_DATETIME = 'cyan'


# remote-related utility functions
def getRemotes():
    remotes = {}
    remotes_path = os.path.join(issue.util.paths.get_repository_path(), 'remotes.json')
    if os.path.isfile(remotes_path):
        with open(remotes_path) as ifstream:
            remotes = json.loads(ifstream.read())
    return remotes

def saveRemotes(remotes):
    remotes_path = os.path.join(issue.util.paths.get_repository_path(), 'remotes.json')
    with open(remotes_path, 'w') as ofstream:
        ofstream.write(json.dumps(remotes))


# misc utility functions
def expandIssueUID(issue_sha1_part):
    if issue_sha1_part == '-':
        return getLastIssue()
    issue_sha1 = []
    issues = issue.util.issues.ls()
    for i_sha1 in issues:
        if i_sha1.startswith(issue_sha1_part): issue_sha1.append(i_sha1)
    if len(issue_sha1) == 0:
        raise issue.exceptions.IssueUIDNotMatched(issue_sha1_part)
    if len(issue_sha1) > 1:
        raise issue.exceptions.IssueUIDAmbiguous(issue_sha1_part)
    return issue_sha1[0]

def expand_issue_uid_or_exir(issue_uid_part):
    try:
        return expandIssueUID(issue_uid_part)
    except issue.exceptions.IssueUIDAmbiguous:
        print('{0}: issue uid {1} is ambiguous'.format(
            colorise(COLOR_ERROR, 'error'),
            colorise_repr(COLOR_HASH, issue_uid_part),
        ))
        exit(1)
    except issue.exceptions.IssueUIDNotMatched:
        print('{0}: issue uid {1} did not match anything'.format(
            colorise(COLOR_ERROR, 'error'),
            colorise_repr(COLOR_HASH, issue_uid_part),
        ))
        exit(1)

def runShell(*command):
    p = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output, error = p.communicate()
    output = output.decode('utf-8').strip()
    error = error.decode('utf-8').strip()
    exit_code = p.wait()
    return (exit_code, output, error)

def shortestUnique(lst):
    if not lst:
        return 0
    if len(lst) == 1:
        return 1

    lst.sort()

    base_n = len(lst[0])
    n = (base_n // 2)

    done = False
    while 1:
        not_same = (len(lst) != len(set([i[:n] for i in lst])))
        if not_same and n == (base_n-1):
            n = base_n
            break
        if not_same:
            n += ((base_n - n) // 2)
            continue
        base_n = n
        n = (base_n // 2)
    return n

def shortest_unique_prefix(seq = None):
    if seq is None:
        seq = issue.util.issues.ls()
    return shortestUnique(seq)

def listIssuesUsingShortestPossibleUIDs(with_full=False):
    list_of_issues = issue.util.issues.ls()
    n = shortestUnique(list_of_issues)
    if with_full:
        final_list_of_issues = [(i[:n], i) for i in list_of_issues]
    else:
        final_list_of_issues = [i[:n] for i in list_of_issues]
    return final_list_of_issues

def markLastIssue(issue_sha1):
    with open(issue.util.paths.last_issue_path(), 'w') as ofstream:
        ofstream.write(issue_sha1)

def getLastIssue():
    last_issue_sha1 = ''
    if os.path.isfile(issue.util.paths.last_issue_path()):
        with open(issue.util.paths.last_issue_path()) as ifstream:
            last_issue_sha1 = ifstream.read()
    return last_issue_sha1

def get_time_delta_arguments(delta_mods):
    time_delta = {}
    time_patterns = [
        re.compile('^(\d+)(minutes?)$'),
        re.compile('^(\d+)(hours?)$'),
        re.compile('^(\d+)(days?)$'),
        re.compile('^(\d+)(weeks?)$'),
    ]
    for dm in delta_mods:
        found_any = False

        for p in time_patterns:
            pm = p.match(dm)
            if pm is not None:
                mod = pm.group(2)

                # Allow both "1week" and "2weeks" forms.
                if mod[-1] != 's':
                    mod += 's'

                time_delta[mod] = int(pm.group(1))
                found_any = True

        if not found_any:
            raise issue.exceptions.Invalid_time_delta_specification(delta_mods)
    return time_delta

def transfer_objects_between(source, destination):
    rsync_argv = [ 'rsync', ]

    global ui
    if '--dry-run' in ui:
        rsync_argv.append('--dry-run')
    if '--quiet' not in ui:
        rsync_argv.extend([
            '--stats',
            '--human-readable',
        ])
    else:
        rsync_argv.append('--quiet')
    if '--verbose' in ui:
        rsync_argv.extend([
            '--verbose',
            '--progress',
        ])

    rsync_options = (
        '--recursive',
        '--checksum',
        '--preallocate',
        '--compress',
        '--prune-empty-dirs',
    )
    rsync_argv.extend(rsync_options)

    rsync_filter_rules = (
        'include /objects/issues/*/*/diff/*.json',
        'exclude /tmp/',
        'exclude /log/',
        'include */',
        'exclude *',
    )
    for rule in rsync_filter_rules:
        rsync_argv.append('--filter')
        rsync_argv.append(rule)

    rsync_argv.append(f'{source}/')
    rsync_argv.append(f'{destination}/')

    return subprocess.call(rsync_argv)

def pull_from_remote(remote_name, remote_url):
    if transfer_objects_between(remote_url, '.issue'):
        fmt = '{}: failed to pull some or all objects from remote {}\n'
        sys.stderr.write(fmt.format(
            colorise(COLOR_ERROR, 'error'),
            colorise_repr('white', remote_name),
        ))

def push_to_remote(remote_name, remote_url):
    if transfer_objects_between('.issue', remote_url):
        fmt = '{}: failed to push some or all objects to remote {}\n'
        sys.stderr.write(fmt.format(
            colorise(COLOR_ERROR, 'error'),
            colorise_repr('white', remote_name),
        ))

def timestamp(dt=None):
    return (dt or datetime.datetime.now()).timestamp()

def getMessage(template='', fmt={}, ignore='#'):
    editor = os.getenv('EDITOR', 'vi')
    message_path = os.path.join(issue.util.paths.get_repository_path(), 'message')
    if template and fmt:
        with open(os.path.expanduser('~/.local/share/issue/{0}'.format(template))) as ifstream:
            default_message_text = ifstream.read()
        with open(message_path, 'w') as ofstream:
            ofstream.write(default_message_text.format(**fmt))
    elif template and not fmt:
        shutil.copy(os.path.expanduser('~/.local/share/issue/{0}'.format(template)), message_path)
    os.system('{0} {1}'.format(editor, message_path))
    message = ''
    with open(message_path) as ifstream:
        message_lines = ifstream.readlines()
        message = ''.join([l for l in message_lines if not l.startswith(ignore)]).strip()
    return message


######################################################################
# LOG UTILITY FUNCTIONS
#
EVENT_TYPE_SHOW = 'show'
EVENT_TYPE_SLUG = 'slug'
EVENT_TYPE_COMMENT = 'comment'
EVENT_TYPE_CLOSE = 'close'

# Lower is more important.
EVENTS_LOG_EVENT_WEIGHTS = {
    EVENT_TYPE_SHOW: 10,
    EVENT_TYPE_SLUG: 0,
    EVENT_TYPE_COMMENT: 7,
    EVENT_TYPE_CLOSE: 0,
}

def display_events_log(events_log, head=None, tail=None):
    if head is not None:
        events_log = events_log[:head]
    if tail is not None:
        events_log = events_log[tail:]
    try:
        shortened_uids = dict(map(lambda each: (each[1], each[0],),
            listIssuesUsingShortestPossibleUIDs(with_full = True)))

        for event in events_log:
            event_name = event['event']
            event_parameters = event.get('parameters', {})
            event_description = ''
            if event_name == 'show':
                try:
                    event_description = issue.util.issues.getIssue(event['issue_uid']).get('message').splitlines()[0]
                except issue.exceptions.NotAnIssue:
                    # This happens when an issue was dropped.
                    pass
            elif event_name == 'slug':
                event_description = 'sluggified to {}'.format(colorise_repr(
                    COLOR_BRANCH_NAME,
                    event_parameters['slug'],
                ))
            elif event_name == 'comment':
                comment_lines = event_parameters['comment'].splitlines()
                event_description = '{}'.format(comment_lines[0].strip())
                if len(comment_lines) > 1:
                    event_description += ' (...)'
            elif event_name == 'open':
                event_description = event_parameters['message'].splitlines()[0]
            elif event_name == 'tagged':
                event_description = ', '.join(event_parameters['tags'])
            else:
                # if no special description formatting is provided, just display name of the event
                event_description = ''
            event_datetime = datetime.datetime.utcfromtimestamp(event.get('timestamp')).strftime('%Y-%m-%d %H:%M:%S')
            if event['issue_uid'] in shortened_uids:
                print('{issue_key} [{event_datetime}] {event_name}{event_description}'.format(
                    issue_key = colorise(COLOR_HASH, shortened_uids[event['issue_uid']]),
                    event_datetime = colorise(COLOR_DATETIME, event_datetime),
                    event_name = event_name,
                    event_description = (': ' * bool(event_description)) + event_description,
                ))
            else:
                n = list(shortened_uids.values())
                n = (len(n[0]) if n else 4)
                print('{issue_key} [{event_datetime}] {error_msg}: {event_name}{event_description}'.format(
                    issue_key = colorise(COLOR_HASH, event['issue_uid'][:n]),
                    event_datetime = colorise(COLOR_DATETIME, event_datetime),
                    event_name = event_name,
                    event_description = (': ' * bool(event_description)) + event_description,
                    error_msg = colorise(COLOR_ERROR, 'not an issue (dropped?)'),
                ))
    except BrokenPipeError as e:
        # just silence this
        # this exception is thrown when events_log is piped to head
        pass


######################################################################
# BACKEND FUNCTIONS
#
def get_release_path(release_name):
    return os.path.join(issue.util.paths.releases_path(), 'r', release_name)

def release_name_exists(release_name):
    return os.path.isdir(get_release_path(release_name))

def get_release_notes_path(release_name):
    return os.path.join(get_release_path(release_name), 'notes')

def store_next_release_pointer(release_name):
    with open(os.path.join(issue.util.paths.releases_path(), 'next'), 'w') as ofstream:
        ofstream.write(release_name)

def get_next_release_pointer():
    next_relese_pointer_path = os.path.join(issue.util.paths.releases_path(), 'next')
    if not os.path.isfile(next_relese_pointer_path):
        return ''
    with open(next_relese_pointer_path) as ifstream:
        return ifstream.read().strip()

def _store_release_diff_simple_named_action(release_name, action_name):
    repo_config = issue.config.getConfig()
    release_differences = [
        {
            'action': action_name,
            'author': {
                'author.email': repo_config['author.email'],
                'author.name': repo_config['author.name'],
            },
            'timestamp': timestamp(),
        },
    ]
    release_diff_sha1 = '{0}{1}{2}{3}'.format(repo_config['author.email'], repo_config['author.name'], timestamp(), random.random())
    release_diff_sha1 = issue.util.misc.create_hash(release_diff_sha1)
    release_diff_file_path = os.path.join(get_release_path(release_name), 'diff', '{0}.json'.format(release_diff_sha1))
    with open(release_diff_file_path, 'w') as ofstream:
        ofstream.write(json.dumps(release_differences))

def store_release_diff_open(release_name):
    _store_release_diff_simple_named_action(release_name, 'open')

def store_release_diff_close(release_name):
    _store_release_diff_simple_named_action(release_name, 'close')

def store_release_diff(release_name, action, params=None):
    repo_config = issue.config.getConfig()
    release_differences = [
        {
            'action': action,
            'author': {
                'author.email': repo_config['author.email'],
                'author.name': repo_config['author.name'],
            },
            'timestamp': timestamp(),
        },
    ]
    if params is not None:
        release_differences[0]['params'] = params
    release_diff_sha1 = '{0}{1}{2}{3}'.format(repo_config['author.email'], repo_config['author.name'], timestamp(), random.random())
    release_diff_sha1 = issue.util.misc.create_hash(release_diff_sha1)
    release_diff_file_path = os.path.join(get_release_path(release_name), 'diff', '{0}.json'.format(release_diff_sha1))
    with open(release_diff_file_path, 'w') as ofstream:
        ofstream.write(json.dumps(release_differences))

def get_release_diffs(release_name):
    release_diff_path = os.path.join(get_release_path(release_name), 'diff')
    release_diff_files = os.listdir(release_diff_path)
    release_diffs = []
    for p in release_diff_files:
        with open(os.path.join(release_diff_path, p)) as ifstream:
            release_diffs.extend(json.loads(ifstream.read()))
    return release_diffs


######################################################################
# LOGIC CODE
#
if '--nuke' in ui:
    repository_exists = os.path.isdir(issue.util.paths.get_repository_path())
    if not repository_exists and ui.get('--nuke') <= 1:
        print('fatal: cannot remove nonexistent repository')
        exit(1)
    if repository_exists:
        shutil.rmtree(issue.util.paths.get_repository_path())
    exit(0)

if '--where' in ui:
    print(issue.util.paths.get_repository_path())
    exit(0)


ui = ui.down() # go down a mode
operands = ui.operands()


def commandInit(ui):
    repository_where = issue.util.misc.first_or(ui.operands(), '.')
    initialised_where = issue.repository.init(
        where = repository_where,
        force = ('--force' in ui),
        up = ('--up' in ui),
    )
    if '--verbose' in ui:
        print('repository initialised in {0}'.format(initialised_where))

def commandOpen(ui):
    tags = ([l[0] for l in ui.get('--tag')] if '--tag' in ui else [])
    gathered_tags = issue.objects.tags.gather()
    for t in tags:
        if t not in gathered_tags[0]:
            print('fatal: tag "{0}" does not exist'.format(t))
            print('note: use "issue tag new {0}" to create it'.format(t))
            exit(1)

    milestones = ([m[0] for m in ui.get('--milestone')] if '--milestone' in ui else [])

    parent_uid = None
    if '--parent' in ui:
        try:
            parent_uid = expandIssueUID(ui.get('--parent'))
        except Exception as e:
            print('{error}: could not link issue identified by "{parent_uid}":'.format(
                colorise(COLOR_ERROR, 'error'),
                colorise(COLOR_HASH, parent_uid),
            ), e)
            exit(1)

    message_fmt = {
        'parent_message': '#',
    }
    if parent_uid is not None:
        formatted_parent_message = '#\n# Parent message:\n#\n'
        parent_message_lines = issue.util.issues.getIssue(parent_uid).get('message').splitlines()
        indented_parent_message_lines = ['    {}'.format(l) for l in parent_message_lines]
        formatted_parent_message += '\n'.join(map(lambda each: '#  {}'.format(each),
            indented_parent_message_lines,
        ))
        message_fmt['parent_message'] = formatted_parent_message
    message = (getMessage('issue_message', fmt = message_fmt) if len(operands) < 1 else operands[0])
    if not message:
        print('fatal: aborting due to empty message')
        exit(1)

    issue_sha1 = '{0}{1}{2}{3}{4}'.format(message, tags, milestones, parent_uid, random.random())
    issue_sha1 = issue.util.misc.create_hash(issue_sha1)

    repo_config = issue.config.getConfig()

    issue_group_path = os.path.join(issue.util.paths.issues_path(), issue_sha1[:2])
    if not os.path.isdir(issue_group_path):
        os.mkdir(issue_group_path)

    # make directories for issue-specific objects
    os.mkdir(os.path.join(issue_group_path, issue_sha1))
    os.mkdir(os.path.join(issue_group_path, issue_sha1, 'comments'))
    os.mkdir(os.path.join(issue_group_path, issue_sha1, 'diff'))

    issue_differences = [
        {
            'action': 'open',
            'author': {
                'author.email': repo_config['author.email'],
                'author.name': repo_config['author.name'],
            },
            'timestamp': timestamp(),
        },
        {
            'action': 'set-message',
            'params': {
                'text': message,
            },
            'author': {
                'author.email': repo_config['author.email'],
                'author.name': repo_config['author.name'],
            },
            'timestamp': timestamp(),
        },
        {
            'action': 'push-tags',
            'params': {
                'tags': tags,
            },
            'author': {
                'author.email': repo_config['author.email'],
                'author.name': repo_config['author.name'],
            },
            'timestamp': timestamp(),
        },
        {
            'action': 'push-milestones',
            'params': {
                'milestones': milestones,
            },
            'author': {
                'author.email': repo_config['author.email'],
                'author.name': repo_config['author.name'],
            },
            'timestamp': timestamp(),
        }
    ]

    repo_config = issue.config.getConfig()
    if 'project.tag' in repo_config:
        issue_differences.append({
            'action': 'push-tags',
            'params': {
                'tags': [repo_config['project.tag']],
            },
            'author': {
                'author.email': repo_config['author.email'],
                'author.name': repo_config['author.name'],
            },
            'timestamp': timestamp(),
        })
        issue_differences.append({
            'action': 'set-project-tag',
            'params': {
                'tag': repo_config['project.tag'],
            },
            'author': {
                'author.email': repo_config['author.email'],
                'author.name': repo_config['author.name'],
            },
            'timestamp': timestamp(),
        })
    if 'project.name' in repo_config:
        issue_differences.append({
            'action': 'set-project-name',
            'params': {
                'name': repo_config['project.name'],
            },
            'author': {
                'author.email': repo_config['author.email'],
                'author.name': repo_config['author.name'],
            },
            'timestamp': timestamp(),
        })

    if '--param' in ui:
        for k, v in ui.get('--param'):
            issue_differences.append({
                'action': 'parameter-set',
                'params': {
                    'key': k,
                    'value': v,
                },
                'author': {
                    'author.email': repo_config['author.email'],
                    'author.name': repo_config['author.name'],
                },
                'timestamp': timestamp(),
            })

    issue_diff_sha1 = '{0}{1}{2}{3}'.format(repo_config['author.email'], repo_config['author.name'], timestamp(), random.random())
    issue_diff_sha1 = issue.util.misc.create_hash(issue_diff_sha1)
    issue_diff_file_path = os.path.join(issue_group_path, issue_sha1, 'diff', '{0}.json'.format(issue_diff_sha1))
    with open(issue_diff_file_path, 'w') as ofstream:
        ofstream.write(json.dumps(issue_differences))

    next_relese_pointer = get_next_release_pointer()
    if next_relese_pointer:
        store_release_diff(next_relese_pointer, 'open-issue', {
            'id': issue_sha1,
            'message': message.splitlines()[0],
        })

    if parent_uid is not None:
        try:
            issue_differences = [
                {
                    'action': 'set-parent',
                    'params': {
                        'uid': parent_uid,
                    },
                    'author': {
                        'author.email': repo_config['author.email'],
                        'author.name': repo_config['author.name'],
                    },
                    'timestamp': timestamp(),
                }
            ]

            issue_diff_uid = '{0}{1}{2}{3}'.format(
                repo_config['author.email'],
                repo_config['author.name'],
                timestamp(),
                random.random(),
            )
            issue_diff_uid = issue.util.misc.create_hash(issue_diff_uid)
            issue_diff_file_path = os.path.join(
                issue.util.paths.issues_path(),
                issue_sha1[:2],
                issue_sha1,
                'diff',
                '{0}.json'.format(issue_diff_uid),
            )
            with open(issue_diff_file_path, 'w') as ofstream:
                ofstream.write(json.dumps(issue_differences))
        except Exception as e:
            print('{error}: could not set parent issue (identified by "{parent_uid}"):'.format(
                error = colorise(COLOR_WARNING, 'warning'),
                parent_uid = colorise(COLOR_HASH, parent_uid),
            ), e)

    issue.util.issues.indexIssue(issue_sha1)
    markLastIssue(issue_sha1)

    issue.shortlog.append_event_open(issue_sha1, message)
    issue.shortlog.append_event_tagged(issue_sha1, tags)

    if '--chain-to' in ui or '--parent' in ui:
        chained_to = []
        for link_issue_sha1 in ui.get('--chain-to') + [parent_uid,]:
            try:
                link_issue_sha1 = expandIssueUID(link_issue_sha1)
                chained_to.append(link_issue_sha1)
                issue_differences = [
                    {
                        'action': 'chain-link',
                        'params': {
                            'sha1': [issue_sha1],
                        },
                        'author': {
                            'author.email': repo_config['author.email'],
                            'author.name': repo_config['author.name'],
                        },
                        'timestamp': timestamp(),
                    }
                ]

                issue_diff_sha1 = '{0}{1}{2}{3}'.format(repo_config['author.email'], repo_config['author.name'], timestamp(), random.random())
                issue_diff_sha1 = issue.util.misc.create_hash(issue_diff_sha1)
                issue_diff_file_path = os.path.join(issue.util.paths.issues_path(), link_issue_sha1[:2], link_issue_sha1, 'diff', '{0}.json'.format(issue_diff_sha1))
                with open(issue_diff_file_path, 'w') as ofstream:
                    ofstream.write(json.dumps(issue_differences))
                issue.util.issues.indexIssue(link_issue_sha1, issue_diff_sha1)
            except Exception as e:
                print('warning: could not link issue identified by "{0}":'.format(link_issue_sha1), e)
        issue.shortlog.append_event_chained_to(issue_sha1, chained_to)

    if '--git' in ui:
        print('issue/{0}'.format(issue.util.issues.sluggify(message)))
    elif '--verbose' in ui:
        print(issue_sha1)

def commandClose(ui):
    repo_config = issue.config.getConfig()
    issue_sha1 = (getLastIssue() if '--last' in ui else operands[0])
    issue_sha1 = expand_issue_uid_or_exir(issue_sha1)
    issue_data = issue.util.issues.getIssue(issue_sha1)

    if issue_data['status'] == 'closed':
        print('fatal: issue already closed by {0}{1}'.format(issue_data.get('close.author.name', 'Unknown author'), (' ({0})'.format(issue_data['close.author.email']) if 'close.author.email' else '')))
        exit(1)

    chained_issues = issue_data.get('chained', [])
    unclosed_chained_issues = []
    for c in chained_issues:
        ci = issue.util.issues.getIssue(c, index=True)
        if ci['status'] != 'closed':
            unclosed_chained_issues.append((c, ci['message'].splitlines()[0]))
    if unclosed_chained_issues:
        print('fatal: unclosed chained issues exist:')
        for ui_sha1, ui_msg in unclosed_chained_issues:
            print('  {0}: {1}'.format(ui_sha1, ui_msg))
        exit(1)

    ts = None

    if '-t' in ui:
        ts = datetime.datetime.strptime(ui.get('-t'), '%Y-%m-%dT%H:%M:%S')
    issue_differences = [
        {
            'action': 'close',
            'params': {
            },
            'author': {
                'author.email': repo_config['author.email'],
                'author.name': repo_config['author.name'],
            },
            'timestamp': timestamp(ts),
        },
    ]

    if '--git-commit' in ui:
        closing_git_commit = ui.get('--git-commit')
        if closing_git_commit == '-':
            closing_git_commit = 'HEAD'
        p = subprocess.Popen((
                'git',
                'show',
                '--date=iso',
                closing_git_commit,
            ),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        output, error = p.communicate()
        exit_code = p.wait()
        output = output.decode('utf-8').strip()
        if exit_code != 0:
            print(error.decode('utf-8').strip().splitlines()[0])
            exit(exit_code)
        output_lines = output.splitlines()
        closing_git_commit = output_lines[0].split(' ')[1]
        issue_differences[0]['timestamp'] = datetime.datetime.strptime(
            output_lines[2],
            'Date:\t%Y-%m-%d %H:%M:%S %z',
        ).timestamp()
        issue_differences[0]['params']['closing_git_commit'] = closing_git_commit

    issue_diff_sha1 = '{0}{1}{2}{3}'.format(repo_config['author.email'], repo_config['author.name'], timestamp(), random.random())
    issue_diff_sha1 = issue.util.misc.create_hash(issue_diff_sha1)
    issue_diff_file_path = os.path.join(issue.util.paths.issues_path(), issue_sha1[:2], issue_sha1, 'diff', '{0}.json'.format(issue_diff_sha1))
    with open(issue_diff_file_path, 'w') as ofstream:
        ofstream.write(json.dumps(issue_differences))
    issue.shortlog.append_event_close(issue_sha1)

    next_relese_pointer = get_next_release_pointer()
    if next_relese_pointer:
        store_release_diff(next_relese_pointer, 'close-issue', {
            'id': issue_sha1,
        })
    markLastIssue(issue_sha1)
    issue.util.issues.indexIssue(issue_sha1, issue_diff_sha1)
    issue.shortlog.append_event_close(issue_sha1)

def ls_with_details(unique_id, data):
    first_message_line = data['message'].splitlines()[0]
    print(colorise(COLOR_HASH, unique_id))

    issue_open_author_name = data.get('open.author.name', 'Unknown')
    issue_open_author_email = data.get('open.author.email', 'unknown')
    print('Author: {name} <{email}>'.format(
        name = issue_open_author_name,
        email = issue_open_author_email,
    ))

    issue_open_timestamp = datetime.datetime.fromtimestamp(data.get('open.timestamp', 0))
    print('Opened: {when_opened}'.format(
        when_opened = issue_open_timestamp,
    ))
    if data['status'] == 'closed':
        issue_close_author_name = data.get('close.author.name', 'Unknown')
        issue_close_author_email = data.get('close.author.email', 'unknown')
        if issue_close_author_email != issue_open_author_email:
            print('Fixer:  {name} <{email}>'.format(
                name = issue_close_author_name,
                email = issue_close_author_email,
            ))
        issue_close_timestamp = datetime.datetime.fromtimestamp(data.get('close.timestamp', 0))
        print('Closed: {closed_when}'.format(
            closed_when = issue_close_timestamp,
        ))

    print()
    print('    {}'.format(first_message_line))

def commandLs(ui):
    groups = os.listdir(issue.util.paths.issues_path())
    issues = listIssuesUsingShortestPossibleUIDs(with_full=True)

    ls_keywords = [kw.lower() for kw in ui.operands() if len(kw) > 1]

    accepted_statuses = []
    if '--status' in ui:
        accepted_statuses = [s[0] for s in ui.get('--status')]
    accepted_tags = []
    if '--tag' in ui:
        accepted_tags = [s[0] for s in ui.get('--tag')]

    delta_mods_since, since, delta_mods_until, until = [], None, [], None
    if '--since' in ui:
        delta_mods_since = [s[0] for s in ui.get('--since')]
    if '--until' in ui:
        delta_mods_until = [s[0] for s in ui.get('--until')]
    if '--recent' in ui:
        delta_mods_since = issue.config.getConfig().get('default.time.recent', '1day').split(',')

    if '--since' in ui or '--recent' in ui:
        set_by_timepoint = False
        for each in delta_mods_since:
            try:
                since = datetime.datetime.strptime(each, '%Y-%m-%d')
                set_by_timepoint = True
                break
            except ValueError:
                pass
        if not set_by_timepoint:
            since = (
                datetime.datetime.now() - datetime.timedelta(
                    **get_time_delta_arguments(delta_mods_since)))

    if '--until' in ui:
        set_by_timepoint = False
        for each in delta_mods_until:
            try:
                until = datetime.datetime.strptime(each, '%Y-%m-%d')
                set_by_timepoint = True
                break
            except ValueError:
                pass
        if not set_by_timepoint:
            until = (
                datetime.datetime.now() - datetime.timedelta(
                    **get_time_delta_arguments(delta_mods_until)))

    issues_to_list = []
    for short, i in issues:
        if colored:
            short = (colored.fg('yellow') + short + colored.attr('reset'))

        issue_sha1 = i.split('.', 1)[0]
        try:
            issue_data = issue.util.issues.getIssue(issue_sha1)
        except issue.exceptions.NotIndexed as e:
            not_indexed_message = '[not indexed]'
            if colored:
                not_indexed_message = (colored.fg('red') + not_indexed_message + colored.attr('reset'))
            print('{0} {1}'.format(short, not_indexed_message))
            continue

        if '--open' in ui and (issue_data['status'] if 'status' in issue_data else '') not in ('open', ''): continue
        if '--closed' in ui and (issue_data['status'] if 'status' in issue_data else '') != 'closed': continue
        if '--status' in ui and (issue_data['status'] if 'status' in issue_data else '') not in accepted_statuses: continue
        if '--tag' in ui:
            issue_tags = (issue_data['tags'] if 'tags' in issue_data else [])
            tags_positive = list(filter(lambda x: x[0] != '^', accepted_tags))
            tags_negative = list(filter(lambda x: x[0] == '^', accepted_tags))

            tags_match = False
            if (not tags_positive) and tags_negative:
                tags_match = True

            for l in tags_positive:
                if l in issue_tags:
                    tags_match = True
                    break
            for l in tags_negative:
                if l[1:] in issue_tags:
                    tags_match = False
                    break
            if not tags_match:
                continue
        issues_to_list.append((short, i, issue_data))

    if '--chained-to' in ui:
        chained_issues = issue.util.issues.getIssue(expandIssueUID(ui.get('--chained-to'))).get('chained', [])
        issues_to_list = list(filter(lambda i: (i[1] in chained_issues), issues_to_list))

    if '--priority' in ui:
        issues_to_list = sorted(issues_to_list, key=lambda t: int(t[2].get('parameters', {}).get('priority', 1024)))

    good_issues_to_list = []
    for each in issues_to_list:
        if 'message' not in each[2]:
            fmt = '{}: broken issue {}: does not have a message\n'
            sys.stderr.write(fmt.format(
                colorise(COLOR_ERROR, 'error'),
                colorise(COLOR_HASH, each[1]),
            ))
            continue
        good_issues_to_list.append(each)
    issues_to_list = sorted(good_issues_to_list, key = lambda each: each[2]['message'].splitlines()[0])

    limit = len(issues_to_list) - 1
    for n, each in enumerate(issues_to_list):
        short, i, issue_data = each
        if since is not None:
            issue_timestamp = ('close.timestamp' if '--closed' in ui else 'open.timestamp')
            issue_timestamp = datetime.datetime.fromtimestamp(issue_data.get(issue_timestamp, 0))
            if issue_timestamp < since:
                continue
        if until is not None:
            issue_timestamp = ('close.timestamp' if '--closed' in ui else 'open.timestamp')
            issue_timestamp = datetime.datetime.fromtimestamp(issue_data.get(issue_timestamp, 0))
            if issue_timestamp > until:
                continue
        if '--author' in ui:
            author = ui.get('--author')
            if not (author in issue_data['open.author.name'] or author in issue_data['open.author.email']):
                continue
        if ls_keywords:
            message_lower = issue_data['message'].lower()
            found = 0
            for kw in ls_keywords:
                if kw[0] == '-' and kw[1:] in message_lower:
                    found -= 1
                    continue
                if kw[0] == '^' and kw[1:] in message_lower:
                    found = 0
                    break
                if kw[0] == '+':
                    found += (1 if kw[1:] in message_lower else -1)
                    continue
                if kw[0] == '=' and kw[1:] not in message_lower:
                    found = 0
                    break
                if kw in message_lower:
                    found += 1
            if found < LS_KEYWORD_MATCH_THRESHOLD:
                continue

        full = i
        if colored:
            full = (colored.fg('yellow') + full + colored.attr('reset'))
        try:
            if colored:
                short = (colored.fg('yellow') + short + colored.attr('reset'))
            if '--details' in ui:
                ls_with_details(full, issue_data)
                if n != limit:
                    print()
            else:
                first_message_line = issue_data['message'].splitlines()[0]
                if colored:
                    for kw in ls_keywords:
                        first_message_line = first_message_line.replace(kw, (colored.fg('light_green') + kw + colored.attr('reset')))
                msg = '{0} {1}'.format(short, first_message_line)
                if '--verbose' in ui or accepted_tags:
                    tags = [t for t in issue_data['tags']]
                    if colored:
                        tags = [(colored.fg('cyan') + t + colored.attr('reset')) for t in tags]
                    tags = ' '.join(['#{}'.format(t) for t in tags])
                    if tags:
                        msg = '{} ({})'.format(msg, tags)
                print(msg)
        except (KeyError, IndexError) as e:
            broken_index_message = '[broken index]'
            if colored:
                broken_index_message = (colored.fg('red') + broken_index_message + colored.attr('reset'))
            print('{0} {1}'.format(full, broken_index_message))

def commandDrop(ui):
    issue_list = ([getLastIssue()] if '--last' in ui else operands)
    for issue_sha1 in issue_list:
        try:
            issue.util.issues.dropIssue(expandIssueUID(issue_sha1))
        except issue.exceptions.IssueUIDAmbiguous:
            print('fail: issue uid {0} is ambiguous'.format(repr(issue_sha1)))

def make_short_uid(uid, limit = 8):
    return uid[:max(8, limit)]

def commandSlug(ui):
    issue_data = {}
    issue_sha1 = (getLastIssue() if '--last' in ui else operands[0])
    issue_sha1 = expand_issue_uid_or_exir(issue_sha1)
    issue_data = issue.util.issues.getIssue(issue_sha1)
    issue_message = issue_data['message'].splitlines()[0].strip()
    issue_slug = issue.util.issues.sluggify(issue_message)
    issue_uid, issue_short_uid = issue_sha1, make_short_uid(
        issue_sha1, limit = shortestUnique(issue.util.issues.ls()))

    slug_format = issue.config.getConfig().get('slug.format.default', '')
    if slug_format.startswith('@'):
        slug_format = issue.config.getConfig().get('slug.format.{0}'.format(slug_format[1:]), '')

    slug_parameters = issue_data.get('parameters', {})
    if '--param' in ui:
        for k, v in ui.get('--param'):
            slug_parameters[k] = v

    if '--git' in ui:
        slug_format = 'issue-{short_uid}-{slug}'
    if '--format' in ui:
        slug_format = ui.get('--format')
    if '--use-format' in ui:
        slug_format = issue.config.getConfig().get('slug.format.{0}'.format(ui.get('--use-format')), '')
        if not slug_format:
            print('fatal: undefined slug format: {0}'.format(ui.get('--use-format')))
            exit(1)

    if '--append' in ui:
        slug_format += ('-' + ui.get('--append'))

    if 'parent' in issue_data:
        slug_parameters['parent_uid'] = issue_data['parent']
        slug_parameters['parent_short_uid'] = make_short_uid(issue_data['parent'])

    if slug_format:
        try:
            uid_regex = re.compile(r'\{uid:(\d+)\}')
            uids_to_replace = uid_regex.findall(slug_format)
            for each in map(int, uids_to_replace):
                slug_format = slug_format.replace(
                    '{{uid:{}}}'.format(each),
                    issue_uid[:each],
                )

            issue_slug = slug_format.format(
                slug = issue_slug,
                uid = issue_uid,
                short_uid = issue_short_uid,
                **slug_parameters,
            )
        except KeyError as e:
            print('error: required parameter not found: {}'.format(str(e)))
            exit(1)

    if '--git-branch' in ui:
        def git_current_branch():
            ret, output = subprocess.getstatusoutput('git rev-parse --abbrev-ref HEAD')
            if ret != 0:
                raise Exception('failed to get current Git branch')
            return output.strip()
        allow_branching_from = issue.config.getConfig().get('slug.allow_branching_from')

        current_branch = git_current_branch()
        if allow_branching_from is not None and current_branch not in allow_branching_from:
            print('{}: branching from {} not allowed'.format(
                colorise(COLOR_ERROR, 'error'),
                colorise_repr(COLOR_BRANCH_NAME, current_branch),
            ))
            print('{}: branching allowed from: {}'.format(
                colorise(COLOR_NOTE, 'note'),
                ', '.join([colorise_repr(COLOR_BRANCH_NAME, each) for each in allow_branching_from]),
            ))
            if '-Z' not in ui:
                exit(1)
            print('{}: overridden by -Z flag'.format(colorise(COLOR_NOTE, 'note')))
        r = os.system('git branch {0}'.format(issue_slug))
        r = (r >> 8)
        if r != 0:
            exit(r)
    if '--git-checkout' in ui:
        r = os.system('git checkout {0}'.format(issue_slug))
        r = (r >> 8)
        if r != 0:
            exit(r)
    if ('--git-branch' not in ui) and ('--git-checkout' not in ui):
        print(issue_slug)
    issue.shortlog.append_event_slug(issue_sha1, issue_slug)
    markLastIssue(issue_sha1)

def commandComment(ui):
    issue_sha1 = (getLastIssue() if '--last' in ui else operands[0])
    try:
        issue_sha1 = expandIssueUID(issue_sha1)
    except issue.exceptions.IssueUIDAmbiguous:
        print('fail: issue uid {0} is ambiguous'.format(repr(issue_sha1)))
        exit(1)

    issue_data = issue.util.issues.getIssue(issue_sha1)

    issue_comment = ''
    if '--message' in ui:
        issue_comment = ui.get('--message')
    elif len(operands) < (1 if '--last' in ui else 2):
        issue_comment = getMessage('issue_comment_message', fmt={'issue_sha1': issue_sha1, 'issue_message': '\n'.join(['#  > {0}'.format(l) for l in issue_data['message'].splitlines()])})
    else:
        # True evaluates to 1 and
        # False evaluates to 0
        # this is exactly what we need here - since the 1 and 0 are
        # indexes of the comment depending on whether the option is
        # given or not
        issue_comment = operands[int(not ('--last' in ui))]

    if not issue_comment:
        print('fatal: aborting due to empty message')
        exit(1)

    issue_comment_timestamp = datetime.datetime.now().timestamp()
    issue_comment_sha1 = issue.util.misc.create_hash('{0}{1}{2}'.format(issue_sha1, issue_comment_timestamp, issue_comment))
    issue_comment_data = {
        'message': issue_comment,
        'timestamp': issue_comment_timestamp,
    }
    config_data = issue.config.getConfig()
    issue_comment_data = {
        'author.name': config_data['author.name'],
        'author.email': config_data['author.email'],
        'message': issue_comment,
        'timestamp': issue_comment_timestamp,
    }

    os.makedirs(issue.util.paths.comments_path_of(issue_sha1), exist_ok = True)
    with open(os.path.join(issue.util.paths.comments_path_of(issue_sha1), '{0}.json'.format(issue_comment_sha1)), 'w') as ofstream:
        ofstream.write(json.dumps(issue_comment_data))
    markLastIssue(issue_sha1)

def commandTag(ui):
    ui = ui.down()
    subcommand = str(ui)
    if subcommand == 'ls':
        available_tags, tag_to_issue_map = issue.objects.tags.gather()
        created_tags = set(issue.objects.tags.ls())
        for t in sorted(set(available_tags)):
            s = '{0}{1}'
            if '--verbose' in ui:
                s += '/{2}'
            tag_marker = ' '
            if t not in created_tags:
                tag_marker = '!'
            print(s.format(tag_marker, t, len(tag_to_issue_map[t])))
    elif subcommand == 'new':
        if '--missing' in ui:
            available_tags, tag_to_issue_map = issue.objects.tags.gather()
            created_tags = set(issue.objects.tags.ls())
            missing_tags = (set(available_tags) - created_tags)
            n = 0
            for t in missing_tags:
                issue.objects.tags.make(t)
            if '--verbose' in ui:
                print('created {0} tag(s): {1}'.format(len(missing_tags), ', '.join(sorted(missing_tags))))
        else:
            try:
                issue.objects.tags.make(
                    tag_name = ui.operands()[0],
                    force = ('--force' in ui),
                )
            except issue.exceptions.TagExists as e:
                print('fatal: tag exists: {0}'.format(e))
                exit(1)
    elif subcommand == 'rm':
        print('removed tag: {0}'.format(ui.operands()[0]))
    elif subcommand == 'show':
        print('details of tag: {0}'.format(ui.operands()[0]))
    elif subcommand == 'tag':
        issue_sha1 = (getLastIssue() if '--last' in ui else operands[1])
        try:
            issue_sha1 = expandIssueUID(issue_sha1)
        except issue.exceptions.IssueUIDAmbiguous:
            print('fail: issue uid {0} is ambiguous'.format(repr(issue_sha1)))
            exit(1)

        issue_tag = operands[0]

        if issue_tag not in issue.objects.tags.gather()[0]:
            print('fatal: tag "{0}" does not exist'.format(issue_tag))
            print('note: use "issue tag new {0}" to create it'.format(issue_tag))
            exit(1)

        if not issue_tag:
            print('fatal: aborting due to empty tag')
            exit(1)

        repo_config = issue.config.getConfig()

        issue_differences = [
            {
                'action': ('remove-tags' if '--remove' in ui else 'push-tags'),
                'params': {
                    'tags': [issue_tag],
                },
                'author': {
                    'author.email': repo_config['author.email'],
                    'author.name': repo_config['author.name'],
                },
                'timestamp': timestamp(),
            }
        ]

        issue_diff_sha1 = '{0}{1}{2}{3}'.format(repo_config['author.email'], repo_config['author.name'], timestamp(), random.random())
        issue_diff_sha1 = issue.util.misc.create_hash(issue_diff_sha1)
        issue_diff_file_path = os.path.join(issue.util.paths.issues_path(), issue_sha1[:2], issue_sha1, 'diff', '{0}.json'.format(issue_diff_sha1))
        with open(issue_diff_file_path, 'w') as ofstream:
            ofstream.write(json.dumps(issue_differences))
        markLastIssue(issue_sha1)
        issue.util.issues.indexIssue(issue_sha1, issue_diff_sha1)
    else:
        print('fatal: unrecognized subcommand: {0}'.format(subcommand))
        exit(1)

def commandParam(ui):
    issue_sha1 = (getLastIssue() if '--last' in ui else operands[0])
    try:
        issue_sha1 = expandIssueUID(issue_sha1)
    except issue.exceptions.IssueUIDAmbiguous:
        print('fail: issue uid {0} is ambiguous'.format(repr(issue_sha1)))
        exit(1)

    issue_parameter_key = operands[int(not ('--last' in ui))]

    if not issue_parameter_key:
        print('fatal: aborting due to empty parameter key')
        exit(1)

    repo_config = issue.config.getConfig()

    issue_differences = [
        {
            'params': {},
            'author': {
                'author.email': repo_config['author.email'],
                'author.name': repo_config['author.name'],
            },
            'timestamp': timestamp(),
        }
    ]
    if '--remove' in ui:
        issue_differences[0]['action'] = 'parameter-remove'
        issue_differences[0]['params']['key'] = issue_parameter_key
    else:
        issue_differences[0]['action'] = 'parameter-set'
        issue_differences[0]['params']['key'] = issue_parameter_key
        issue_differences[0]['params']['value'] = operands[int(not ('--last' in ui))+1]

    issue_diff_sha1 = '{0}{1}{2}{3}'.format(repo_config['author.email'], repo_config['author.name'], timestamp(), random.random())
    issue_diff_sha1 = issue.util.misc.create_hash(issue_diff_sha1)
    issue_diff_file_path = os.path.join(issue.util.paths.issues_path(), issue_sha1[:2], issue_sha1, 'diff', '{0}.json'.format(issue_diff_sha1))
    with open(issue_diff_file_path, 'w') as ofstream:
        ofstream.write(json.dumps(issue_differences))
    markLastIssue(issue_sha1)
    issue.util.issues.indexIssue(issue_sha1, issue_diff_sha1)

def commandShow(ui):
    ui = ui.down()
    issue_sha1 = (getLastIssue() if '--last' in ui else ui.operands()[0])
    issue_sha1 = expand_issue_uid_or_exir(issue_sha1)

    if str(ui) == 'show' and '--index' in ui:
        issue.util.issues.indexIssue(issue_sha1)

    issue_data = {}
    try:
        issue_data = issue.util.issues.getIssue(issue_sha1)
    except issue.exceptions.NotAnIssue as e:
        print('fatal: {0} does not identify a valid object'.format(repr(issue_sha1)))
        exit(1)
    except issue.exceptions.NotIndexed as e:
        print('fatal: object {0} is not indexed'.format(repr(issue_sha1)))
        print('note: run "issue index {0}"'.format(ui.operands()[0]))
        exit(1)

    if str(ui) == 'show':
        issue.shortlog.append_event_show(issue_sha1)

        issue_message_lines = issue_data['message'].splitlines()

        issue_open_author_name = (issue_data['open.author.name'] if 'open.author.name' in issue_data else 'Unknown Author')
        issue_open_author_email = (issue_data['open.author.email'] if 'open.author.email' in issue_data else 'Unknown email')
        issue_open_timestamp = (datetime.datetime.fromtimestamp(issue_data['open.timestamp']) if 'open.timestamp' in issue_data else 'unknown date')

        issue_heading = 'issue {0}'.format(issue_sha1)
        if colored:
            issue_heading = (colored.fg('yellow') + issue_heading + colored.attr('reset'))
        print(issue_heading)

        opened_by_heading = 'opened by'
        if colored:
            opened_by_heading = (colored.fg('red') + opened_by_heading + colored.attr('reset'))
        print('{}:   {} ({}), on {}'.format(opened_by_heading, issue_open_author_name, issue_open_author_email, issue_open_timestamp))
        if issue_data['status'] == 'closed':
            closed_by_heading = 'closed by'
            if colored:
                closed_by_heading = (colored.fg('green') + closed_by_heading + colored.attr('reset'))
            issue_close_author_name = (issue_data['close.author.name'] if 'close.author.name' in issue_data else 'Unknown Author')
            issue_close_author_email = (issue_data['close.author.email'] if 'close.author.email' in issue_data else 'Unknown email')
            issue_close_timestamp = (datetime.datetime.fromtimestamp(issue_data['close.timestamp']) if 'close.timestamp' in issue_data else 'unknown date')
            print('{}:   {} ({}), on {}'.format(closed_by_heading, issue_close_author_name, issue_close_author_email, issue_close_timestamp))

        milestones = issue_data.get('milestones', [])
        if milestones:
            print('milestones:  {0}'.format(', '.join(milestones)))

        tags = issue_data.get('tags', [])
        if tags:
            print('tags:        {0}'.format(', '.join(tags)))

        default_project = 'Unknown'
        project = issue_data.get('project.name', 'Unknown')
        if project != default_project:
            print('project:     {0} ({1})'.format(project, issue_data.get('project.tag', '')))

        indented_message_lines = ['    {}'.format(l) for l in issue_message_lines]
        print('\n{}'.format('\n'.join(indented_message_lines)))

        parameters = issue_data.get('parameters', [])
        if parameters:
            parameters_heading = '---- PARAMETERS'
            if colored:
                parameters_heading = (colored.fg('white') + parameters_heading + colored.attr('reset'))
            print('\n{}'.format(parameters_heading))
            for key in sorted(parameters.keys()):
                value = parameters[key]
                if colored: key = (colored.fg('green') + key + colored.attr('reset'))
                print('    {0} = {1}'.format(key, value))

        short_hash_chars = shortest_unique_prefix()

        parent_uid = issue_data.get('parent')
        if parent_uid:
            chained_issues_heading = '---- CHILD OF'
            if colored:
                chained_issues_heading = (colored.fg('white') + chained_issues_heading + colored.attr('reset'))
            print('\n{}'.format(chained_issues_heading))
            parent_issue = getIssue(parent_uid)
            print('    {0} ({1}): {2}'.format(
                colorise(COLOR_HASH, parent_uid[:short_hash_chars]),
                parent_issue.get('status'),
                parent_issue.get('message', '').splitlines()[0]),
            )

        attached_issues = issue_data.get('attached', [])
        if attached_issues:
            attached_issues_heading = '---- ATTACHED ISSUES'
            if colored:
                attached_issues_heading = (colored.fg('white') + attached_issues_heading + colored.attr('reset'))
            print('\n{}'.format(attached_issues_heading))
            for s in sorted(attached_issues):
                attached_issue = issue.util.issues.getIssue(s)
                short_hash = s[:short_hash_chars]
                if colored:
                    short_hash = (colored.fg('yellow') + short_hash + colored.attr('reset'))
                print('    {0} ({1}): {2}'.format(
                    short_hash,
                    attached_issue.get('status'),
                    attached_issue.get('message', '').splitlines()[0],
                ))

        chained_issues = issue_data.get('chained', [])
        if chained_issues:
            chained_issues_heading = '---- CHAINED ISSUES'
            if colored:
                chained_issues_heading = (colored.fg('white') + chained_issues_heading + colored.attr('reset'))
            print('\n{}'.format(chained_issues_heading))
            for s in sorted(chained_issues):
                try:
                    chained_issue = issue.util.issues.getIssue(s)
                except issue.exceptions.NotAnIssue:
                    # Ignore dropped issues.
                    continue
                short_hash = s[:short_hash_chars]
                if colored:
                    short_hash = (colored.fg('yellow') + short_hash + colored.attr('reset'))
                print('    {0} ({1}): {2}'.format(
                    short_hash,
                    chained_issue.get('status'),
                    chained_issue.get('message', '').splitlines()[0],
                ))

        if 'closing_git_commit' in issue_data:
            closing_git_commit_heading = '---- CLOSING GIT COMMIT'
            closing_git_commit = issue_data['closing_git_commit']
            if colored:
                closing_git_commit_heading = (colored.fg('white') + closing_git_commit_heading + colored.attr('reset'))
                closing_git_commit = (colored.fg('yellow') + closing_git_commit + colored.attr('reset'))
            print('\n{}: {}\n'.format(closing_git_commit_heading, closing_git_commit))

        issue_comment_thread = dict((issue_data['comments'][key]['timestamp'], key) for key in issue_data['comments'])
        if issue_comment_thread and '--comments' in ui:
            comment_thread_heading = '---- COMMENT THREAD:'
            comment_thread_heading = colorise('white', comment_thread_heading)
            print('\n{}'.format(comment_thread_heading))
            for timestamp in sorted(issue_comment_thread.keys()):
                issue_comment = issue_data['comments'][issue_comment_thread[timestamp]]
                print('{0} {1} ({2}) at {3}\n'.format(
                    colorise(COLOR_NOTE, '>>>>'),
                    issue_comment['author.name'],
                    issue_comment['author.email'],
                    colorise(COLOR_DATETIME,
                        str(datetime.datetime.fromtimestamp(issue_comment['timestamp']))),
                ))
                indented_message_lines = ['  {}'.format(l) for l in issue_comment['message'].splitlines()]
                print('{}'.format('\n'.join(indented_message_lines)))
                print()
        markLastIssue(issue_sha1)
    elif str(ui) == 'log':
        issue.shortlog.append_event_show(issue_sha1)

        issue_sha1_heading = colorise(COLOR_HASH, issue_sha1)
        print('showing log of issue: {0}'.format(issue_sha1_heading))
        issue_differences = issue.util.issues.getIssueDifferences(issue_sha1, *issue.util.issues.listIssueDifferences(issue_sha1))

        issue_differences_sorted = []
        issue_differences_order = {}
        for i, d in enumerate(issue_differences):
            if d['timestamp'] not in issue_differences_order:
                issue_differences_order[d['timestamp']] = []
            issue_differences_order[d['timestamp']].append(i)
        issue_differences_sorted = []
        for ts in sorted(issue_differences_order.keys()):
            issue_differences_sorted.extend([issue_differences[i] for i in issue_differences_order[ts]])

        for d in issue_differences_sorted:
            diff_datetime = str(datetime.datetime.fromtimestamp(d['timestamp'])).rsplit('.', 1)[0]
            diff_action = d['action']

            diff_datetime_heading = diff_datetime
            action_heading = ''
            author_heading = '{}'.format(d['author']['author.name'])
            author_email_heading = d['author']['author.email'].strip()
            message_heading = ''

            if diff_action == 'open':
                action_heading = 'opened'
            elif diff_action == 'close':
                action_heading = 'closed'
                if 'closing_git_commit' in d['params'] and d['params']['closing_git_commit']:
                    message_heading = ' with Git commit {0}'.format(d['params']['closing_git_commit'])
            elif diff_action == 'set-message':
                action_heading = 'message set'
            # support both -tags and -labels ("labels" name has been used in pre-0.1.5 versions)
            # FIXME: this support should be removed after early repositories are converted
            elif diff_action == 'push-tags' or diff_action == 'push-labels':
                action_heading = 'tagged'
                message_heading = 'with {}'.format(', '.join(d['params'][('tags' if 'tags' in d['params'] else 'labels')]))
            # support both -tags and -labels ("labels" name has been used in pre-0.1.5 versions)
            # FIXME: this support should be removed after early repositories are converted
            elif diff_action == 'remove-tags' or diff_action == 'remove-labels':
                action_heading = 'tags removed'
                message_heading = 'with {}'.format(', '.join(d['params'][('tags' if 'tags' in d['params'] else 'labels')]))
            elif diff_action == 'parameter-set':
                action_heading = 'parameter set'
                message_heading = '{} = {}'.format(d['params']['key'], repr(d['params']['value']))
            elif diff_action == 'parameter-remove':
                action_heading = 'parameter removed'
                message_heading = d['params']['key']
            elif diff_action == 'push-milestones':
                action_heading = 'milestones set'
                message_heading = ', '.join(d['params']['milestones'])
            elif diff_action == 'set-status':
                action_heading = 'status set'
                message_heading = d['params']['status']
            elif diff_action == 'set-project-tag':
                action_heading = 'project tag set'
                message_heading = d['params']['tag']
            elif diff_action == 'set-project-name':
                action_heading = 'project name set'
                message_heading = d['params']['name']
            elif diff_action == 'chain-link':
                action_heading = 'chained'
                message_heading = 'with issue(s) {}'.format(', '.join(d['params']['sha1']))
            elif diff_action == 'chain-unlink':
                action_heading = 'unchained'
                message_heading = 'from issue(s) {}'.format(', '.join(d['params']['sha1']))

            if colored:
                diff_datetime_heading = (colored.fg('white') + diff_datetime_heading + colored.attr('reset'))
                action_heading = (colored.fg('green') + action_heading + colored.attr('reset'))
                author_heading = (colored.fg('white') + author_heading + colored.attr('reset'))
                if author_email_heading:
                    author_email_heading = (colored.fg('white') + author_email_heading + colored.attr('reset'))

            if author_email_heading:
                author_heading = '{} ({})'.format(author_heading, author_email_heading)

            if message_heading:
                message_heading = ': {}'.format(message_heading)

            print('{}: {} by {}{}'.format(diff_datetime_heading, action_heading, author_heading, message_heading))

def commandConfig(ui):
    ui = ui.down()
    config_data = {}
    config_path = os.path.expanduser(('~/.issueconfig.json' if '--global' in ui else './.issue/config.json'))
    if not os.path.isfile(config_path):
        config_data = {}
    else:
        with open(config_path, 'r') as ifstream:
            config_data = json.loads(ifstream.read())

    if str(ui) == 'get':
        config_key = ui.operands()[0]

        if '..' in config_key:
            print('fatal: invalid key: double dot used')
            exit(1)
        if config_key.startswith('.') or config_key.endswith('.'):
            print('fatal: invalid key: starts or begins with dot')
            exit(1)

        config_value = config_data[config_key]

        print((json.dumps({config_key: config_value}) if '--verbose' in ui else (config_value if config_value is not None else 'null')))
    elif str(ui) == 'set':
        operands = ui.operands()
        config_key = operands[0]
        config_value = (operands[1] if len(operands) == 2 else '')
        if '--null' in ui:
            config_value = None

        if '..' in config_key:
            print('fatal: invalid key: double dot used')
            exit(1)
        if config_key.startswith('.') or config_key.endswith('.'):
            print('fatal: invalid key: starts or begins with dot')
            exit(1)

        if '--unset' in ui:
            del config_data[config_key]
        else:
            config_data[config_key] = config_value

        with open(config_path, 'w') as ofstream:
            ofstream.write(json.dumps(config_data))
    elif str(ui) == 'dump':
        print((json.dumps(config_data) if '--verbose' not in ui else json.dumps(config_data, sort_keys=True, indent=2)))

def commandRemote(ui):
    ui = ui.down()
    operands = ui.operands()

    remotes = getRemotes()

    if str(ui) == 'ls':
        for k, remote_data in remotes.items():
            print(('{}\t{}' if '--verbose' in ui else '{}').format(
                k,
                remote_data['url']
            ))
    elif str(ui) == 'set':
        remote_name = operands[0]
        if remote_name not in remotes:
            remotes[remote_name] = {}
        if len(operands) == 2:
            remotes[remote_name]['url'] = operands[1]
        if '--url' in ui:
            remotes[remote_name]['url'] = ui.get('--url')
        if '--key' in ui:
            remotes[remote_name][ui.get('--key')] = ui.get('--value')
        if '--unset' in ui:
            del remotes[remote_name][ui.get('--unset')]
        saveRemotes(remotes)
    elif str(ui) == 'rm':
        remote_name = ui.operands()[0]
        if remote_name in remotes:
            del remotes[remote_name]
        else:
            print('fatal: remote does not exist: {0}'.format(remote_name))
            exit(1)
        saveRemotes(remotes)
    elif str(ui) == 'show':
        remote_name = ui.operands()[0]
        if remote_name in remotes:
            for k in sorted(remotes[remote_name].keys()):
                print('{0} => {1}'.format(k, repr(remotes[remote_name][k])))
        else:
            print('fatal: remote does not exist: {0}'.format(remote_name))
            exit(1)

def commandPull(ui):
    ui = ui.down()
    remotes = getRemotes()
    pull_from_remotes = (ui.operands() or sorted(remotes.keys()))

    for remote_name in pull_from_remotes:
        pull_from_remote(remote_name, remotes[remote_name]['url'])

    if '--index' in ui:
        for issue_uuid in issue.util.issues.ls():
            issue.util.issues.indexIssue(issue_uuid)

def commandPush(ui):
    ui = ui.down()
    remotes = getRemotes()
    publish_to_remotes = (ui.operands() or sorted(remotes.keys()))

    for remote_name in publish_to_remotes:
        push_to_remote(remote_name, remotes[remote_name]['url'])

def commandIndex(ui):
    ui = ui.down()
    issue_list = ui.operands()
    if '--reverse' not in ui and not issue_list:
        issue_list = issue.util.issues.ls()
    if '--reverse' in ui:
        for i in issue.util.issues.ls():
            if not os.listdir(os.path.join(issue.util.paths.issues_path(), i[:2], i, 'diff')):
                issue_list.append(i)
    n = shortestUnique(issue_list)
    for issue_uuid in issue_list:
        issue_uuid = expandIssueUID(issue_uuid)
        short_uuid = issue_uuid[:n]
        if '--reverse' in ui:
            print('rev-indexing issue: {0}'.format(short_uuid))
            issue.util.issues.revindexIssue(issue_uuid)
        else:
            if '--verbose' in ui:
                print('indexing issue: {}'.format(
                    colorise(COLOR_HASH, short_uuid),
                ))
            issue.util.issues.indexIssue(issue_uuid)

def commandClone(ui):
    ui = ui.down()
    operands = ui.operands()

    try:
        initialised_where = issue.repository.init(
            where = '.',
            force = ('--force' in ui),
        )
        if '--verbose' in ui:
            print('repository initialised in {0}'.format(initialised_where))
    except issue.exceptions.RepositoryExists:
        print('fatal: repository exists')
        exit(1)
    remotes = getRemotes()

    remote_name = (ui.get('--name') if '--name' in ui else 'origin')
    remote_url = operands[0]

    remotes[remote_name] = {}
    remotes[remote_name]['url'] = remote_url
    saveRemotes(remotes)

    pull_from_remote(remote_name, remote_url)

def commandChain(ui):
    ui = ui.down()

    issue_sha1 = ui.operands()[0]
    try:
        issue_sha1 = expandIssueUID(issue_sha1)
    except issue.exceptions.IssueUIDAmbiguous:
        print('fail: issue uid {0} is ambiguous'.format(repr(issue_sha1)))
        exit(1)

    link_issue_sha1s = ui.operands()[1:]
    for i, link_issue_sha1 in enumerate(link_issue_sha1s):
        link_issue_sha1s[i] = expand_issue_uid_or_exir(link_issue_sha1)

    if str(ui) == 'attach':
        repo_config = issue.config.getConfig()

        for link_issue_sha1 in link_issue_sha1s:
            issue_differences = [
                {
                    'action': 'chain-attach',
                    'params': {
                        'sha1': [link_issue_sha1],
                    },
                    'author': {
                        'author.email': repo_config['author.email'],
                        'author.name': repo_config['author.name'],
                    },
                    'timestamp': timestamp(),
                }
            ]

            issue_diff_sha1 = '{0}{1}{2}{3}'.format(repo_config['author.email'], repo_config['author.name'], timestamp(), random.random())
            issue_diff_sha1 = issue.util.misc.create_hash(issue_diff_sha1)
            issue_diff_file_path = os.path.join(issue.util.paths.issues_path(), issue_sha1[:2], issue_sha1, 'diff', '{0}.json'.format(issue_diff_sha1))
            with open(issue_diff_file_path, 'w') as ofstream:
                ofstream.write(json.dumps(issue_differences))
            markLastIssue(issue_sha1)
            issue.util.issues.indexIssue(issue_sha1, issue_diff_sha1)
    elif str(ui) == 'link':
        repo_config = issue.config.getConfig()

        for link_issue_sha1 in link_issue_sha1s:
            issue_differences = [
                {
                    'action': 'chain-link',
                    'params': {
                        'sha1': [link_issue_sha1],
                    },
                    'author': {
                        'author.email': repo_config['author.email'],
                        'author.name': repo_config['author.name'],
                    },
                    'timestamp': timestamp(),
                }
            ]

            issue_diff_sha1 = '{0}{1}{2}{3}'.format(repo_config['author.email'], repo_config['author.name'], timestamp(), random.random())
            issue_diff_sha1 = issue.util.misc.create_hash(issue_diff_sha1)
            issue_diff_file_path = os.path.join(issue.util.paths.issues_path(), issue_sha1[:2], issue_sha1, 'diff', '{0}.json'.format(issue_diff_sha1))
            with open(issue_diff_file_path, 'w') as ofstream:
                ofstream.write(json.dumps(issue_differences))
            markLastIssue(issue_sha1)
            issue.util.issues.indexIssue(issue_sha1, issue_diff_sha1)
    elif str(ui) == 'unlink':
        print(ui)
    else:
        print(ui)

def commandStatistics(ui):
    ui = ui.down()
    issue_list = listIssuesUsingShortestPossibleUIDs(with_full=True)

    try:
        issues = [issue.util.issues.getIssue(i[1]) for i in issue_list]
    except issue.exceptions.NotIndexed:
        sys.stderr.write('{}: not indexed\n'.format(colorise(COLOR_ERROR, 'error')))
        sys.stderr.write('{}: run {} to index issues\n'.format(
            colorise(COLOR_NOTE, 'note'),
            colorise_repr('white', 'issue index'),
        ))
        exit(1)

    open_issues = list(filter(lambda i: i['status'] == 'open', issues))
    closed_issues = list(filter(lambda i: i['status'] == 'closed', issues))

    issues_count = len(issues)
    open_issues_count = len(open_issues)
    closed_issues_count = len(closed_issues)

    if not issues_count:
        print('No issues.')
        exit(0)

    if True:
        percentage_closed = round((closed_issues_count/issues_count*100), 2)
        N = 40
        limit = int(percentage_closed * N / 100)
        print('|', end='')
        for i in range(limit):
            print((colored.fg('green') + '#' + colored.attr('reset') if colored else '#'), end='')
        for i in range(N-limit):
            print((colored.fg('red') + '#' + colored.attr('reset') if colored else ' '), end='')

        closed_issues_count_heading = str(closed_issues_count)
        open_issues_count_heading = str(issues_count - closed_issues_count)
        issues_count_heading = str(issues_count)
        percentage_closed_heading = '{}%'.format(percentage_closed)
        if colored:
            closed_issues_count_heading = (colored.fg('green') + closed_issues_count_heading + colored.attr('reset'))
            open_issues_count_heading = (colored.fg('red') + open_issues_count_heading + colored.attr('reset'))
            issues_count_heading = (colored.fg('cyan') + issues_count_heading + colored.attr('reset'))
            percentage_closed_heading = (colored.fg('white') + percentage_closed_heading + colored.attr('reset'))
        print('| {closed}/{still_open}/{total} ({perc_closed} closed)'.format(
            closed = closed_issues_count_heading,
            still_open = open_issues_count_heading,
            total = issues_count_heading,
            perc_closed = percentage_closed_heading,
        ))

    if True:
        avg_tags_per_issue = (sum(map(lambda i: len(i.get('tags', [])), issues)) / issues_count)
        print('avg. tags per issue: {0}'.format(round(avg_tags_per_issue, 1)))

    if True:
        if closed_issues_count:
            open_closed_timestamps = list(map(lambda each: (
                datetime.datetime.fromtimestamp(each['close.timestamp']),
                datetime.datetime.fromtimestamp(each['open.timestamp']),
            ), closed_issues))

            current_datetime = datetime.datetime.now()
            still_open_timestamps = list(map(lambda each: (
                current_datetime,
                datetime.datetime.fromtimestamp(each['open.timestamp']),
            ), open_issues))

            lifetimes_of_closed = list(map(lambda each: (each[0] - each[1]), open_closed_timestamps))
            lifetimes_of_still_open = list(map(lambda each: (each[0] - each[1]), still_open_timestamps))

            def sum_or_none_if_empty(seq):
                if not seq:
                    return None
                if len(seq) == 1:
                    return seq[0]
                return sum(seq[1:], seq[0])

            def avg_or_none(seq):
                summed = sum_or_none_if_empty(seq)
                if summed is None:
                    return summed
                return summed / len(seq)

            def median_or_none(seq):
                if not seq:
                    return None
                s = sorted(seq)
                i = len(s) // 2
                if len(s) % 2 == 0:
                    return (s[i - 1] + s[i]) / 2
                else:
                    return s[i]

            total_lifetime_of_closed = sum_or_none_if_empty(lifetimes_of_closed)
            total_lifetime_of_still_open = sum_or_none_if_empty(lifetimes_of_still_open)
            total_lifetime_of_all = sum_or_none_if_empty(lifetimes_of_closed + lifetimes_of_still_open)

            avg_lifetime_of_closed = avg_or_none(lifetimes_of_closed)
            med_lifetime_of_closed = median_or_none(lifetimes_of_closed)
            avg_lifetime_of_still_open = avg_or_none(lifetimes_of_still_open)
            med_lifetime_of_still_open = median_or_none(lifetimes_of_still_open)
            avg_lifetime_of_all = avg_or_none(lifetimes_of_closed + lifetimes_of_still_open)
            med_lifetime_of_all = median_or_none(lifetimes_of_closed + lifetimes_of_still_open)

            if (total_lifetime_of_closed is None) or (total_lifetime_of_still_open is None):
                perc_total_closed_of_open = None
                perc_total_closed_of_all = None
                perc_avg_closed_of_open = None
                perc_avg_closed_of_all = None

                perc_total_open_more_than_closed = None
            else:
                perc_total_closed_of_open = (total_lifetime_of_closed / total_lifetime_of_still_open) * 100
                perc_total_closed_of_all = (total_lifetime_of_closed / total_lifetime_of_all) * 100
                perc_avg_closed_of_open = (avg_lifetime_of_closed / avg_lifetime_of_still_open) * 100
                perc_avg_closed_of_all = (avg_lifetime_of_closed / avg_lifetime_of_all) * 100

                perc_total_open_more_than_closed = (
                    ((total_lifetime_of_still_open / total_lifetime_of_closed) * 100) - 100
                )

            def round_or_none(f, precision):
                if f is None:
                    return None
                return round(f, precision)

            print('lifetime of {} {} issues:'.format(
                len(closed_issues),
                colorise('green', 'closed'),
            ))
            print('    total: {} ({}% of open, {}% of all)'.format(
                total_lifetime_of_closed,
                round_or_none(perc_total_closed_of_open, 2),
                round_or_none(perc_total_closed_of_all, 2),
            ))
            print('    avg:   {} ({}% of open, {}% of all)'.format(
                avg_lifetime_of_closed,
                round_or_none(perc_avg_closed_of_open, 2),
                round_or_none(perc_avg_closed_of_all, 2),
            ))
            print('    med:   {}'.format(
                med_lifetime_of_closed,
            ))

            print('lifetime of {} {} issues:'.format(
                len(open_issues),
                colorise('red', 'open'),
            ))
            print('    total: {} ({}% more than closed)'.format(
                total_lifetime_of_still_open,
                round_or_none(perc_total_open_more_than_closed, 2),
            ))
            print('    avg:   {}'.format(avg_lifetime_of_still_open))
            print('    med:   {}'.format(
                med_lifetime_of_still_open,
            ))

            print('lifetime of {} {} issues:'.format(
                colorise('cyan', 'all'),
                len(issues),
            ))
            print('    total: {}'.format(total_lifetime_of_all))
            print('    avg:   {}'.format(avg_lifetime_of_all))
            print('    med:   {}'.format(
                med_lifetime_of_all,
            ))

def commandReleaseOpen(ui):
    ui = ui.down()
    release_name = ui.operands()[0]
    current_next_release = get_next_release_pointer()
    if current_next_release:
        print('error: a release is currently opened: {}'.format(repr(current_next_release)))
        print('note: only one release can be opened at a time')
        print('note: close release {} before opening new one'.format(current_next_release))
        exit(1)
    if release_name_exists(release_name) and not '--force' in ui:
        print('error: release already exists: {}'.format(repr(release_name)))
        exit(1)
    release_base_path = get_release_path(release_name)
    os.makedirs(release_base_path, exist_ok=True)
    os.makedirs(os.path.join(release_base_path, 'diff'), exist_ok=True)

    store_release_diff_open(release_name)
    store_next_release_pointer(release_name)

def commandReleaseClose(ui):
    ui = ui.down()
    release_name = ui.operands()[0]
    current_next_release = get_next_release_pointer()
    if current_next_release and release_name == '-':
        release_name = current_next_release
    if release_name != current_next_release:
        print('error: not an opened release: {}'.format(release_name))
        if current_next_release:
            print('note: {} is the currently opened release'.format(current_next_release))
        else:
            print('note: no release is currently opened')
        exit(1)
    release_notes = ''
    if '--message' in ui:
        release_notes = ui.get('-m').strip()
    if not release_notes:
        release_notes = getMessage('release_notes_message', fmt={'release_name': release_name}, ignore='%%')
    if not release_notes:
        print('error: aborting due to empty release notes')
        exit(1)

    with open(get_release_notes_path(release_name), 'w') as ofstream:
        ofstream.write(release_notes)

    store_release_diff_close(release_name)
    store_next_release_pointer('')

def commandReleaseLs(ui):
    ui = ui.down()
    print('\n'.join(sorted(os.listdir(os.path.join(issue.util.paths.releases_path(), 'r')))))

def commandReleaseNotes(ui):
    ui = ui.down()
    release_name = ui.operands()[0]
    if not release_name_exists(release_name):
        print('error: release does not exist: {}'.format(repr(release_name)))
        exit(1)
    if '--closed' not in ui and '--opened' not in ui:
        pager = os.getenv('PAGER', 'less')
        os.system('{} {}'.format(pager, get_release_notes_path(release_name)))
        return
    release_diffs = get_release_diffs(release_name)
    opened_issues = filter(lambda _: _['action'] == 'open-issue', release_diffs)
    closed_issues = filter(lambda _: _['action'] == 'close-issue', release_diffs)
    if '--opened' in ui:
        if '--closed' in ui:
            print('opened issues:')
        for i in opened_issues:
            print('{} {}'.format(i['params']['id'], i['params']['message']))
        if not opened_issues:
            print('no opened issues')
    if '--opened' in ui and '--closed' in ui:
        print()
    if '--closed' in ui:
        if '--opened' in ui:
            print('closed issues:')
        for i in closed_issues:
            print('{}'.format(i['params']['id']))
        if not closed_issues:
            print('no closed issues')

def commandRelease(ui):
    ui = ui.down()
    if str(ui) == 'open':
        commandReleaseOpen(ui)
    elif str(ui) == 'close':
        commandReleaseClose(ui)
    elif str(ui) == 'ls':
        commandReleaseLs(ui)
    elif str(ui) == 'notes':
        commandReleaseNotes(ui)

def commandLog(ui):
    ui = ui.down()
    events_log = issue.shortlog.read()
    events_log = issue.shortlog.sort(events_log)

    if str(ui) == 'squash':
        initial_size = len(events_log)
        if initial_size < 2:
            print('{}: events_log too short to shorten'.format(colorise(COLOR_WARNING, 'warning')))
            return
        squashed_events_log = issue.shortlog.squash_events_log(
            events_log,
            aggressive = ui.get('--aggressive'),
        )
        final_size = len(squashed_events_log)
        if final_size < initial_size:
            print('{}: shortened events_log from {} to {} entries'.format(colorise(COLOR_NOTE, 'note'), initial_size, final_size))
        issue.shortlog.write(squashed_events_log)
        if '--verbose' in ui:
            display_events_log(squashed_events_log)
    else:
        head = None
        tail = None
        if '--head' in ui:
            head = ui.get('-H')
        if '--tail' in ui:
            tail = ui.get('-T')
        display_events_log(events_log, head=head, tail=tail)


def dispatch(ui, *commands, overrides = {}, default_command=''):
    """Semi-automatic command dispatcher.

    Functions passed to `*commands` parameter should be named like `commandFooBarBaz` because
    of command name mangling.
    Example: `foo-bar-baz` is transformed to `FooBarBaz` and handled with `commandFooBarBaz`.

    It is possible to override a command handler by passing it inside the `overrides` parameter.

    This scheme can be effectively used to support command auto-dispatch with minimal manual guidance by
    providing sane defaults and a way of overriding them when needed.
    """
    ui_command = (str(ui) or default_command)
    if not ui_command:
        return
    try:
        if ui_command in overrides:
            overrides[ui_command](ui)
        else:
            ui_command = ('command' + ''.join([(s[0].upper() + s[1:]) for s in ui_command.split('-')]))
            for cmd in commands:
                if cmd.__name__ == ui_command:
                    cmd(ui)
                    break
    except issue.exceptions.RepositoryNotFound:
        print('{}: not an issue repository (or any of the parent directories): {}'.format(
            colorise(COLOR_ERROR, 'error'),
            os.path.abspath(issue.util.paths.get_repository_path(safe = True)),
        ))


dispatch(ui,        # first: pass the UI object to dispatch
    commandInit,    # second: pass command handling functions
    commandOpen,
    commandClose,
    commandLs,
    commandDrop,
    commandSlug,
    commandComment,
    commandTag,
    commandParam,
    commandShow,
    commandConfig,
    commandRemote,
    commandPull,
    commandPush,
    commandIndex,
    commandClone,
    commandChain,
    commandStatistics,
    commandRelease,
    commandLog,
)
