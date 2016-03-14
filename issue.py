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
except Exception as e:
    print('fatal: unhandled exception: {0}: {1}'.format(str(type(e))[8:-2], e))
    fail, err = True, e
finally:
    if fail: exit(1)
    ui = parser.parse().ui().finalise()


if '--version' in ui:
    print('issue version {0}'.format(issue.__version__))
    exit(0)
if clap.helper.HelpRunner(ui=ui, program=sys.argv[0]).adjust(options=['-h', '--help']).run().displayed(): exit(0)



# ensure the repository exists
REPOSITORY_PATH = '.issue'
OBJECTS_PATH = os.path.join(REPOSITORY_PATH, 'objects')
REPOSITORY_TMP_PATH = os.path.join(REPOSITORY_PATH, 'tmp')
ISSUES_PATH = os.path.join(OBJECTS_PATH, 'issues')
TAGS_PATH = os.path.join(OBJECTS_PATH, 'tags')
MILESTONES_PATH = os.path.join(OBJECTS_PATH, 'milestones')
PACK_PATH = os.path.join(REPOSITORY_PATH, 'pack.json')
REMOTE_PACK_PATH = os.path.join(REPOSITORY_PATH, 'remote_pack.json')
LAST_ISSUE_PATH = os.path.join(REPOSITORY_PATH, 'last')

LS_KEYWORD_MATCH_THRESHOLD = 1


# issue-related utility functions
def getIssue(issue_sha1, index=False):
    if index:
        indexIssue(issue_sha1)
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
        if os.path.isdir(os.path.join(ISSUES_PATH, issue_group, issue_sha1)):
            raise issue.exceptions.NotIndexed(issue_file_path)
        else:
            raise issue.exceptions.NotAnIssue(issue_file_path)
    return issue_data

def saveIssue(issue_sha1, issue_data):
    issue_group = issue_sha1[:2]
    issue_file_path = os.path.join(ISSUES_PATH, issue_group, '{0}.json'.format(issue_sha1))
    if 'comments' in issue_data:
        del issue_data['comments']
    with open(issue_file_path, 'w') as ofstream:
        ofstream.write(json.dumps(issue_data))

def listIssueDifferences(issue_sha1):
    issue_group = issue_sha1[:2]
    issue_diffs_path = os.path.join(ISSUES_PATH, issue_group, issue_sha1, 'diff')
    return [k.split('.')[0] for k in os.listdir(issue_diffs_path)]

def getIssueDifferences(issue_sha1, *diffs):
    issue_differences = []
    issue_diff_path = os.path.join(ISSUES_PATH, issue_sha1[:2], issue_sha1, 'diff')
    for d in diffs:
        issue_diff_file_path = os.path.join(issue_diff_path, '{0}.json'.format(d))
        with open(issue_diff_file_path) as ifstream:
            issue_differences.extend(json.loads(ifstream.read()))
    return issue_differences

def sortIssueDifferences(issue_differences):
    issue_differences_sorted = []
    issue_differences_order = {}
    for i, d in enumerate(issue_differences):
        if d['timestamp'] not in issue_differences_order:
            issue_differences_order[d['timestamp']] = []
        issue_differences_order[d['timestamp']].append(i)
    issue_differences_sorted = []
    for ts in sorted(issue_differences_order.keys()):
        issue_differences_sorted.extend([issue_differences[i] for i in issue_differences_order[ts]])
    return issue_differences_sorted

def indexIssue(issue_sha1, *diffs):
    issue_data = {}
    issue_file_path = os.path.join(ISSUES_PATH, issue_sha1[:2], '{0}.json'.format(issue_sha1))
    if os.path.isfile(issue_file_path) and diffs:
        with open(issue_file_path) as ifstream:
            issue_data = json.loads(ifstream.read())

    issue_differences = (diffs or listIssueDifferences(issue_sha1))
    issue_differences = getIssueDifferences(issue_sha1, *issue_differences)

    issue_differences_sorted = sortIssueDifferences(issue_differences)

    issue_work_started = {}
    issue_work_in_progress_time_deltas = []
    for d in issue_differences_sorted:
        diff_datetime = datetime.datetime.fromtimestamp(d['timestamp'])
        diff_action = d['action']
        if diff_action == 'open':
            issue_data['status'] = 'open'
            issue_data['open.author.name'] = d['author']['author.name']
            issue_data['open.author.email'] = d['author']['author.email']
            issue_data['open.timestamp'] = d['timestamp']
        elif diff_action == 'close':
            issue_data['status'] = 'closed'
            issue_data['close.author.name'] = d['author']['author.name']
            issue_data['close.author.email'] = d['author']['author.email']
            issue_data['close.timestamp'] = d['timestamp']
            if 'closing_git_commit' in d['params'] and d['params']['closing_git_commit']:
                issue_data['closing_git_commit'] = d['params']['closing_git_commit']
        elif diff_action == 'set-message':
            issue_data['message'] = d['params']['text']
        # support both -tags and -labels ("labels" name has been used in pre-0.1.5 versions)
        # FIXME: this support should be removed after early repositories are converted
        elif diff_action == 'push-tags' or diff_action == 'push-labels':
            if 'tags' not in issue_data:
                issue_data['tags'] = []
            issue_data['tags'].extend(d['params'][('tags' if 'tags' in d['params'] else 'labels')])
        # support both -tags and -labels ("labels" name has been used in pre-0.1.5 versions)
        # FIXME: this support should be removed after early repositories are converted
        elif diff_action == 'remove-tags' or diff_action == 'remove-labels':
            if 'tags' not in issue_data:
                issue_data['tags'] = []
            for l in d['params'][('tags' if 'tags' in d['params'] else 'labels')]:
                issue_data['tags'].remove(l)
        elif diff_action == 'parameter-set':
            if 'parameters' not in issue_data:
                issue_data['parameters'] = {}
            issue_data['parameters'][d['params']['key']] = d['params']['value']
        elif diff_action == 'parameter-remove':
            if 'parameters' not in issue_data:
                issue_data['parameters'] = {}
            del issue_data['parameters'][d['params']['key']]
        elif diff_action == 'push-milestones':
            if 'milestones' not in issue_data:
                issue_data['milestones'] = []
            issue_data['milestones'].extend(d['params']['milestones'])
        elif diff_action == 'set-status':
            issue_data['status'] = d['params']['status']
        elif diff_action == 'set-project-tag':
            issue_data['project.tag'] = d['params']['tag']
        elif diff_action == 'set-project-name':
            issue_data['project.name'] = d['params']['name']
        elif diff_action == 'work-start':
            # FIXME: for now, if several 'work-start' events follow each other make the next one end
            # the preceding one and set it as new start timestamp
            # this should not happen - "work start" should check if there is an unmatched 'work-start' event
            # and complain
            if issue_work_started.get(d['author']['author.email']) is not None:
                issue_work_in_progress_time_deltas.append((datetime.datetime.fromtimestamp(d['params']['timestamp']) - issue_work_started[d['author']['author.email']]))
            issue_work_started[d['author']['author.email']] = datetime.datetime.fromtimestamp(d['params']['timestamp'])
        elif diff_action == 'work-stop':
            if issue_work_started.get(d['author']['author.email']) is not None:
                issue_work_in_progress_time_deltas.append((datetime.datetime.fromtimestamp(d['params']['timestamp']) - issue_work_started[d['author']['author.email']]))
            issue_work_started[d['author']['author.email']] = None
        elif diff_action == 'chain-link':
            if 'chained' not in issue_data:
                issue_data['chained'] = []
            issue_data['chained'].extend(d['params']['sha1'])
        elif diff_action == 'chain-unlink':
            if 'chained' not in issue_data:
                issue_data['chained'] = []
                continue
            for s in d['params']['sha1']:
                issue_data['chained'].remove(s)

    # remove duplicated tags
    issue_data['tags'] = list(set(issue_data.get('tags', [])))

    issue_total_time_spent = None
    if issue_work_in_progress_time_deltas:
        issue_total_time_spent = issue_work_in_progress_time_deltas[0]
        for td in issue_work_in_progress_time_deltas[1:]:
            issue_total_time_spent += td

    repo_config = getConfig()
    if issue_work_started.get(repo_config['author.email']) is not None:
        if issue_total_time_spent is not None:
            issue_total_time_spent += (datetime.datetime.now() - issue_work_started.get(repo_config['author.email']))
        else:
            issue_total_time_spent = (datetime.datetime.now() - issue_work_started.get(repo_config['author.email']))
    if issue_total_time_spent is not None:
        issue_data['total_time_spent'] = str(issue_total_time_spent).rsplit('.', 1)[0]

    with open(issue_file_path, 'w') as ofstream:
        ofstream.write(json.dumps(issue_data))

