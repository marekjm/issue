import datetime
import json
import os
import re
import shutil
import sys

import unidecode

import issue


def ls():
    list_of_issues = []
    groups = os.listdir(issue.util.paths.issues_path())
    for g in groups:
        list_of_issues.extend(
            [
                p
                for p in os.listdir(os.path.join(issue.util.paths.issues_path(), g))
                if not p.endswith(".json")
            ]
        )
    return list_of_issues


def getIssue(issue_sha1, index=False):
    if index:
        indexIssue(issue_sha1)
    issue_group = issue_sha1[:2]
    issue_file_path = os.path.join(
        issue.util.paths.issues_path(), issue_group, "{0}.json".format(issue_sha1)
    )
    issue_data = {}
    try:
        with open(issue_file_path, "r") as ifstream:
            issue_data = json.loads(ifstream.read())

        issue_comments_dir = issue.util.paths.comments_path_of(issue_sha1)
        issue_data["comments"] = {}
        if os.path.isdir(issue_comments_dir):
            for cmt in os.listdir(issue_comments_dir):
                with open(os.path.join(issue_comments_dir, cmt)) as ifstream:
                    try:
                        issue_data["comments"][cmt.split(".")[0]] = json.loads(
                            ifstream.read()
                        )
                    except json.decoder.JSONDecodeError as e:
                        print(
                            "error: diff (comment) {}.{} corrupted: {}".format(
                                issue_sha1, cmt.split(".", 1)[0], e
                            )
                        )
    except FileNotFoundError as e:
        # if os.path.isdir(os.path.join(ISSUES_PATH, issue_group, issue_sha1)):
        if os.path.isdir(
            os.path.join(issue.util.paths.issues_path(), issue_group, issue_sha1)
        ):
            raise issue.exceptions.NotIndexed(issue_file_path)
        else:
            raise issue.exceptions.NotAnIssue(issue_file_path)
    return issue_data


def saveIssue(issue_sha1, issue_data):
    issue_group = issue_sha1[:2]
    issue_file_path = os.path.join(
        ISSUES_PATH, issue_group, "{0}.json".format(issue_sha1)
    )
    if "comments" in issue_data:
        del issue_data["comments"]
    with open(issue_file_path, "w") as ofstream:
        ofstream.write(json.dumps(issue_data))


def listIssueDifferences(issue_sha1):
    issue_group = issue_sha1[:2]
    issue_diffs_path = issue.util.paths.diffs_path_of(issue_sha1)
    return [k.split(".")[0] for k in os.listdir(issue_diffs_path)]


def getIssueDifferences(issue_sha1, *diffs):
    issue_differences = []
    issue_diff_path = issue.util.paths.diffs_path_of(issue_sha1)
    for d in diffs:
        issue_diff_file_path = os.path.join(issue_diff_path, "{0}.json".format(d))
        with open(issue_diff_file_path) as ifstream:
            try:
                issue_differences.extend(json.loads(ifstream.read()))
            except json.decoder.JSONDecodeError:
                sys.stderr.write(
                    "warning: problem with issue {} diff {}\n".format(issue_sha1, d)
                )
    return issue_differences


def sortIssueDifferences(issue_differences):
    issue_differences_sorted = []
    issue_differences_order = {}
    for i, d in enumerate(issue_differences):
        if d["timestamp"] not in issue_differences_order:
            issue_differences_order[d["timestamp"]] = []
        issue_differences_order[d["timestamp"]].append(i)
    issue_differences_sorted = []
    for ts in sorted(issue_differences_order.keys()):
        issue_differences_sorted.extend(
            [issue_differences[i] for i in issue_differences_order[ts]]
        )
    return issue_differences_sorted


