import json
import os
import random
import shutil

import issue


def ls():
    return os.listdir(issue.util.paths.tags_path())


def gather():
    available_tags = []
    tag_to_issue_map = {}
    for issue_sha1 in sorted(issue.util.issues.ls()):
        issue_differences = issue.util.issues.getIssueDifferences(
            issue_sha1,
            *issue.util.issues.listIssueDifferences(issue_sha1),
        )
        for diff in issue_differences[::-1]:
            if diff["action"] == "push-tags":
                available_tags.extend(diff["params"]["tags"])
                for t in diff["params"]["tags"]:
                    if t not in tag_to_issue_map:
                        tag_to_issue_map[t] = []
                    tag_to_issue_map[t].append(issue_sha1)
    for t in ls():
        available_tags.append(t)
        if t not in tag_to_issue_map:
            tag_to_issue_map[t] = []
    return (available_tags, tag_to_issue_map)


def make(tag_name: str, force: bool = False):
    tag_path = os.path.join(issue.util.paths.tags_path(), tag_name)
    if os.path.isdir(tag_path) and force:
        shutil.rmtree(tag_path)
    if os.path.isdir(tag_path):
        raise issue.exceptions.TagExists(tag_name)

    os.mkdir(tag_path)
    os.mkdir(os.path.join(tag_path, "diff"))

    repo_config = issue.config.getConfig()

    tag_differences = [
        {
            "action": "tag-open",
            "params": {
                "name": tag_name,
            },
            "author": {
                "author.email": repo_config["author.email"],
                "author.name": repo_config["author.name"],
            },
            "timestamp": issue.util.misc.timestamp(),
        },
    ]
    if "project.name" in repo_config:
        tag_differences.append(
            {
                "action": "tag-set-project-name",
                "params": {
                    "name": repo_config["project.name"],
                },
                "author": {
                    "author.email": repo_config["author.email"],
                    "author.name": repo_config["author.name"],
                },
                "timestamp": timestamp(),
            }
        )

    tag_diff_sha1 = "{0}{1}{2}{3}{4}".format(
        tag_name,
        repo_config["author.email"],
        repo_config["author.name"],
        issue.util.misc.timestamp(),
        random.random(),
    )
    tag_diff_sha1 = issue.util.misc.create_hash(tag_diff_sha1)
    tag_diff_file_path = os.path.join(
        tag_path, "diff", "{0}.json".format(tag_diff_sha1)
    )
    with open(tag_diff_file_path, "w") as ofstream:
        ofstream.write(json.dumps(tag_differences))

    return tag_name
