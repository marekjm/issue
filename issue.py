#!/usr/bin/env python3

import datetime
import hashlib
import json
import os
import random
import re
import shutil
import subprocess
import sys

import unidecode

import clap


__version__ = '0.1.1'


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
except Exception as e:
    print('fatal: unhandled exception: {0}: {1}'.format(str(type(e))[8:-2], e))
    fail, err = True, e
finally:
    if fail: exit(1)
    ui = parser.parse().ui().finalise()


if '--version' in ui:
    print('issue version {0}'.format(__version__))
    exit(0)
if clap.helper.HelpRunner(ui=ui, program=sys.argv[0]).adjust(options=['-h', '--help']).run().displayed(): exit(0)



# ensure the repository exists
REPOSITORY_PATH = '.issue'
OBJECTS_PATH = os.path.join(REPOSITORY_PATH, 'objects')
ISSUES_PATH = os.path.join(OBJECTS_PATH, 'issues')
LABELS_PATH = os.path.join(OBJECTS_PATH, 'labels')
MILESTONES_PATH = os.path.join(OBJECTS_PATH, 'milestones')
PACK_PATH = os.path.join(REPOSITORY_PATH, 'pack.json')
REMOTE_PACK_PATH = os.path.join(REPOSITORY_PATH, 'remote_pack.json')


# exception definitions
class IssueException(Exception):
    pass

class NotAnIssue(IssueException):
    pass

class IssueUIDNotMatched(IssueException):
    pass

class IssueUIDAmbiguous(IssueException):
    pass


# utility functions
def getIssue(issue_sha1):
    issue_group = issue_sha1[:2]
    issue_file_path = os.path.join(ISSUES_PATH, issue_group, '{0}.json'.format(issue_sha1))
    issue_data = {}
    try:
        with open(issue_file_path, 'r') as ifstream:
            issue_data = json.loads(ifstream.read())

        issue_comments_dir = os.path.join(ISSUES_PATH, issue_group, issue_sha1, 'comments')
        issue_data['comments'] = {}
        for cmt in os.listdir(issue_comments_dir):
            with open(os.path.join(issue_comments_dir, cmt)) as ifstream:
                issue_data['comments'][cmt.split('.')[0]] = json.loads(ifstream.read())
    except FileNotFoundError as e:
        raise NotAnIssue(issue_file_path)
    return issue_data

def saveIssue(issue_sha1, issue_data):
    issue_group = issue_sha1[:2]
    issue_file_path = os.path.join(ISSUES_PATH, issue_group, '{0}.json'.format(issue_sha1))
    if 'comments' in issue_data:
        del issue_data['comments']
    with open(issue_file_path, 'w') as ofstream:
        ofstream.write(json.dumps(issue_data))

def dropIssue(issue_sha1):
    issue_group_path = os.path.join(ISSUES_PATH, issue_sha1[:2])
    issue_file_path = os.path.join(issue_group_path, '{0}.json'.format(issue_sha1))
    os.unlink(issue_file_path)
    shutil.rmtree(os.path.join(issue_group_path, issue_sha1))

def sluggify(issue_message):
    return '-'.join(re.compile('[^ a-z]').sub(' ', unidecode.unidecode(issue_message).lower()).split())

def getConfig():
    config_data = {}
    config_path_global = os.path.expanduser('~/.issueconfig.json')
    config_path_local = './.issue/config.json'
    if os.path.isfile(config_path_global):
        with open(config_path_global, 'r') as ifstream:
            config_data = json.loads(ifstream.read())
    if os.path.isfile(config_path_local):
        with open(config_path_local, 'r') as ifstream:
            for k, v in json.loads(ifstream.read()).items():
                config_data[k] = v
    return config_data

def getRemotes():
    remotes = {}
    remotes_path = os.path.join(REPOSITORY_PATH, 'remotes.json')
    if os.path.isfile(remotes_path):
        with open(remotes_path) as ifstream:
            remotes = json.loads(ifstream.read())
    return remotes

def saveRemotes(remotes):
    remotes_path = os.path.join(REPOSITORY_PATH, 'remotes.json')
    with open(remotes_path, 'w') as ofstream:
        ofstream.write(json.dumps(remotes))

def getPack():
    pack_data = {
        'issues': [],
        'comments': {},
    }

    pack_issue_list = listIssues()
    pack_data['issues'] = pack_issue_list

    pack_comments = {}
    for p in pack_issue_list:
        pack_comments_path = os.path.join(ISSUES_PATH, p[:2], p, 'comments')
        pack_comments[p] = [sp.split('.')[0] for sp in os.listdir(pack_comments_path)]
    pack_data['comments'] = pack_comments

    return pack_data