def indexIssue(issue_sha1, *diffs):
    issue_data = {}
    issue_file_path = issue.util.paths.indexed_path_of(issue_sha1)
    if os.path.isfile(issue_file_path) and diffs:
        with open(issue_file_path) as ifstream:
            issue_data = json.loads(ifstream.read())

    issue_differences = diffs or listIssueDifferences(issue_sha1)
    issue_differences = getIssueDifferences(issue_sha1, *issue_differences)

    issue_differences_sorted = sortIssueDifferences(issue_differences)

    issue_work_started = {}
    issue_work_in_progress_time_deltas = []
    for d in issue_differences_sorted:
        diff_datetime = datetime.datetime.fromtimestamp(d["timestamp"])
        diff_action = d["action"]
        if diff_action == "open":
            issue_data["status"] = "open"
            issue_data["open.author.name"] = d["author"]["author.name"]
            issue_data["open.author.email"] = d["author"]["author.email"]
            issue_data["open.timestamp"] = d["timestamp"]
        elif diff_action == "close":
            issue_data["status"] = "closed"
            issue_data["close.author.name"] = d["author"]["author.name"]
            issue_data["close.author.email"] = d["author"]["author.email"]
            issue_data["close.timestamp"] = d["timestamp"]
            if (
                "closing_git_commit" in d["params"]
                and d["params"]["closing_git_commit"]
            ):
                issue_data["closing_git_commit"] = d["params"]["closing_git_commit"]
            if "git_timestamp" in d["params"]:
                issue_data["close.timestamp"] = d["params"]["git_timestamp"]
        elif diff_action == "set-message":
            issue_data["message"] = d["params"]["text"]
        # support both -tags and -labels ("labels" name has been used in pre-0.1.5 versions)
        # FIXME: this support should be removed after early repositories are converted
        elif diff_action == "push-tags" or diff_action == "push-labels":
            if "tags" not in issue_data:
                issue_data["tags"] = []
            issue_data["tags"].extend(
                d["params"][("tags" if "tags" in d["params"] else "labels")]
            )
        # support both -tags and -labels ("labels" name has been used in pre-0.1.5 versions)
        # FIXME: this support should be removed after early repositories are converted
        elif diff_action == "remove-tags" or diff_action == "remove-labels":
            if "tags" not in issue_data:
                issue_data["tags"] = []
            for l in d["params"][("tags" if "tags" in d["params"] else "labels")]:
                issue_data["tags"].remove(l)
        elif diff_action == "parameter-set":
            if "parameters" not in issue_data:
                issue_data["parameters"] = {}
            issue_data["parameters"][d["params"]["key"]] = d["params"]["value"]
        elif diff_action == "parameter-remove":
            if "parameters" not in issue_data:
                issue_data["parameters"] = {}
            del issue_data["parameters"][d["params"]["key"]]
        elif diff_action == "push-milestones":
            if "milestones" not in issue_data:
                issue_data["milestones"] = []
            issue_data["milestones"].extend(d["params"]["milestones"])
        elif diff_action == "set-status":
            issue_data["status"] = d["params"]["status"]
        elif diff_action == "set-project-tag":
            issue_data["project.tag"] = d["params"]["tag"]
        elif diff_action == "set-project-name":
            issue_data["project.name"] = d["params"]["name"]
        elif diff_action == "chain-attach":
            if "attached" not in issue_data:
                issue_data["attached"] = []
            issue_data["attached"].extend(d["params"]["sha1"])
        elif diff_action == "chain-link":
            if "chained" not in issue_data:
                issue_data["chained"] = []
            issue_data["chained"].extend(d["params"]["sha1"])
        elif diff_action == "chain-unlink":
            if "chained" not in issue_data:
                issue_data["chained"] = []
                continue
            for s in d["params"]["sha1"]:
                issue_data["chained"].remove(s)

    # remove duplicated tags
    issue_data["tags"] = list(set(issue_data.get("tags", [])))

    issue_total_time_spent = None
    if issue_work_in_progress_time_deltas:
        issue_total_time_spent = issue_work_in_progress_time_deltas[0]
        for td in issue_work_in_progress_time_deltas[1:]:
            issue_total_time_spent += td

    repo_config = issue.config.getConfig()
    if issue_work_started.get(repo_config["author.email"]) is not None:
        if issue_total_time_spent is not None:
            issue_total_time_spent += datetime.datetime.now() - issue_work_started.get(
                repo_config["author.email"]
            )
        else:
            issue_total_time_spent = datetime.datetime.now() - issue_work_started.get(
                repo_config["author.email"]
            )
    if issue_total_time_spent is not None:
        issue_data["total_time_spent"] = str(issue_total_time_spent).rsplit(".", 1)[0]

    with open(issue_file_path, "w") as ofstream:
        ofstream.write(json.dumps(issue_data))


