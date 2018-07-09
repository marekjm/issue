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