def revindexIssue(issue_sha1, *diffs):
    issue_data = {}
    issue_file_path = os.path.join(ISSUES_PATH, issue_sha1[:2], '{0}.json'.format(issue_sha1))
    with open(issue_file_path) as ifstream:
        issue_data = json.loads(ifstream.read())

    repo_config = getConfig()

    issue_author_email = issue_data.get('open.author.email', repo_config['author.email'])
    issue_author_name = issue_data.get('open.author.name', repo_config['author.name'])
    issue_open_timestamp = issue_data.get('open.timestamp', issue_data.get('timestamp', 0))
    issue_differences = [
        {
            'action': 'open',
            'author': {
                'author.email': issue_author_email,
                'author.name': issue_author_name,
            },
            'timestamp': issue_open_timestamp,
        },
        {
            'action': 'set-message',
            'params': {
                'text': issue_data['message'],
            },
            'author': {
                'author.email': issue_author_email,
                'author.name': issue_author_name,
            },
            'timestamp': issue_open_timestamp+1,
        },
        {
            'action': 'push-tags',
            'params': {
                'tags': issue_data['tags'],
            },
            'author': {
                'author.email': issue_author_email,
                'author.name': issue_author_name,
            },
            'timestamp': issue_open_timestamp+1,
        },
        {
            'action': 'push-milestones',
            'params': {
                'milestones': issue_data.get('milestones', []),
            },
            'author': {
                'author.email': issue_author_email,
                'author.name': issue_author_name,
            },
            'timestamp': issue_open_timestamp+1,
        }
    ]
    if issue_data.get('status', 'open') == 'closed':
        issue_close_diff = {
            'action': 'close',
            'params': {
            },
            'author': {
                'author.email': issue_data.get('close.author.email', repo_config['author.email']),
                'author.name': issue_data.get('close.author.name', repo_config['author.name']),
            },
            'timestamp': issue_data.get('close.timestamp', 0),
        }
        if 'closing_git_commit' in issue_data:
            issue_close_diff['closing_git_commit'] = issue_data['closing_git_commit']
        issue_differences.append(issue_close_diff)

    issue_diff_sha1 = '{0}{1}{2}{3}'.format(repo_config['author.email'], repo_config['author.name'], timestamp(), random.random())
    issue_diff_sha1 = hashlib.sha1(issue_diff_sha1.encode('utf-8')).hexdigest()
    issue_diff_file_path = os.path.join(ISSUES_PATH, issue_sha1[:2], issue_sha1, 'diff', '{0}.json'.format(issue_diff_sha1))
    with open(issue_diff_file_path, 'w') as ofstream:
        ofstream.write(json.dumps(issue_differences))

def dropIssue(issue_sha1):
    issue_group_path = os.path.join(ISSUES_PATH, issue_sha1[:2])
    issue_file_path = os.path.join(issue_group_path, '{0}.json'.format(issue_sha1))
    os.unlink(issue_file_path)
    shutil.rmtree(os.path.join(issue_group_path, issue_sha1))

def sluggify(issue_message):
    return '-'.join(re.compile('[^ a-zA-Z0-9_]').sub(' ', unidecode.unidecode(issue_message).lower()).split())


# tag-related utility functions
def listTags():
    return os.listdir(TAGS_PATH)

def gatherTags():
    available_tags = []
    tag_to_issue_map = {}
    for issue_sha1 in sorted(listIssues()):
        issue_differences = getIssueDifferences(issue_sha1, *listIssueDifferences(issue_sha1))
        for diff in issue_differences[::-1]:
            if diff['action'] == 'push-tags':
                available_tags.extend(diff['params']['tags'])
                for t in diff['params']['tags']:
                    if t not in tag_to_issue_map:
                        tag_to_issue_map[t] = []
                    tag_to_issue_map[t].append(issue_sha1)
    for t in listTags():
        available_tags.append(t)
        if t not in tag_to_issue_map:
            tag_to_issue_map[t] = []
    return (available_tags, tag_to_issue_map)

def listTagDifferences(tag_sha1):
    tag_group = tag_sha1[:2]
    tag_diffs_path = os.path.join(TAGS_PATH, tag_group, tag_sha1, 'diff')
    return [k.split('.')[0] for k in os.listdir(tag_diffs_path)]

def getTagDifferences(tag_sha1, *diffs):
    tag_differences = []
    tag_diff_path = os.path.join(TAGS_PATH, tag_sha1[:2], tag_sha1, 'diff')
    for d in diffs:
        tag_diff_file_path = os.path.join(tag_diff_path, '{0}.json'.format(d))
        with open(tag_diff_file_path) as ifstream:
            tag_differences.extend(json.loads(ifstream.read()))
    return tag_differences

def indexTag(tag_sha1, *diffs):
    tag_data = {}
    tag_file_path = os.path.join(TAGS_PATH, tag_sha1[:2], '{0}.json'.format(tag_sha1))
    if os.path.isfile(tag_file_path) and diffs:
        with open(tag_file_path) as ifstream:
            tag_data = json.loads(ifstream.read())

    tag_differences = (diffs or listTagDifferences(tag_sha1))
    tag_differences = getTagDifferences(tag_sha1, *tag_differences)

    tag_differences_sorted = []
    tag_differences_order = {}
    for i, d in enumerate(tag_differences):
        if d['timestamp'] not in tag_differences_order:
            tag_differences_order[d['timestamp']] = []
        tag_differences_order[d['timestamp']].append(i)
    tag_differences_sorted = []
    for ts in sorted(tag_differences_order.keys()):
        tag_differences_sorted.extend([tag_differences[i] for i in tag_differences_order[ts]])

    for d in tag_differences_sorted:
        diff_datetime = datetime.datetime.fromtimestamp(d['timestamp'])
        diff_action = d['action']
        if diff_action == 'tag-open':
            tag_data['name'] = d['params']['name']
            tag_data['tag.author.name'] = d['author']['author.name']
            tag_data['tag.author.email'] = d['author']['author.email']
        elif diff_action == 'tag-set-project-name':
            tag_data['project.name'] = d['params']['name']

    with open(tag_file_path, 'w') as ofstream:
        ofstream.write(json.dumps(tag_data))

