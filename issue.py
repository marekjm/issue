#!/usr/bin/env python3

import hashlib
import json
import os
import random
import shutil
import sys

import clap


__version__ = '0.0.0'


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
REPOSITORY_PATH = './.issue'
OBJECTS_PATH = os.path.join(REPOSITORY_PATH, 'objects')
ISSUES_PATH = os.path.join(OBJECTS_PATH, 'issues')
DROPPED_ISSUES_PATH = os.path.join(OBJECTS_PATH, 'dropped')
LABELS_PATH = os.path.join(OBJECTS_PATH, 'labels')
MILESTONES_PATH = os.path.join(OBJECTS_PATH, 'milestones')


# exception definitions
class IssueException(Exception):
    pass

# utility functions
def getIssue(issue_sha1):
    issue_group = issue_sha1[:2]
    issue_file_path = os.path.join(ISSUES_PATH, issue_group, '{0}.json'.format(issue_sha1))
    issue_data = {}
    with open(issue_file_path, 'r') as ifstream:
        issue_data = json.loads(ifstream.read())
    return issue_data

def saveIssue(issue_sha1, issue_data):
    issue_group = issue_sha1[:2]
    issue_file_path = os.path.join(ISSUES_PATH, issue_group, '{0}.json'.format(issue_sha1))
    with open(issue_file_path, 'w') as ofstream:
        ofstream.write(json.dumps(issue_data))

def dropIssue(issue_sha1):
    issue_group_path = os.path.join(DROPPED_ISSUES_PATH, issue_sha1[:2])
    if not os.path.isdir(issue_group_path):
        os.mkdir(issue_group_path)

    issue_file_path = os.path.join(ISSUES_PATH, issue_sha1[:2], '{0}.json'.format(issue_sha1))
    dropped_issue_file_path = os.path.join(DROPPED_ISSUES_PATH, issue_sha1[:2], '{0}.json'.format(issue_sha1))
    shutil.copy(issue_file_path, dropped_issue_file_path)
    os.unlink(issue_file_path)


ui = ui.down() # go down a mode
operands = ui.operands()

if str(ui) not in ('init', 'help', '') and not os.path.isdir(REPOSITORY_PATH):
    print('fatal: not inside issues repository')
    exit(1)

if str(ui) == 'init':
    if '--force' in ui and os.path.isdir(REPOSITORY_PATH):
        shutil.rmtree(REPOSITORY_PATH)
    if os.path.isdir(REPOSITORY_PATH):
        print('fatal: repository already exists')
        exit(1)
    for pth in (REPOSITORY_PATH, OBJECTS_PATH, ISSUES_PATH, DROPPED_ISSUES_PATH, LABELS_PATH, MILESTONES_PATH):
        if not os.path.isdir(pth):
            os.mkdir(pth)
elif str(ui) == 'open':
    message = ''
    if len(operands) < 1:
        message = input('issue description: ')
    else:
        message = operands[0]
    labels = ([l[0] for l in ui.get('--label')] if '--label' in ui else [])
    milestones = ([m[0] for m in ui.get('--milestone')] if '--milestone' in ui else [])

    issue_sha1 = '{0}{1}{2}{3}'.format(message, labels, milestones, random.random())
    issue_sha1 = hashlib.sha1(issue_sha1.encode('utf-8')).hexdigest()
    print(issue_sha1)

    issue_data = {
        'message': message,
        'comments': {},
        'labels': labels,
        'milestones': milestones,
        'status': 'open',
        '_meta': {}
    }

    issue_group_path = os.path.join(ISSUES_PATH, issue_sha1[:2])
    if not os.path.isdir(issue_group_path):
        os.mkdir(issue_group_path)

    issue_file_path = os.path.join(issue_group_path, '{0}.json'.format(issue_sha1))
    with open(issue_file_path, 'w') as ofstream:
        ofstream.write(json.dumps(issue_data))
elif str(ui) == 'close':
    for i in operands:
        issue_data = getIssue(i)
        issue_data['status'] = 'closed'
        saveIssue(i, issue_data)
elif str(ui) == 'ls':
    groups = os.listdir(ISSUES_PATH)
    issues = []
    for g in groups:
        if g == 'dropped': continue
        issues.extend(os.listdir(os.path.join(ISSUES_PATH, g)))

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
        print('{0}: {1}'.format(issue_sha1, issue_data['message']))
elif str(ui) == 'drop':
    print(operands)
    for i in operands:
        dropIssue(i)
elif str(ui) == 'slug':
    issue_data = getIssue(operands[0])
    issue_message = issue_data['message']
    issue_slug = '-'.join(issue_message.lower().replace('/', ' ').split())
    if '--git' in ui:
        issue_slug = 'issue/{0}'.format(issue_slug)
    if '--format' in ui:
        issue_slug = ui.get('--format').format(issue_slug)
    print(issue_slug)