def listIssues():
    list_of_issues = []
    groups = os.listdir(ISSUES_PATH)
    for g in groups:
        list_of_issues.extend([p for p in os.listdir(os.path.join(ISSUES_PATH, g)) if not p.endswith('.json')])
    return list_of_issues

def expandIssueUID(issue_sha1_part):
    issue_sha1 = []
    issues = listIssues()
    for i_sha1 in issues:
        if i_sha1.startswith(issue_sha1_part): issue_sha1.append(i_sha1)
    if len(issue_sha1) == 0:
        raise IssueUIDNotMatched(issue_sha1_part)
    if len(issue_sha1) > 1:
        raise IssueUIDAmbiguous(issue_sha1_part)
    return issue_sha1[0]

def runShell(*command):
    p = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output, error = p.communicate()
    output = output.decode('utf-8').strip()
    error = error.decode('utf-8').strip()
    exit_code = p.wait()
    return (exit_code, output, error)


ui = ui.down() # go down a mode
operands = ui.operands()

if str(ui) not in ('init', 'help') and '--nuke' not in ui and not os.path.isdir(REPOSITORY_PATH):
    while not os.path.isdir(REPOSITORY_PATH) and os.path.abspath(REPOSITORY_PATH) != '/.issue':
        REPOSITORY_PATH = os.path.join('..', REPOSITORY_PATH)
    REPOSITORY_PATH = os.path.abspath(REPOSITORY_PATH)
    if REPOSITORY_PATH == '/.issue':
        print('fatal: not inside issues repository')
        exit(1)
    OBJECTS_PATH = os.path.join(REPOSITORY_PATH, 'objects')
    ISSUES_PATH = os.path.join(OBJECTS_PATH, 'issues')
    LABELS_PATH = os.path.join(OBJECTS_PATH, 'labels')
    MILESTONES_PATH = os.path.join(OBJECTS_PATH, 'milestones')
    PACK_PATH = os.path.join(REPOSITORY_PATH, 'pack.json')
    REMOTE_PACK_PATH = os.path.join(REPOSITORY_PATH, 'remote_pack.json')


if '--pack' in ui:
    print('packing objects:')
    pack_data = getPack()

    print('  * issues  ', end='')
    print(' [{0} object(s)]'.format(len(pack_data['issues'])))

    print('  * comments', end='')
    print(' [{0} object(s)]'.format(sum([len(pack_data['comments'][n]) for n in pack_data['comments'].keys()])))

    with open(PACK_PATH, 'w') as ofstream:
        ofstream.write(json.dumps(pack_data))

    exit(0)

if '--nuke' in ui:
    repository_exists = os.path.isdir(REPOSITORY_PATH)
    if not repository_exists and ui.get('--nuke') <= 1:
        print('fatal: cannot remove nonexistent repository')
        exit(1)
    if repository_exists:
        shutil.rmtree(REPOSITORY_PATH)
    exit(0)

if '--where' in ui:
    print(REPOSITORY_PATH)
    exit(0)


def commandInit(ui):
    if '--force' in ui and os.path.isdir(REPOSITORY_PATH):
        shutil.rmtree(REPOSITORY_PATH)
    if os.path.isdir(REPOSITORY_PATH):
        print('fatal: repository already exists')
        exit(1)
    for pth in (REPOSITORY_PATH, OBJECTS_PATH, ISSUES_PATH, LABELS_PATH, MILESTONES_PATH):
        if not os.path.isdir(pth):
            os.mkdir(pth)