def createTag(tag_name, force=False):
    tag_path = os.path.join(TAGS_PATH, tag_name)
    if os.path.isdir(tag_path) and force:
        shutil.rmtree(tag_path)
    if os.path.isdir(tag_path):
        raise issue.exceptions.TagExists(tag_name)

    os.mkdir(tag_path)
    os.mkdir(os.path.join(tag_path, 'diff'))

    repo_config = getConfig()

    tag_differences = [
        {
            'action': 'tag-open',
            'params': {
                'name': tag_name,
            },
            'author': {
                'author.email': repo_config['author.email'],
                'author.name': repo_config['author.name'],
            },
            'timestamp': timestamp(),
        },
    ]
    if 'project.name' in repo_config:
        tag_differences.append({
            'action': 'tag-set-project-name',
            'params': {
                'name': repo_config['project.name'],
            },
            'author': {
                'author.email': repo_config['author.email'],
                'author.name': repo_config['author.name'],
            },
            'timestamp': timestamp(),
        })

    tag_diff_sha1 = '{0}{1}{2}{3}{4}'.format(tag_name, repo_config['author.email'], repo_config['author.name'], timestamp(), random.random())
    tag_diff_sha1 = hashlib.sha1(tag_diff_sha1.encode('utf-8')).hexdigest()
    tag_diff_file_path = os.path.join(tag_path, 'diff', '{0}.json'.format(tag_diff_sha1))
    with open(tag_diff_file_path, 'w') as ofstream:
        ofstream.write(json.dumps(tag_differences))


# configuration-related utility functions
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


# remote-related utility functions
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
        'diffs': {},
    }

    pack_issue_list = listIssues()
    pack_data['issues'] = pack_issue_list

    pack_comments = {}
    for p in pack_issue_list:
        pack_comments_path = os.path.join(ISSUES_PATH, p[:2], p, 'comments')
        pack_comments[p] = [sp.split('.')[0] for sp in os.listdir(pack_comments_path)]
    pack_data['comments'] = pack_comments

    pack_diffs = {}
    for p in pack_issue_list:
        pack_diffs_path = os.path.join(ISSUES_PATH, p[:2], p, 'diff')
        pack_diffs[p] = [sp.split('.')[0] for sp in os.listdir(pack_diffs_path)]
    pack_data['diffs'] = pack_diffs

    return pack_data

def savePack(pack_data=None):
    if pack_data is None:
        pack_data = getPack()
    with open(PACK_PATH, 'w') as ofstream:
        ofstream.write(json.dumps(pack_data))


# misc utility functions
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
        raise issue.exceptions.IssueUIDNotMatched(issue_sha1_part)
    if len(issue_sha1) > 1:
        raise issue.exceptions.IssueUIDAmbiguous(issue_sha1_part)
    return issue_sha1[0]

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

def listIssuesUsingShortestPossibleUIDs(with_full=False):
    list_of_issues = listIssues()
    n = shortestUnique(list_of_issues)
    if with_full:
        final_list_of_issues = [(i[:n], i) for i in list_of_issues]
    else:
        final_list_of_issues = [i[:n] for i in list_of_issues]
    return final_list_of_issues

def markLastIssue(issue_sha1):
    with open(LAST_ISSUE_PATH, 'w') as ofstream:
        ofstream.write(issue_sha1)

def getLastIssue():
    last_issue_sha1 = ''
    if os.path.isfile(LAST_ISSUE_PATH):
        with open(LAST_ISSUE_PATH) as ifstream:
            last_issue_sha1 = ifstream.read()
    return last_issue_sha1

def getTimeDeltaArguments(delta_mods):
    time_delta = {}
    time_patterns = [
        re.compile('^(\d+)(minutes?)$'),
        re.compile('^(\d+)(hours?)$'),
        re.compile('^(\d+)(days?)$'),
        re.compile('^(\d+)(weeks?)$'),
        re.compile('^(\d+)(months?)$'),
    ]
    # print(delta_mods)
    for dm in delta_mods:
        for p in time_patterns:
            pm = p.match(dm)
            if pm is not None:
                mod = pm.group(2)
                if mod[-1] != 's': mod += 's'  # allow both "1week" and "2weeks"
                time_delta[mod] = int(pm.group(1))
    return time_delta

def fetchRemote(remote_name, remote_data=None, local_pack=None):
    if remote_data is None:
        remote_data = getRemotes()[remote_name]
    if local_pack is None:
        local_pack = getPack()
    remote_pack_fetch_command = ('scp', '{0}/pack.json'.format(remote_data['url']), REMOTE_PACK_PATH)
    exit_code, output, error = runShell(*remote_pack_fetch_command)

    if exit_code:
        print('  * fail ({0}): {1}'.format(exit_code, error))
        return 1

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

    new_diffs = {}
    for k, v in remote_pack.get('diffs', {}).items():
        if k in local_pack['diffs']:
            new_diffs[k] = set(remote_pack['diffs'][k]) - set(local_pack['diffs'][k])
        else:
            new_diffs[k] = remote_pack['diffs'][k]
    # print(new_diffs)

    print('  * issues:   {0} object(s)'.format(len(new_issues)))
    print('  * comments: {0} object(s)'.format(sum([len(new_comments[k]) for k in new_comments])))
    print('  * diffs:    {0} object(s)'.format(sum([len(new_diffs[k]) for k in new_diffs])))

    if '--probe' in ui:
        return 0

    for issue_sha1 in new_issues:
        issue_group_path = os.path.join(ISSUES_PATH, issue_sha1[:2])
        if not os.path.isdir(issue_group_path):
            os.mkdir(issue_group_path)
        # make directories for issue-specific objects
        os.mkdir(os.path.join(issue_group_path, issue_sha1))
        os.mkdir(os.path.join(issue_group_path, issue_sha1, 'comments'))
        os.mkdir(os.path.join(issue_group_path, issue_sha1, 'diff'))

    for issue_sha1 in new_comments:
        if not new_comments[issue_sha1]:
            continue

        for cmt_sha1 in new_comments[issue_sha1]:
            exit_code, output, error = runShell(
                'scp',
                '{0}/objects/issues/{1}/{2}/comments/{3}.json'.format(
                    remote_data['url'],
                    issue_sha1[:2],
                    issue_sha1,
                    cmt_sha1,
                ),
                os.path.join(ISSUES_PATH, issue_sha1[:2], issue_sha1, 'comments', '{0}.json'.format(cmt_sha1))
            )

            if exit_code:
                print('  * fail ({0}): comment {1}.{2}: {3}'.format(exit_code, issue_sha1, cmt_sha1, error))
                continue

    for issue_sha1 in new_diffs:
        if not new_diffs[issue_sha1]:
            continue

        if '--verbose' in ui:
            print(' -> fetching issue: {0}'.format(issue_sha1))

        total_diffs = len(new_diffs[issue_sha1])
        for i, cmt_sha1 in enumerate(new_diffs[issue_sha1]):
            if '--verbose' in ui:
                print('    + diff: {0}: {1}/{2}'.format(cmt_sha1, (i+1), total_diffs))
            exit_code, output, error = runShell(
                'scp',
                '{0}/objects/issues/{1}/{2}/diff/{3}.json'.format(
                    remote_data['url'],
                    issue_sha1[:2],
                    issue_sha1,
                    cmt_sha1,
                ),
                os.path.join(ISSUES_PATH, issue_sha1[:2], issue_sha1, 'diff', '{0}.json'.format(cmt_sha1))
            )

            if exit_code:
                print('  * fail ({0}): diff {1}.{2}: {3}'.format(exit_code, issue_sha1, cmt_sha1, error))
                continue

