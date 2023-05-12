import hashlib
import datetime


def first(seq):
    return seq[0]


def first_or(seq, alternative):
    try:
        return first(seq)
    except IndexError:
        return alternative


def timestamp(dt: datetime.datetime = None):
    return (dt or datetime.datetime.now()).timestamp()


def create_hash(s: str) -> str:
    return hashlib.sha3_384(s.encode("utf-8")).hexdigest()
