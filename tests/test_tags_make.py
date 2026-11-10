"""Tests for tag creation (issue.objects.tags.make)."""

import json
import os

import issue
import issue.objects.tags
import issue.util.paths


def _init_repo(path, config):
    os.makedirs(os.path.join(path, ".issue", "objects", "tags"))
    with open(os.path.join(path, ".issue", "config.json"), "w") as ofstream:
        ofstream.write(json.dumps(config))


def test_make_tag_with_project_name(tmp_path, monkeypatch):
    _init_repo(str(tmp_path), {
        "author.email": "a@example.com",
        "author.name": "A Uthor",
        "project.name": "My Project",
    })
    monkeypatch.chdir(tmp_path)
    issue.util.paths._ISSUE_REPOSITORY_PATH = None
    try:
        assert issue.objects.tags.make("mytag") == "mytag"
    finally:
        issue.util.paths._ISSUE_REPOSITORY_PATH = None
    diff_dir = tmp_path / ".issue" / "objects" / "tags" / "mytag" / "diff"
    assert len(os.listdir(diff_dir)) == 1