def publishToRemote(remote_name, remote_data=None, local_pack=None, republish=False):
    if remote_data is None:
        remote_data = getRemotes()[remote_name]
    if local_pack is None:
        local_pack = getPack()

    remote_status = remote_data.get('status', 'unknown')
    if remote_status != 'exchange':
        print('cannot publish to "{0}": invalid remote status: {1}'.format(remote_name, remote_status))
        if '--verbose' in ui:
            if remote_status == 'endpoint':
                print('note: create a shared exchange from which "{0}" endpoint can fetch objects'.format(remote_name))
            elif remote_status == 'unknown':
                print('note: run "issue fetch --status {0}" to obtain status of this node'.format(remote_name))
            else:
                print('note: broken status, run "issue fetch --status {0}" to fix it'.format(remote_name))
        return 1
    print('publishing objects to remote: {0}'.format(remote_name))

    remote_pack = {'issues': [], 'comments': {}}

    if not republish:
        remote_pack_fetch_command = ('scp', '{0}/pack.json'.format(remote_data['url']), REMOTE_PACK_PATH)
        exit_code, output, error = runShell(*remote_pack_fetch_command)

        if exit_code == 0:
            with open(REMOTE_PACK_PATH) as ifstream:
                remote_pack = json.loads(ifstream.read())

    new_issues = set(local_pack['issues']) - set(remote_pack['issues'])
    # print(new_issues)

    new_comments = {}
    for k, v in local_pack['comments'].items():
        if k in remote_pack.get('comments', []):
            new_comments[k] = set(local_pack['comments'][k]) - set(remote_pack.get('comments', {}).get(k, []))
        else:
            new_comments[k] = local_pack['comments'][k]
    # print(new_comments)

    new_diffs = {}
    for k, v in local_pack['diffs'].items():
        if k in remote_pack.get('diffs', {}):
            new_diffs[k] = set(local_pack['diffs'][k]) - set(remote_pack.get('diffs', {}).get(k, []))
        else:
            new_diffs[k] = local_pack['diffs'][k]
    # print(new_diffs)

    print('  * publishing issues:   {0} object(s)'.format(len(new_issues)))
    print('  * publishing comments: {0} object(s)'.format(sum([len(new_comments[k]) for k in new_comments])))
    print('  * publishing diffs:    {0} object(s)'.format(sum([len(new_diffs[k]) for k in new_diffs])))

    for issue_sha1 in new_issues:
        print(' -> publishing issue: {0}'.format(issue_sha1))
        issue_group_path = os.path.join(ISSUES_PATH, issue_sha1[:2])

        required_directories = [
            os.path.join('objects', 'issues', issue_sha1[:2]),
            os.path.join('objects', 'issues', issue_sha1[:2], issue_sha1),
            os.path.join('objects', 'issues', issue_sha1[:2], issue_sha1, 'comments'),
            os.path.join('objects', 'issues', issue_sha1[:2], issue_sha1, 'diff'),
        ]

        remote_repository_host, remote_repository_path = remote_data['url'].split(':')
        required_directories = [os.path.join(remote_repository_path, rd) for rd in required_directories]
        remote_mkdir_command = 'mkdir -p {0}'.format(' '.join(required_directories))

        exit_code, output, error = runShell(
            'ssh',
            remote_repository_host,
            remote_mkdir_command,
        )

        if exit_code:
            print('  * fail ({0}): cannot create required directories: {1}'.format(exit_code, error))
            continue

    for issue_sha1 in new_comments:
        if not new_comments[issue_sha1]:
            continue

        for cmt_sha1 in new_comments[issue_sha1]:
            exit_code, output, error = runShell(
                'scp',
                os.path.join(ISSUES_PATH, issue_sha1[:2], issue_sha1, 'comments', '{0}.json'.format(cmt_sha1)),
                '{0}/objects/issues/{1}/{2}/comments/{3}.json'.format(
                    remote_data['url'],
                    issue_sha1[:2],
                    issue_sha1,
                    cmt_sha1,
                )
            )

            if exit_code:
                print('  * fail ({0}): comment {1}.{2}: {3}'.format(exit_code, issue_sha1, cmt_sha1, error))
                continue

    for issue_sha1 in new_diffs:
        if not new_diffs[issue_sha1]:
            continue

        total_diffs = len(new_diffs[issue_sha1])
        for i, diff_sha1 in enumerate(new_diffs[issue_sha1]):
            if '--verbose' in ui:
                print('    + diff: {0}: {1}/{2}'.format(diff_sha1, (i+1), total_diffs))
            exit_code, output, error = runShell(
                'scp',
                os.path.join(ISSUES_PATH, issue_sha1[:2], issue_sha1, 'diff', '{0}.json'.format(diff_sha1)),
                '{0}/objects/issues/{1}/{2}/diff/{3}.json'.format(
                    remote_data['url'],
                    issue_sha1[:2],
                    issue_sha1,
                    diff_sha1,
                )
            )

            if exit_code:
                print('  * fail ({0}): diff {1}.{2}: {3}'.format(exit_code, issue_sha1, diff_sha1, error))
                continue

    remote_pack_publish_command = ('scp', os.path.join(PACK_PATH), '{0}/pack.json'.format(remote_data['url']))
    exit_code, output, error = runShell(*remote_pack_publish_command)

    if exit_code:
        print('  * fail ({0}): failed to send pack: {1}'.format(exit_code, error))
        return 1

def timestamp(dt=None):
    return (dt or datetime.datetime.now()).timestamp()

def getMessage(template='', fmt={}):
    editor = os.getenv('EDITOR', 'vi')
    message_path = os.path.join(REPOSITORY_PATH, 'message')
    if template and format:
        with open(os.path.expanduser('~/.local/share/issue/{0}'.format(template))) as ifstream:
            default_message_text = ifstream.read()
        with open(message_path, 'w') as ofstream:
            ofstream.write(default_message_text.format(**fmt))
    elif template and not format:
        shutil.copy(os.path.expanduser('~/.local/share/issue/{0}'.format(template)), message_path)
    os.system('{0} {1}'.format(editor, message_path))
    message = ''
    with open(message_path) as ifstream:
        message_lines = ifstream.readlines()
        message = ''.join([l for l in message_lines if not l.startswith('#')]).strip()
    return message

def repositoryInit(force=False, up=False):
    if force and os.path.isdir(REPOSITORY_PATH):
        shutil.rmtree(REPOSITORY_PATH)
    if not up and os.path.isdir(REPOSITORY_PATH):
        raise issue.exceptions.RepositoryExists(REPOSITORY_PATH)
    for pth in (REPOSITORY_PATH, OBJECTS_PATH, REPOSITORY_TMP_PATH, ISSUES_PATH, TAGS_PATH, MILESTONES_PATH):
        if not os.path.isdir(pth):
            os.mkdir(pth)
    with open(os.path.join(REPOSITORY_PATH, 'status'), 'w') as ofstream:
        ofstream.write('exchange' if '--exchange' in ui else 'endpoint')
    for issue_sha1 in listIssues():
        issue_diffs_path = os.path.join(ISSUES_PATH, issue_sha1[:2], issue_sha1, 'diff')
        if not os.path.isdir(issue_diffs_path):
            os.mkdir(issue_diffs_path)
    return os.path.abspath(REPOSITORY_PATH)


######################################################################
# LOGIC CODE
#
if '--pack' in ui:
    print('packing objects:')
    pack_data = getPack()

    count_issues = len(pack_data['issues'])
    count_comments = sum([len(pack_data['comments'][n]) for n in pack_data['comments'].keys()])
    count_diffs = sum([len(pack_data['diffs'][n]) for n in pack_data['diffs'].keys()])

    print('  * issues  ', end='')
    print(' [{0} object(s)]'.format(count_issues))

    print('  * comments', end='')
    print(' [{0} object(s)]'.format(count_comments))

    print('  * diffs   ', end='')
    print(' [{0} object(s)]'.format(count_diffs))

    savePack(pack_data)
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