def commandOpen(ui):
    message = ''
    if len(operands) < 1:
        editor = os.getenv('EDITOR', 'vi')
        message_path = os.path.join(REPOSITORY_PATH, 'message')
        shutil.copy(os.path.expanduser('~/.local/share/issue/issue_message'), message_path)
        os.system('{0} {1}'.format(editor, message_path))
        with open(message_path) as ifstream:
            message_lines = ifstream.readlines()
            message = ''.join([l for l in message_lines if not l.startswith('#')]).strip()
    else:
        message = operands[0]

    if not message:
        print('fatal: aborting due to empty message')
        exit(1)

    labels = ([l[0] for l in ui.get('--label')] if '--label' in ui else [])
    milestones = ([m[0] for m in ui.get('--milestone')] if '--milestone' in ui else [])

    issue_sha1 = '{0}{1}{2}{3}'.format(message, labels, milestones, random.random())
    issue_sha1 = hashlib.sha1(issue_sha1.encode('utf-8')).hexdigest()

    repo_config = getConfig()

    issue_data = {
        'message': message,
        'labels': labels,
        'milestones': milestones,
        'status': 'open',
        'open.author.email': repo_config['author.email'],
        'open.author.name': repo_config['author.name'],
        'open.timestamp': datetime.datetime.now().timestamp(),
        '_meta': {}
    }

    issue_group_path = os.path.join(ISSUES_PATH, issue_sha1[:2])
    if not os.path.isdir(issue_group_path):
        os.mkdir(issue_group_path)

    issue_file_path = os.path.join(issue_group_path, '{0}.json'.format(issue_sha1))
    with open(issue_file_path, 'w') as ofstream:
        ofstream.write(json.dumps(issue_data))

    # make directories for issue-specific objects
    os.mkdir(os.path.join(issue_group_path, issue_sha1))
    os.mkdir(os.path.join(issue_group_path, issue_sha1, 'comments'))

    if '--git' in ui:
        print('issue/{0}'.format(sluggify(message)))
    else:
        print(issue_sha1)

def commandClose(ui):
    repo_config = getConfig()
    for issue_sha1 in operands:
        try:
            issue_sha1 = expandIssueUID(issue_sha1)
        except IssueUIDAmbiguous:
            print('fail: issue uid {0} is ambiguous'.format(issue_sha1))
            continue
        issue_data = getIssue(issue_sha1)
        issue_data['status'] = 'closed'
        issue_data['close.author.email'] = repo_config['author.email']
        issue_data['close.author.name'] = repo_config['author.name']
        issue_data['close.timestamp'] = datetime.datetime.now().timestamp()
        if '--git-commit' in ui:
            issue_data['closing_git_commit'] = ui.get('--git-commit')
        saveIssue(issue_sha1, issue_data)

def commandLs(ui):
    groups = os.listdir(ISSUES_PATH)
    issues = listIssues()

    accepted_statuses = []
    if '--status' in ui:
        accepted_statuses = [s[0] for s in ui.get('--status')]
    accepted_labels = []
    if '--label' in ui:
        accepted_labels = [s[0] for s in ui.get('--label')]
    for i in issues:
        issue_sha1 = i.split('.', 1)[0]
        issue_data = getIssue(issue_sha1)
        if '--open' in ui and (issue_data['status'] if 'status' in issue_data else '') not in ('open', ''): continue
        if '--closed' in ui and (issue_data['status'] if 'status' in issue_data else '') != 'closed': continue
        if '--status' in ui and (issue_data['status'] if 'status' in issue_data else '') not in accepted_statuses: continue
        if '--label' in ui:
            labels_match = False
            for l in (issue_data['labels'] if 'labels' in issue_data else []):
                if l in accepted_labels:
                    labels_match = True
                    break
            if not labels_match:
                continue
        if '--details' in ui:
            print('{0}: {1}'.format(issue_sha1, issue_data['message']))
            print('    milestones: {0}'.format(', '.join(issue_data['milestones'])))
            print('    labels:     {0}'.format(', '.join(issue_data['labels'])))
            print()
        else:
            print('{0}: {1}'.format(issue_sha1, issue_data['message'].splitlines()[0]))

def commandDrop(ui):
    for issue_sha1 in operands:
        try:
            dropIssue(expandIssueUID(issue_sha1))
        except IssueUIDAmbiguous:
            print('fail: issue uid {0} is ambiguous'.format(issue_sha1))

def commandSlug(ui):
    issue_data = {}
    issue_sha1 = operands[0]
    try:
        issue_data = getIssue(expandIssueUID(issue_sha1))
    except IssueUIDAmbiguous:
        print('fail: issue uid {0} is ambiguous'.format(issue_sha1))
        exit(1)
    issue_message = issue_data['message'].splitlines()[0].strip()
    issue_slug = sluggify(issue_message)
    if '--git' in ui:
        issue_slug = 'issue/{0}'.format(issue_slug)
    if '--format' in ui:
        issue_slug = ui.get('--format').format(slug=issue_slug, **dict(ui.get('--param')))
    print(issue_slug)

