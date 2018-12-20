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

class RepositoryNotFound(IssueException):
    pass

class TagExists(IssueException):
    pass

class Invalid_time_delta_specification(IssueException):
    pass
