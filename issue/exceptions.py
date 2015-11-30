#!/usr/bin/env python3


class IssueException(Exception):
    pass

class NotAnIssue(IssueException):
    pass

class NotIndexed(IssueException):
    pass

class IssueUIDNotMatched(IssueException):
    pass

class IssueUIDAmbiguous(IssueException):
    pass

class RepositoryExists(IssueException):
    pass

class TagExists(IssueException):
    pass