def commandComment(ui):
    issue_sha1 = operands[0]
    try:
        issue_sha1 = expandIssueUID(issue_sha1)
    except IssueUIDAmbiguous:
        print('fail: issue uid {0} is ambiguous'.format(issue_sha1))
        exit(1)

    issue_data = getIssue(issue_sha1)

    issue_comment = ''
    if len(operands) < 2:
        editor = os.getenv('EDITOR', 'vi')
        message_path = os.path.join(REPOSITORY_PATH, 'message')
        default_message_text = ''
        with open(os.path.expanduser('~/.local/share/issue/issue_comment_message')) as ifstream:
            default_message_text = ifstream.read()
        with open(message_path, 'w') as ofstream:
            ofstream.write(default_message_text.format(issue_sha1=issue_sha1, issue_message='\n'.join(['#  > {0}'.format(l) for l in issue_data['message'].splitlines()])))
        os.system('{0} {1}'.format(editor, message_path))
        with open(message_path) as ifstream:
            issue_comment_lines = ifstream.readlines()
            issue_comment = ''.join([l for l in issue_comment_lines if not l.startswith('#')]).strip()
    else:
        issue_comment = operands[1]

    if not issue_comment:
        print('fatal: aborting due to empty message')
        exit(1)

    issue_comment_timestamp = datetime.datetime.now().timestamp()
    issue_comment_sha1 = hashlib.sha1(str('{0}{1}{2}'.format(issue_sha1, issue_comment_timestamp, issue_comment)).encode('utf-8')).hexdigest()
    issue_comment_data = {
        'message': issue_comment,
        'timestamp': issue_comment_timestamp,
    }
    config_data = getConfig()
    issue_comment_data = {
        'author.name': config_data['author.name'],
        'author.email': config_data['author.email'],
        'message': issue_comment,
        'timestamp': issue_comment_timestamp,
    }
    with open(os.path.join(ISSUES_PATH, issue_sha1[:2], issue_sha1, 'comments', '{0}.json'.format(issue_comment_sha1)), 'w') as ofstream:
        ofstream.write(json.dumps(issue_comment_data))

def commandShow(ui):
    issue_sha1 = operands[0]
    try:
        issue_sha1 = expandIssueUID(issue_sha1)
    except IssueUIDAmbiguous:
        print('fail: issue uid {0} is ambiguous'.format(issue_sha1))
        exit(1)

    issue_data = {}
    try:
        issue_data = getIssue(issue_sha1)
    except NotAnIssue as e:
        print('fatal: {0} does not identify a valid object'.format(repr(issue_sha1)))
        exit(1)

    issue_message_lines = issue_data['message'].splitlines()

    issue_open_author_name = (issue_data['open.author.name'] if 'open.author.name' in issue_data else 'Unknown Author')
    issue_open_author_email = (issue_data['open.author.email'] if 'open.author.email' in issue_data else 'Unknown email')
    issue_open_timestamp = (datetime.datetime.fromtimestamp(issue_data['open.timestamp']) if 'open.timestamp' in issue_data else 'unknown date')
    print('{0}: {1}'.format(issue_sha1, issue_message_lines[0]))
    print('    opened by:  {0} ({1}), on {2}'.format(issue_open_author_name, issue_open_author_email, issue_open_timestamp))
    if issue_data['status'] == 'closed':
        issue_close_author_name = (issue_data['close.author.name'] if 'close.author.name' in issue_data else 'Unknown Author')
        issue_close_author_email = (issue_data['close.author.email'] if 'close.author.email' in issue_data else 'Unknown email')
        issue_close_timestamp = (datetime.datetime.fromtimestamp(issue_data['close.timestamp']) if 'close.timestamp' in issue_data else 'unknown date')
        print('    closed by:  {0} ({1}), on {2}'.format(issue_close_author_name, issue_close_author_email, issue_close_timestamp))
    print('    milestones: {0}'.format(', '.join(issue_data['milestones'])))
    print('    labels:     {0}'.format(', '.join(issue_data['labels'])))

    print('\n---- MESSAGE')
    print('\n  {0}\n'.format('\n  '.join(issue_message_lines)))

    if 'closing_git_commit' in issue_data:
        print('\n---- CLOSING GIT COMMIT: {0}\n'.format(issue_data['closing_git_commit']))

    issue_comment_thread = dict((issue_data['comments'][key]['timestamp'], key) for key in issue_data['comments'])
    if issue_comment_thread:
        print('\n---- COMMENT THREAD:\n')
        for i, timestamp in enumerate(sorted(issue_comment_thread.keys())):
            issue_comment = issue_data['comments'][issue_comment_thread[timestamp]]
            print('>>>> {0}. {1} ({2}) at {3}\n'.format(i, issue_comment['author.name'], issue_comment['author.email'], datetime.datetime.fromtimestamp(issue_comment['timestamp'])))
            print(issue_comment['message'])
            print()

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
            print(('{0} => {1}' if '--verbose' in ui else '{0}').format(k, remote_data['url']))
    elif str(ui) == 'set':
        remote_name = operands[0]
        if remote_name not in remotes:
            remotes[remote_name] = {}
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