ui = ui.down() # go down a mode
operands = ui.operands()

if str(ui) not in ('clone', 'init', 'help') and not os.path.isdir(REPOSITORY_PATH):
    while not os.path.isdir(REPOSITORY_PATH) and os.path.abspath(REPOSITORY_PATH) != '/.issue':
        REPOSITORY_PATH = os.path.join('..', REPOSITORY_PATH)
    REPOSITORY_PATH = os.path.abspath(REPOSITORY_PATH)
    if REPOSITORY_PATH == '/.issue':
        print('fatal: not inside issues repository')
        exit(1)
    OBJECTS_PATH = os.path.join(REPOSITORY_PATH, 'objects')
    REPOSITORY_TMP_PATH = os.path.join(REPOSITORY_PATH, 'tmp')
    ISSUES_PATH = os.path.join(OBJECTS_PATH, 'issues')
    TAGS_PATH = os.path.join(OBJECTS_PATH, 'tags')
    MILESTONES_PATH = os.path.join(OBJECTS_PATH, 'milestones')
    PACK_PATH = os.path.join(REPOSITORY_PATH, 'pack.json')
    REMOTE_PACK_PATH = os.path.join(REPOSITORY_PATH, 'remote_pack.json')
    LAST_ISSUE_PATH = os.path.join(REPOSITORY_PATH, 'last')


def commandInit(ui):
    if '--force' in ui and os.path.isdir(REPOSITORY_PATH):
        shutil.rmtree(REPOSITORY_PATH)
    if os.path.isdir(REPOSITORY_PATH) and '--up' not in ui:
        print('fatal: repository already exists')
        exit(1)
    initialised_in = repositoryInit(force=('--force' in ui), up=('--up' in ui))
    if '--verbose' in ui:
        print('repository initialised in {0}'.format(initialised_in))

def commandOpen(ui):
    tags = ([l[0] for l in ui.get('--tag')] if '--tag' in ui else [])
    gathered_tags = gatherTags()
    for t in tags:
        if t not in gathered_tags[0]:
            print('fatal: tag "{0}" does not exist'.format(t))
            print('note: use "issue tag new {0}" to create it'.format(t))
            exit(1)

    milestones = ([m[0] for m in ui.get('--milestone')] if '--milestone' in ui else [])

    message = (getMessage('issue_message') if len(operands) < 1 else operands[0])
    if not message:
        print('fatal: aborting due to empty message')
        exit(1)

    issue_sha1 = '{0}{1}{2}{3}'.format(message, tags, milestones, random.random())
    issue_sha1 = hashlib.sha1(issue_sha1.encode('utf-8')).hexdigest()

    repo_config = getConfig()

    issue_group_path = os.path.join(ISSUES_PATH, issue_sha1[:2])
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

    repo_config = getConfig()
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
    issue_diff_sha1 = hashlib.sha1(issue_diff_sha1.encode('utf-8')).hexdigest()
    issue_diff_file_path = os.path.join(issue_group_path, issue_sha1, 'diff', '{0}.json'.format(issue_diff_sha1))
    with open(issue_diff_file_path, 'w') as ofstream:
        ofstream.write(json.dumps(issue_differences))

    indexIssue(issue_sha1)
    markLastIssue(issue_sha1)

    if '--chain-to' in ui:
        for link_issue_sha1 in ui.get('--chain-to'):
            try:
                link_issue_sha1 = expandIssueUID(link_issue_sha1)
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
                issue_diff_sha1 = hashlib.sha1(issue_diff_sha1.encode('utf-8')).hexdigest()
                issue_diff_file_path = os.path.join(ISSUES_PATH, link_issue_sha1[:2], link_issue_sha1, 'diff', '{0}.json'.format(issue_diff_sha1))
                with open(issue_diff_file_path, 'w') as ofstream:
                    ofstream.write(json.dumps(issue_differences))
                indexIssue(link_issue_sha1, issue_diff_sha1)
            except Exception as e:
                print('warning: could not link issue identified by "{0}":'.format(link_issue_sha1), e)

    if '--git' in ui:
        print('issue/{0}'.format(sluggify(message)))
    elif '--verbose' in ui:
        print(issue_sha1)

