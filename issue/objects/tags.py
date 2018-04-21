import os

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
            if diff['action'] == 'push-tags':
                available_tags.extend(diff['params']['tags'])
                for t in diff['params']['tags']:
                    if t not in tag_to_issue_map:
                        tag_to_issue_map[t] = []
                    tag_to_issue_map[t].append(issue_sha1)
    for t in ls():
        available_tags.append(t)
        if t not in tag_to_issue_map:
            tag_to_issue_map[t] = []
    return (available_tags, tag_to_issue_map)