def commandFetch(ui):
    ui = ui.down()
    local_pack = getPack()
    remotes = getRemotes()
    fetch_from_remotes = (ui.operands() or sorted(remotes.keys()))
    for remote_name in fetch_from_remotes:
        print('fetching objects from remote: {0}'.format(remote_name))
        remote_pack_fetch_command = ('scp', '{0}/pack.json'.format(remotes[remote_name]['url']), REMOTE_PACK_PATH)
        exit_code, output, error = runShell(*remote_pack_fetch_command)

        if exit_code:
            print('  * fail ({0}): {1}'.format(exit_code, error))
            continue

        remote_pack = {}
        with open(REMOTE_PACK_PATH) as ifstream:
            remote_pack = json.loads(ifstream.read())

        new_issues = set(remote_pack['issues']) - set(local_pack['issues'])
        # print(new_issues)

        new_comments = {}
        for k, v in remote_pack['comments'].items():
            if k in local_pack['comments']:
                new_comments[k] = set(remote_pack['comments'][k]) - set(local_pack['comments'][k])
            else:
                new_comments[k] = remote_pack['comments'][k]
        # print(new_comments)
        print('  * issues:   {0} object(s)'.format(len(new_issues)))
        print('  * comments: {0} object(s)'.format(sum([len(new_comments[k]) for k in new_comments])))

        if '--probe' in ui:
            continue

        for issue_sha1 in new_issues:
            issue_group_path = os.path.join(ISSUES_PATH, issue_sha1[:2])
            if not os.path.isdir(issue_group_path):
                os.mkdir(issue_group_path)

            exit_code, output, error = runShell(
                'scp',
                '{0}/objects/issues/{1}/{2}.json'.format(remotes[remote_name]['url'], issue_sha1[:2], issue_sha1),
                os.path.join(ISSUES_PATH, issue_sha1[:2], '{0}.json'.format(issue_sha1))
            )

            if exit_code:
                print('  * fail ({0}): issue {1}: {2}'.format(exit_code, issue_sha1, error))
                continue

            # make directories for issue-specific objects
            os.mkdir(os.path.join(issue_group_path, issue_sha1))
            os.mkdir(os.path.join(issue_group_path, issue_sha1, 'comments'))

        for issue_sha1 in new_comments:
            if not new_comments[issue_sha1]:
                continue

            for cmt_sha1 in new_comments[issue_sha1]:
                exit_code, output, error = runShell(
                    'scp',
                    '{0}/objects/issues/{1}/{2}/comments/{3}.json'.format(
                        remotes[remote_name]['url'],
                        issue_sha1[:2],
                        issue_sha1,
                        cmt_sha1,
                    ),
                    os.path.join(ISSUES_PATH, issue_sha1[:2], issue_sha1, 'comments', '{0}.json'.format(cmt_sha1))
                )

                if exit_code:
                    print('  * fail ({0}): comment {1}.{2}: {3}'.format(exit_code, issue_sha1, cmt_sha1, error))
                    continue


def dispatch(ui, *commands, overrides = {}):
    """Semi-automatic command dispatcher.

    Functions passed to `*commands` parameter should be named like `commandFooBarBaz` because
    of command name mangling.
    Example: `foo-bar-baz` is transformed to `FooBarBaz` and handled with `commandFooBarBaz`.

    It is possible to override a command handler by passing it inside the `overrides` parameter.

    This scheme can be effectively used to support command auto-dispatch with minimal manual guidance by
    providing sane defaults and a way of overriding them when needed.
    """
    ui_command = str(ui)
    if ui_command in overrides:
        overrides[ui_command](ui)
    else:
        ui_command = ('command' + ''.join([(s[0].upper() + s[1:]) for s in ui_command.split('-')]))
        for cmd in commands:
            if cmd.__name__ == ui_command:
                cmd(ui)
                break


dispatch(ui,        # first: pass the UI object to dispatch
    commandInit,    # second: pass command handling functions
    commandOpen,
    commandClose,
    commandLs,
    commandDrop,
    commandSlug,
    commandComment,
    commandShow,
    commandConfig,
    commandRemote,
    commandFetch,
)