def commandClose(ui):
    repo_config = getConfig()
    issue_sha1 = (getLastIssue() if '--last' in ui else operands[0])
    try:
        issue_sha1 = expandIssueUID(issue_sha1)
    except issue.exceptions.IssueUIDAmbiguous:
        print('fail: issue uid {0} is ambiguous'.format(repr(issue_sha1)))
        exit(1)
    except issue.exceptions.IssueUIDNotMatched:
        print('fail: uid {0} does not match anything'.format(repr(issue_sha1)))
        exit(1)
    issue_data = getIssue(issue_sha1)

    if issue_data['status'] == 'closed':
        print('fatal: issue already closed by {0}{1}'.format(issue_data.get('close.author.name', 'Unknown author'), (' ({0})'.format(issue_data['close.author.email']) if 'close.author.email' else '')))
        exit(1)

    chained_issues = issue_data.get('chained', [])
    unclosed_chained_issues = []
    for c in chained_issues:
        ci = getIssue(c, index=True)
        if ci['status'] != 'closed':
            unclosed_chained_issues.append((c, ci['message'].splitlines()[0]))
    if unclosed_chained_issues:
        print('fatal: unclosed chained issues exist:')
        for ui_sha1, ui_msg in unclosed_chained_issues:
            print('  {0}: {1}'.format(ui_sha1, ui_msg))
        exit(1)

    issue_differences = [
        {
            'action': 'close',
            'params': {
            },
            'author': {
                'author.email': repo_config['author.email'],
                'author.name': repo_config['author.name'],
            },
            'timestamp': timestamp(),
        },
    ]
    if '--git-commit' in ui:
        closing_git_commit = ui.get('--git-commit')
        if closing_git_commit == '-':
            closing_git_commit = 'HEAD'
        p = subprocess.Popen(('git', 'show', closing_git_commit), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, error = p.communicate()
        exit_code = p.wait()
        output = output.decode('utf-8').strip()
        if exit_code != 0:
            print(error.decode('utf-8').strip().splitlines()[0])
            exit(exit_code)
        closing_git_commit = output.splitlines()[0].split(' ')[1]
        issue_differences[0]['params']['closing_git_commit'] = closing_git_commit

    issue_diff_sha1 = '{0}{1}{2}{3}'.format(repo_config['author.email'], repo_config['author.name'], timestamp(), random.random())
    issue_diff_sha1 = hashlib.sha1(issue_diff_sha1.encode('utf-8')).hexdigest()
    issue_diff_file_path = os.path.join(ISSUES_PATH, issue_sha1[:2], issue_sha1, 'diff', '{0}.json'.format(issue_diff_sha1))
    with open(issue_diff_file_path, 'w') as ofstream:
        ofstream.write(json.dumps(issue_differences))
    markLastIssue(issue_sha1)
    # indexIssue(issue_sha1, issue_diff_sha1)
    indexIssue(issue_sha1, issue_diff_sha1)

def commandLs(ui):
    groups = os.listdir(ISSUES_PATH)
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
        delta_mods_since = getConfig().get('default.time.recent', '1day').split(',')

    if '--since' in ui or '--recent' in ui:
        since = (datetime.datetime.now() - datetime.timedelta(**getTimeDeltaArguments(delta_mods_since)))

    if '--until' in ui:
        until = (datetime.datetime.now() - datetime.timedelta(**getTimeDeltaArguments(delta_mods_until)))

    issues_to_list = []
    for short, i in issues:
        issue_sha1 = i.split('.', 1)[0]
        try:
            issue_data = getIssue(issue_sha1)
        except issue.exceptions.NotIndexed as e:
            print('{0}: [not indexed]'.format(short))
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
        chained_issues = getIssue(expandIssueUID(ui.get('--chained-to'))).get('chained', [])
        issues_to_list = list(filter(lambda i: (i[1] in chained_issues), issues_to_list))

    if '--priority' in ui:
        issues_to_list = sorted(issues_to_list, key=lambda t: int(t[2].get('parameters', {}).get('priority', 1024)))

    for short, i, issue_data in issues_to_list:
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
        try:
            if '--details' in ui:
                print('{0}: {1}'.format(short, issue_data['message'].splitlines()[0]))
                issue_open_author_name = (issue_data['open.author.name'] if 'open.author.name' in issue_data else 'Unknown Author')
                issue_open_author_email = (issue_data['open.author.email'] if 'open.author.email' in issue_data else 'Unknown email')
                issue_open_timestamp = (datetime.datetime.fromtimestamp(issue_data['open.timestamp']) if 'open.timestamp' in issue_data else 'unknown date')
                if issue_data['status'] == 'closed':
                    issue_close_author_name = (issue_data['close.author.name'] if 'close.author.name' in issue_data else 'Unknown Author')
                    issue_close_author_email = (issue_data['close.author.email'] if 'close.author.email' in issue_data else 'Unknown email')
                    issue_close_timestamp = (datetime.datetime.fromtimestamp(issue_data['close.timestamp']) if 'close.timestamp' in issue_data else 'unknown date')
                    print('    closed by:  {0} ({1}), on {2}'.format(issue_close_author_name, issue_close_author_email, issue_close_timestamp))
                print('    opened by:  {0} ({1}), on {2}'.format(issue_open_author_name, issue_open_author_email, issue_open_timestamp))
                print('    milestones: {0}'.format(', '.join(issue_data['milestones'])))
                print('    tags:       {0}'.format(', '.join(issue_data['tags'])))
                print()
            else:
                print('{0}: {1}'.format(short, issue_data['message'].splitlines()[0]))
        except (KeyError, IndexError) as e:
            print('{0}: [broken index]'.format(i))

def commandDrop(ui):
    issue_list = ([getLastIssue()] if '--last' in ui else operands)
    for issue_sha1 in issue_list:
        try:
            dropIssue(expandIssueUID(issue_sha1))
        except issue.exceptions.IssueUIDAmbiguous:
            print('fail: issue uid {0} is ambiguous'.format(repr(issue_sha1)))

def commandSlug(ui):
    issue_data = {}
    issue_sha1 = (getLastIssue() if '--last' in ui else operands[0])
    try:
        issue_sha1 = expandIssueUID(issue_sha1)
        issue_data = getIssue(issue_sha1)
    except issue.exceptions.IssueUIDAmbiguous:
        print('fail: issue uid {0} is ambiguous'.format(repr(issue_sha1)))
        exit(1)
    issue_message = issue_data['message'].splitlines()[0].strip()
    issue_slug = sluggify(issue_message)

    slug_format = getConfig().get('slug.format.default', '')
    if slug_format.startswith('@'):
        slug_format = getConfig().get('slug.format.{0}'.format(slug_format[1:]), '')

    slug_parameters = issue_data.get('parameters', {})
    if '--param' in ui:
        for k, v in ui.get('--param'):
            slug_parameters[k] = v

    if '--git' in ui:
        slug_format = 'issue/{slug}'
    if '--format' in ui:
        slug_format = ui.get('--format')
    if '--use-format' in ui:
        repo_config = getConfig()
        slug_format = repo_config.get('slug.format.{0}'.format(ui.get('--use-format')), '')
        if not slug_format:
            print('fatal: undefined slug format: {0}'.format(ui.get('--use-format')))
            exit(1)

    if slug_format:
        issue_slug = slug_format.format(slug=issue_slug, **slug_parameters)

    if '--git-branch' in ui:
        r = os.system('git branch {0}'.format(issue_slug))
        if r != 0:
            exit(r)
    if '--git-checkout' in ui:
        r = os.system('git checkout {0}'.format(issue_slug))
        if r != 0:
            exit(r)
    if ('--git-branch' not in ui) and ('--git-checkout' not in ui):
        print(issue_slug)
    markLastIssue(issue_sha1)

def commandComment(ui):
    issue_sha1 = (getLastIssue() if '--last' in ui else operands[0])
    try:
        issue_sha1 = expandIssueUID(issue_sha1)
    except issue.exceptions.IssueUIDAmbiguous:
        print('fail: issue uid {0} is ambiguous'.format(repr(issue_sha1)))
        exit(1)

    issue_data = getIssue(issue_sha1)

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
    markLastIssue(issue_sha1)

def commandTag(ui):
    ui = ui.down()
    subcommand = str(ui)
    if subcommand == 'ls':
        available_tags, tag_to_issue_map = gatherTags()
        created_tags = set(listTags())
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
            available_tags, tag_to_issue_map = gatherTags()
            created_tags = set(listTags())
            missing_tags = (set(available_tags) - created_tags)
            n = 0
            for t in missing_tags:
                createTag(t)
            if '--verbose' in ui:
                print('created {0} tag(s): {1}'.format(len(missing_tags), ', '.join(sorted(missing_tags))))
        else:
            try:
                createTag(ui.operands()[0])
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

        if issue_tag not in gatherTags()[0]:
            print('fatal: tag "{0}" does not exist'.format(issue_tag))
            print('note: use "issue tag new {0}" to create it'.format(issue_tag))
            exit(1)

        if not issue_tag:
            print('fatal: aborting due to empty tag')
            exit(1)

        repo_config = getConfig()

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
        issue_diff_sha1 = hashlib.sha1(issue_diff_sha1.encode('utf-8')).hexdigest()
        issue_diff_file_path = os.path.join(ISSUES_PATH, issue_sha1[:2], issue_sha1, 'diff', '{0}.json'.format(issue_diff_sha1))
        with open(issue_diff_file_path, 'w') as ofstream:
            ofstream.write(json.dumps(issue_differences))
        markLastIssue(issue_sha1)
        indexIssue(issue_sha1, issue_diff_sha1)
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

    repo_config = getConfig()

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
    issue_diff_sha1 = hashlib.sha1(issue_diff_sha1.encode('utf-8')).hexdigest()
    issue_diff_file_path = os.path.join(ISSUES_PATH, issue_sha1[:2], issue_sha1, 'diff', '{0}.json'.format(issue_diff_sha1))
    with open(issue_diff_file_path, 'w') as ofstream:
        ofstream.write(json.dumps(issue_differences))
    markLastIssue(issue_sha1)
    indexIssue(issue_sha1, issue_diff_sha1)

def commandShow(ui):
    ui = ui.down()
    issue_sha1 = (getLastIssue() if '--last' in ui else ui.operands()[0])
    try:
        issue_sha1 = expandIssueUID(issue_sha1)
    except issue.exceptions.IssueUIDAmbiguous:
        print('fail: issue uid {0} is ambiguous'.format(repr(issue_sha1)))
        exit(1)
    except issue.exceptions.IssueUIDNotMatched:
        print('fail: issue uid {0} did not match anything'.format(repr(issue_sha1)))
        exit(1)

    if str(ui) == 'show' and '--index' in ui:
        indexIssue(issue_sha1)

    issue_data = {}
    try:
        issue_data = getIssue(issue_sha1)
    except issue.exceptions.NotAnIssue as e:
        print('fatal: {0} does not identify a valid object'.format(repr(issue_sha1)))
        exit(1)
    except issue.exceptions.NotIndexed as e:
        print('fatal: object {0} is not indexed'.format(repr(issue_sha1)))
        print('note: run "issue index {0}"'.format(ui.operands()[0]))
        exit(1)

    if str(ui) == 'show':
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
        print('    total time spent:  {0}'.format(issue_data.get('total_time_spent', '0:00:00')))
        print('    milestones: {0}'.format(', '.join(issue_data['milestones'])))
        print('    tags:       {0}'.format(', '.join(issue_data['tags'])))
        print('    project:    {0} ({1})'.format(issue_data.get('project.name', 'Unknown'), issue_data.get('project.tag', '')))
        if 'parameters' in issue_data and issue_data['parameters']:
            print('\n---- PARAMETERS')
            for key in sorted(issue_data['parameters'].keys()):
                print('    {0} = {1}'.format(key, issue_data['parameters'][key]))

        chained_issues = issue_data.get('chained', [])
        if chained_issues:
            print('\n---- CHAINED ISSUES')
            for s in sorted(chained_issues):
                chained_issue = getIssue(s)
                print('    {0} ({1}): {2}'.format(s, chained_issue.get('status'), chained_issue.get('message', '').splitlines()[0]))

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
        markLastIssue(issue_sha1)
    elif str(ui) == 'log':
        print('showing log of issue: {0}'.format(issue_sha1))
        issue_differences = getIssueDifferences(issue_sha1, *listIssueDifferences(issue_sha1))

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
            if diff_action == 'open':
                print('{0}: opened by: {1} ({2})'.format(diff_datetime, d['author']['author.name'], d['author']['author.email']))
            elif diff_action == 'close':
                print('{0}: closed by: {1} ({2})'.format(diff_datetime, d['author']['author.name'], d['author']['author.email']), end='')
                if 'closing_git_commit' in d['params'] and d['params']['closing_git_commit']:
                    print(' with Git commit {0}'.format(d['params']['closing_git_commit']))
                else:
                    print()
            elif diff_action == 'set-message':
                print('{0}: message set by: {1} ({2})'.format(diff_datetime, d['author']['author.name'], d['author']['author.email']))
            # support both -tags and -labels ("labels" name has been used in pre-0.1.5 versions)
            # FIXME: this support should be removed after early repositories are converted
            elif diff_action == 'push-tags' or diff_action == 'push-labels':
                print('{0}: tagged by: {1} ({2}) with {3}'.format(diff_datetime, d['author']['author.name'], d['author']['author.email'], ', '.join(d['params'][('tags' if 'tags' in d['params'] else 'labels')])))
            # support both -tags and -labels ("labels" name has been used in pre-0.1.5 versions)
            # FIXME: this support should be removed after early repositories are converted
            elif diff_action == 'remove-tags' or diff_action == 'remove-labels':
                print('{0}: tags removed by: {1} ({2}) with {3}'.format(diff_datetime, d['author']['author.name'], d['author']['author.email'], ', '.join(d['params'][('tags' if 'tags' in d['params'] else 'labels')])))
            elif diff_action == 'parameter-set':
                print('{0}: parameter set by: {1} ({2}): {3} = {4}'.format(diff_datetime, d['author']['author.name'], d['author']['author.email'], d['params']['key'], repr(d['params']['value'])))
            elif diff_action == 'parameter-remove':
                print('{0}: parameter removed by: {1} ({2}): {3}'.format(diff_datetime, d['author']['author.name'], d['author']['author.email'], d['params']['key']))
            elif diff_action == 'push-milestones':
                print('{0}: milestones set by: {1} ({2}): {3}'.format(diff_datetime, d['author']['author.name'], d['author']['author.email'], ', '.join(d['params']['milestones'])))
            elif diff_action == 'set-status':
                print('{0}: status set by: {1} ({2}): {3}'.format(diff_datetime, d['author']['author.name'], d['author']['author.email'], d['params']['status']))
            elif diff_action == 'set-project-tag':
                print('{0}: project tag set by: {1} ({2}): {3}'.format(diff_datetime, d['author']['author.name'], d['author']['author.email'], d['params']['tag']))
            elif diff_action == 'set-project-name':
                print('{0}: project name set by: {1} ({2}): {3}'.format(diff_datetime, d['author']['author.name'], d['author']['author.email'], d['params']['name']))
            elif diff_action == 'work-start':
                print('{0}: work started by {1} ({2})'.format(diff_datetime, d['author']['author.name'], d['author']['author.email']))
            elif diff_action == 'work-stop':
                print('{0}: work stopped by {1} ({2})'.format(diff_datetime, d['author']['author.name'], d['author']['author.email']))
            elif diff_action == 'chain-link':
                print('{0}: chained with {3} by {1} ({2})'.format(diff_datetime, d['author']['author.name'], d['author']['author.email'], ', '.join(d['params']['sha1'])))
            elif diff_action == 'chain-unlink':
                print('{0}: unchained from {3} by {1} ({2})'.format(diff_datetime, d['author']['author.name'], d['author']['author.email'], ', '.join(d['params']['sha1'])))

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
            print(('{0} [{1}] => {2}' if '--verbose' in ui else '{0}').format(k, remote_data.get('status', 'unknown'), remote_data['url']))
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

def commandFetch(ui):
    ui = ui.down()
    remotes = getRemotes()
    fetch_from_remotes = (ui.operands() or sorted(remotes.keys()))
    if '--status' in ui:
        for remote_name in fetch_from_remotes:
            if '--unknown-status' in ui and not (remotes[remote_name].get('status', 'unknown') == 'unknown'):
                # if --unknown-status is specified fetch only when status is 'unknown'
                continue
            print('fetching status from remote: {0}'.format(remote_name))
            remote_status_path = os.path.join(REPOSITORY_TMP_PATH, 'status')
            remote_pack_fetch_command = ('scp', '{0}/status'.format(remotes[remote_name]['url']), remote_status_path)
            exit_code, output, error = runShell(*remote_pack_fetch_command)
            if exit_code:
                print('  * fail ({0}): {1}'.format(exit_code, error))
                continue
            with open(remote_status_path) as ifstream:
                remotes[remote_name]['status'] = ifstream.read().strip()
        saveRemotes(remotes)
    else:
        for remote_name in fetch_from_remotes:
            print('{1} objects from remote: {0}'.format(remote_name, ('probing' if '--probe' in ui else 'fetching')))
            fetchRemote(remote_name, remotes[remote_name])
        if '--index' in ui:
            for issue_sha1 in listIssues():
                indexIssue(issue_sha1)

def commandPublish(ui):
    ui = ui.down()
    local_pack = getPack()
    remotes = getRemotes()
    publish_to_remotes = (ui.operands() or sorted([k for k in remotes.keys() if remotes[k].get('status', 'unknow') == 'exchange']))

    if '--fetch' in ui:
        for remote_name in publish_to_remotes:
            print('fetching remote "{0}" before publishing'.format(remote_name))
            fetchRemote(remote_name, remotes[remote_name])

    if '--pack' in ui:
        savePack()

    for remote_name in publish_to_remotes:
        publishToRemote(remote_name, remotes[remote_name], local_pack, republish=('--republish' in ui))

def commandIndex(ui):
    ui = ui.down()
    issue_list = ui.operands()
    if '--reverse' not in ui and not issue_list:
        issue_list = listIssues()
    if '--reverse' in ui:
        for i in listIssues():
            if not os.listdir(os.path.join(ISSUES_PATH, i[:2], i, 'diff')):
                issue_list.append(i)
    for issue_sha1 in issue_list:
        issue_sha1 = expandIssueUID(issue_sha1)
        if '--reverse' in ui:
            print('rev-indexing issue: {0}'.format(issue_sha1))
            revindexIssue(issue_sha1)
        else:
            indexIssue(issue_sha1)
    if '--pack' in ui:
        savePack()

def commandClone(ui):
    ui = ui.down()
    operands = ui.operands()

    try:
        repositoryInit(force=('--force' in ui))
    except issue.exceptions.RepositoryExists:
        print('fatal: repository exists')
        exit(1)
    remotes = getRemotes()

    remote_name = (ui.get('--name') if '--name' in ui else 'origin')
    remote_url = operands[0]

    remotes[remote_name] = {}
    remotes[remote_name]['url'] = remote_url
    fetchRemote(remote_name, remotes[remote_name])

    remote_status_path = os.path.join(REPOSITORY_TMP_PATH, 'status')
    remote_pack_fetch_command = ('scp', '{0}/status'.format(remotes[remote_name]['url']), remote_status_path)
    exit_code, output, error = runShell(*remote_pack_fetch_command)
    if exit_code:
        print('  could not fetch status, use "issue fetch -U" to try again')
    if exit_code == 0:
        with open(remote_status_path) as ifstream:
            remotes[remote_name]['status'] = ifstream.read().strip()
    saveRemotes(remotes)

def commandWork(ui):
    ui = ui.down()

    if '--in-progress' in ui:
        repo_config = getConfig()
        work_in_progress = []
        wip_of = (ui.get('--of') if '--of' in ui else repo_config['author.email'])
        for issue_sha1 in sorted(listIssues()):
            issue_differences = sortIssueDifferences(getIssueDifferences(issue_sha1, *listIssueDifferences(issue_sha1)))
            for diff in issue_differences[::-1]:
                if diff['action'] == 'work-stop' and diff['author']['author.email'] == wip_of:
                    break
                if diff['action'] == 'work-start' and diff['author']['author.email'] == wip_of:
                    work_in_progress.append(issue_sha1)
                    break
        for wip in work_in_progress:
            print(wip)
        return

    issue_sha1 = (getLastIssue() if '--last' in ui else ui.operands()[0])
    try:
        issue_sha1 = expandIssueUID(issue_sha1)
    except issue.exceptions.IssueUIDAmbiguous:
        print('fail: issue uid {0} is ambiguous'.format(repr(issue_sha1)))
        exit(1)
    except issue.exceptions.IssueUIDNotMatched:
        print('fail: issue uid {0} did not match anything'.format(repr(issue_sha1)))
        exit(1)

    if str(ui) == 'start':
        issue_differences = sortIssueDifferences(getIssueDifferences(issue_sha1, *listIssueDifferences(issue_sha1)))
        repo_config = getConfig()
        wip_of = repo_config['author.email']
        for diff in issue_differences[::-1]:
            if diff['action'] == 'work-stop' and diff['author']['author.email'] == wip_of:
                break
            if diff['action'] == 'work-start' and diff['author']['author.email'] == wip_of:
                print('fatal: work on issue {0} already started'.format(issue_sha1))
                exit(1)

        ts = timestamp()
        issue_differences = [
            {
                'action': 'work-start',
                'params': {
                    'timestamp': ts,
                },
                'author': {
                    'author.email': repo_config['author.email'],
                    'author.name': repo_config['author.name'],
                },
                'timestamp': ts,
            }
        ]

        issue_diff_sha1 = '{0}{1}{2}{3}'.format(repo_config['author.email'], repo_config['author.name'], timestamp(), random.random())
        issue_diff_sha1 = hashlib.sha1(issue_diff_sha1.encode('utf-8')).hexdigest()
        issue_diff_file_path = os.path.join(ISSUES_PATH, issue_sha1[:2], issue_sha1, 'diff', '{0}.json'.format(issue_diff_sha1))
        with open(issue_diff_file_path, 'w') as ofstream:
            ofstream.write(json.dumps(issue_differences))
        markLastIssue(issue_sha1)
        indexIssue(issue_sha1, issue_diff_sha1)
    elif str(ui) == 'stop':
        issue_differences = sortIssueDifferences(getIssueDifferences(issue_sha1, *listIssueDifferences(issue_sha1)))
        repo_config = getConfig()
        wip_of = repo_config['author.email']
        work_not_started = True
        for diff in issue_differences[::-1]:
            if diff['action'] == 'work-stop' and diff['author']['author.email'] == wip_of:
                print('fatal: work on issue {0} already stopped'.format(issue_sha1))
                exit(1)
            if diff['action'] == 'work-start' and diff['author']['author.email'] == wip_of:
                work_not_started = False
                break
        if work_not_started:
            print('fatal: work on issue {0} not started'.format(issue_sha1))
            exit(1)

        ts = timestamp()
        issue_differences = [
            {
                'action': 'work-stop',
                'params': {
                    'timestamp': ts,
                },
                'author': {
                    'author.email': repo_config['author.email'],
                    'author.name': repo_config['author.name'],
                },
                'timestamp': ts,
            }
        ]

        issue_diff_sha1 = '{0}{1}{2}{3}'.format(repo_config['author.email'], repo_config['author.name'], timestamp(), random.random())
        issue_diff_sha1 = hashlib.sha1(issue_diff_sha1.encode('utf-8')).hexdigest()
        issue_diff_file_path = os.path.join(ISSUES_PATH, issue_sha1[:2], issue_sha1, 'diff', '{0}.json'.format(issue_diff_sha1))
        with open(issue_diff_file_path, 'w') as ofstream:
            ofstream.write(json.dumps(issue_differences))
        markLastIssue(issue_sha1)
        indexIssue(issue_sha1, issue_diff_sha1)

def commandChain(ui):
    ui = ui.down()

    issue_sha1 = (getLastIssue() if '--last' in ui else ui.operands()[0])
    try:
        issue_sha1 = expandIssueUID(issue_sha1)
    except issue.exceptions.IssueUIDAmbiguous:
        print('fail: issue uid {0} is ambiguous'.format(repr(issue_sha1)))
        exit(1)

    link_issue_sha1s = ui.operands()
    if '--last' not in ui:
        link_issue_sha1s = link_issue_sha1s[1:]
    for i, link_issue_sha1 in enumerate(link_issue_sha1s):
        try:
            link_issue_sha1s[i] = expandIssueUID(link_issue_sha1)
        except issue.exceptions.IssueUIDAmbiguous:
            print('fail: link issue uid {0} is ambiguous'.format(repr(link_issue_sha1)))
            exit(1)
        except issue.exceptions.IssueUIDNotMatched:
            print('fail: uid {0} does not match anything'.format(repr(link_issue_sha1)))
            exit(1)

    if str(ui) == 'link':
        repo_config = getConfig()

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
            issue_diff_sha1 = hashlib.sha1(issue_diff_sha1.encode('utf-8')).hexdigest()
            issue_diff_file_path = os.path.join(ISSUES_PATH, issue_sha1[:2], issue_sha1, 'diff', '{0}.json'.format(issue_diff_sha1))
            with open(issue_diff_file_path, 'w') as ofstream:
                ofstream.write(json.dumps(issue_differences))
            markLastIssue(issue_sha1)
            indexIssue(issue_sha1, issue_diff_sha1)
    elif str(ui) == 'unlink':
        print(ui)
    else:
        print(ui)


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
    commandTag,
    commandParam,
    commandShow,
    commandConfig,
    commandRemote,
    commandFetch,
    commandPublish,
    commandIndex,
    commandClone,
    commandWork,
    commandChain,
)