def revindexIssue(issue_sha1, *diffs):
    issue_data = {}
    issue_file_path = os.path.join(
        ISSUES_PATH, issue_sha1[:2], "{0}.json".format(issue_sha1)
    )
    with open(issue_file_path) as ifstream:
        issue_data = json.loads(ifstream.read())

    repo_config = getConfig()

    issue_author_email = issue_data.get(
        "open.author.email", repo_config["author.email"]
    )
    issue_author_name = issue_data.get("open.author.name", repo_config["author.name"])
    issue_open_timestamp = issue_data.get(
        "open.timestamp", issue_data.get("timestamp", 0)
    )
    issue_differences = [
        {
            "action": "open",
            "author": {
                "author.email": issue_author_email,
                "author.name": issue_author_name,
            },
            "timestamp": issue_open_timestamp,
        },
        {
            "action": "set-message",
            "params": {
                "text": issue_data["message"],
            },
            "author": {
                "author.email": issue_author_email,
                "author.name": issue_author_name,
            },
            "timestamp": issue_open_timestamp + 1,
        },
        {
            "action": "push-tags",
            "params": {
                "tags": issue_data["tags"],
            },
            "author": {
                "author.email": issue_author_email,
                "author.name": issue_author_name,
            },
            "timestamp": issue_open_timestamp + 1,
        },
        {
            "action": "push-milestones",
            "params": {
                "milestones": issue_data.get("milestones", []),
            },
            "author": {
                "author.email": issue_author_email,
                "author.name": issue_author_name,
            },
            "timestamp": issue_open_timestamp + 1,
        },
    ]
    if issue_data.get("status", "open") == "closed":
        issue_close_diff = {
            "action": "close",
            "params": {},
            "author": {
                "author.email": issue_data.get(
                    "close.author.email", repo_config["author.email"]
                ),
                "author.name": issue_data.get(
                    "close.author.name", repo_config["author.name"]
                ),
            },
            "timestamp": issue_data.get("close.timestamp", 0),
        }
        if "closing_git_commit" in issue_data:
            issue_close_diff["closing_git_commit"] = issue_data["closing_git_commit"]
        issue_differences.append(issue_close_diff)

    issue_diff_sha1 = "{0}{1}{2}{3}".format(
        repo_config["author.email"],
        repo_config["author.name"],
        timestamp(),
        random.random(),
    )
    issue_diff_sha1 = issue.util.misc.create_hash(issue_diff_sha1)
    issue_diff_file_path = os.path.join(
        ISSUES_PATH,
        issue_sha1[:2],
        issue_sha1,
        "diff",
        "{0}.json".format(issue_diff_sha1),
    )
    with open(issue_diff_file_path, "w") as ofstream:
        ofstream.write(json.dumps(issue_differences))


def dropIssue(issue_sha1):
    issue_group_path = os.path.join(issue.util.paths.issues_path(), issue_sha1[:2])
    issue_file_path = os.path.join(issue_group_path, "{0}.json".format(issue_sha1))
    os.unlink(issue_file_path)
    shutil.rmtree(os.path.join(issue_group_path, issue_sha1))


def sluggify(issue_message):
    return "-".join(
        re.compile("[^ a-zA-Z0-9_]")
        .sub(" ", unidecode.unidecode(issue_message).lower())
        .split()
    )
